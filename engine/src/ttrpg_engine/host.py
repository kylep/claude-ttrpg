"""Hosted, authenticated table view and narrow agent-to-engine bridge.

The existing ``engine serve`` remains a local, read-only convenience. This
server is the deployment boundary: nginx authenticates browser requests and
the platform's brokered tool authenticates internal agent requests. The GM is
the only caller that can execute engine commands. All world writes are
serialized, and a started command is never automatically retried after an
ambiguous failure.
"""
from __future__ import annotations

import hmac
import json
import os
import subprocess
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from ttrpg_engine import serve, worldfs
from ttrpg_engine.coordinator import Coordinator, read_control

PREFIX = "/apps/ttrpg"
MAX_BODY = 16_384
MAX_ARGV = 32
MAX_ARG = 2_000
DENIED_TOP_LEVEL = {"world", "game", "export", "override", "serve", "dice"}
DENIED_FLAGS = {"--world", "--game", "--out", "--seed"}


def _ledger_path(root: Path) -> Path:
    return root / "state" / "host-commands.json"


def _read_ledger(root: Path) -> dict:
    path = _ledger_path(root)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _write_ledger(root: Path, data: dict) -> None:
    path = _ledger_path(root)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, separators=(",", ":")))
    temp.replace(path)


def _safe_argv(argv: object) -> list[str] | None:
    if not isinstance(argv, list) or not 1 <= len(argv) <= MAX_ARGV:
        return None
    if not all(isinstance(a, str) and 0 < len(a) <= MAX_ARG for a in argv):
        return None
    if argv[0].startswith("-") or argv[0] in DENIED_TOP_LEVEL:
        return None
    if any(a in DENIED_FLAGS or "\x00" in a for a in argv):
        return None
    # The hosted GM operates this world, never a path supplied by a model.
    if any("/" in a or "\\" in a or ".." in a for a in argv):
        return None
    return argv


class _HostedHandler(serve._Handler):
    command_lock = threading.Lock()
    coordinator: Coordinator

    def _caller(self) -> str | None:
        expected = os.environ.get("AP_API_TOKEN", "")
        actual = self.headers.get("Authorization", "")
        if not expected or not hmac.compare_digest(actual, "Bearer " + expected):
            return None
        caller = self.headers.get("X-Tool-Caller-Agent", "").strip()
        return caller or None

    def do_GET(self):
        if self.path == "/healthz":
            try:
                worldfs.load_game_for(self.root)
            except Exception:
                self._json({"ok": False}, 503)
            else:
                self._json({"ok": True})
            return
        if self.path == PREFIX + "/api/session":
            if not self.headers.get("X-AP-User", "").strip():
                self._json({"error": "unauthorized"}, 401)
            else:
                self._json(read_control(self.root))
            return
        if self.path == "/_internal/view":
            if not self._caller():
                self._json({"error": "unauthorized"}, 401)
                return
            from ttrpg_engine import story_log, viewer_data
            state = viewer_data.state_snapshot(self.root, self.game, "player")
            entries, _ = story_log.read(self.root, 0, lens="player")
            self._json({"state": state, "story": entries[-12:]})
            return
        if not self.path.startswith(PREFIX + "/") and self.path != PREFIX:
            self._json({"error": "not found"}, 404)
            return
        # nginx removes client-supplied identity headers and adds these after
        # its auth_request. A direct in-cluster connection gets no identity.
        if not self.headers.get("X-AP-User", "").strip():
            self._json({"error": "unauthorized"}, 401)
            return
        admin = self.headers.get("X-AP-Role") == "admin"
        parsed = urlparse(self.path)
        relative = parsed.path[len(PREFIX):] or "/"
        if relative == "/gm" and not admin:
            self._json({"error": "forbidden"}, 403)
            return
        if relative.startswith("/renders/") and not admin:
            self._json({"error": "forbidden"}, 403)
            return
        allowed = (relative in {"/", "/gm", "/events", "/api/state",
                                "/api/story", "/api/glossary"}
                   or relative.startswith(("/api/entity/", "/api/glossary/",
                                           "/art/", "/maps/", "/renders/")))
        if not allowed:
            self._json({"error": "not found"}, 404)
            return
        query = parse_qs(parsed.query)
        query["lens"] = ["gm" if admin and relative == "/gm" else "player"]
        self.path = relative + "?" + urlencode(query, doseq=True)
        super().do_GET()

    def do_POST(self):
        if self.path == PREFIX + "/api/session":
            if (not self.headers.get("X-AP-User", "").strip()
                    or self.headers.get("X-AP-Role") != "admin"):
                self._json({"error": "forbidden"}, 403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1024:
                    raise ValueError("body size")
                body = json.loads(self.rfile.read(size))
                action = body.get("action")
                if action == "start":
                    result = self.coordinator.start(
                        max_player_turns=body.get("max_player_turns", 8),
                        max_minutes=body.get("max_minutes", 60))
                elif action == "pause":
                    result = self.coordinator.pause()
                elif action == "resume":
                    result = self.coordinator.resume()
                else:
                    raise ValueError("action must be start, pause or resume")
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self._json({"error": str(exc)}, 400)
            else:
                self._json(result)
            return
        if self.path != "/_internal/command":
            self._json({"error": "not found"}, 404)
            return
        if self._caller() != os.environ.get("TTRPG_GM_AGENT", "ttrpg-gm"):
            self._json({"error": "forbidden"}, 403)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                raise ValueError("body size")
            body = json.loads(self.rfile.read(size))
            request_id = body["request_id"]
            argv = _safe_argv(body.get("argv"))
            if (not isinstance(request_id, str) or len(request_id) > 80
                    or not request_id or argv is None):
                raise ValueError("invalid command")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            self._json({"error": "invalid request"}, 400)
            return
        with self.command_lock:
            ledger = _read_ledger(self.root)
            old = ledger.get(request_id)
            if old:
                if old.get("argv") != argv:
                    self._json({"error": "request_id reused"}, 409)
                elif old.get("state") == "done":
                    self._json(old["result"])
                else:
                    # A process may have died after applying a state change.
                    # Returning 409 is safer than silently re-running it.
                    self._json({"error": "outcome uncertain; inspect world"}, 409)
                return
            ledger[request_id] = {"argv": argv, "state": "started"}
            _write_ledger(self.root, ledger)
            try:
                proc = subprocess.run(["engine", "--world", str(self.root), *argv],
                                      capture_output=True, text=True, timeout=90,
                                      check=False, cwd=self.root,
                                      env={"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                                           "HOME": "/tmp", "LANG": "C.UTF-8"})
                result = {"exit_code": proc.returncode,
                          "output": proc.stdout[-32_000:],
                          "error": proc.stderr[-2_000:]}
            except (OSError, subprocess.TimeoutExpired) as exc:
                self._json({"error": f"engine command uncertain: {type(exc).__name__}"}, 503)
                return
            ledger[request_id] = {"argv": argv, "state": "done", "result": result}
            _write_ledger(self.root, ledger)
        self._json(result)


def run(root: Path, port: int = 8000) -> ThreadingHTTPServer:
    root = Path(root).resolve()
    game = worldfs.load_game_for(root)
    coordinator = Coordinator(root)
    _HostedHandler.coordinator = coordinator
    server = ThreadingHTTPServer(("0.0.0.0", port), partial(_HostedHandler, root, game))
    server.daemon_threads = True
    if os.environ.get("TTRPG_COORDINATOR", "") == "1":
        threading.Thread(target=coordinator.run_forever, daemon=True).start()
    return server


def main() -> None:
    root = Path(os.environ.get("TTRPG_WORLD", "/world"))
    server = run(root, int(os.environ.get("PORT", "8000")))
    try:
        server.serve_forever()
    finally:
        server.server_close()
