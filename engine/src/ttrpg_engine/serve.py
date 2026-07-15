"""Read-only live viewer for a world: engine serve.

Serves a player lens (/) and a GM lens (/gm) over the world's files plus
the Claude Code session transcript (story feed). Never writes anything.
"""
import errno
import json
import time
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ttrpg_engine import story, viewer_data, worldfs
from ttrpg_engine.errors import EngineError

_POLL_SECONDS = 0.3
_PING_SECONDS = 15


def _world_mtime(root: Path) -> float:
    """Newest mtime under the dirs whose changes the viewer cares about."""
    latest = 0.0
    for sub in ("state", "timeline", "renders"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            try:
                latest = max(latest, p.stat().st_mtime)
            except OSError:
                pass
    return latest


def _story_mtime(root: Path) -> float:
    t = story.latest_transcript(root)
    try:
        return t.stat().st_mtime if t else 0.0
    except OSError:
        return 0.0


class _Handler(BaseHTTPRequestHandler):
    def __init__(self, root: Path, game: dict, *args, **kwargs):
        self.root = root
        self.game = game
        super().__init__(*args, **kwargs)

    def log_message(self, *args):  # keep the terminal clean for the operator
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            if path in ("/", "/gm"):
                page = resources.files("ttrpg_engine").joinpath("viewer.html").read_bytes()
                self._send(200, page, "text/html; charset=utf-8")
            elif path == "/api/state":
                lens = query.get("lens", ["player"])[0]
                self._json(viewer_data.state_snapshot(self.root, self.game, lens))
            elif path == "/api/story":
                lens = "gm" if query.get("lens", ["player"])[0] == "gm" else "player"
                cursor = None
                if "file" in query:
                    try:
                        offset = int(query.get("offset", ["0"])[0])
                    except ValueError:
                        offset = 0
                    cursor = {"file": query["file"][0], "offset": offset}
                entries, cursor = story.read_story(self.root, cursor, lens=lens)
                self._json({"entries": entries, "cursor": cursor})
            elif path == "/events":
                self._events()
            elif path.startswith("/renders/"):
                self._render_file(path.removeprefix("/renders/"))
            else:
                self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # a broken pane must not kill the server
            try:
                self._json({"error": str(e)}, 500)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _render_file(self, name: str) -> None:
        renders = (self.root / "renders").resolve()
        target = (renders / name).resolve()
        if not target.is_relative_to(renders) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        ctype = {"svg": "image/svg+xml", "html": "text/html; charset=utf-8",
                 "png": "image/png"}.get(target.suffix.lstrip("."),
                                         "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def _events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b"retry: 1000\n\n")
        self.wfile.flush()
        world_seen = _world_mtime(self.root)
        story_seen = _story_mtime(self.root)
        last_ping = time.monotonic()
        while True:
            time.sleep(_POLL_SECONDS)
            world_now = _world_mtime(self.root)
            story_now = _story_mtime(self.root)
            out = b""
            if world_now != world_seen:
                world_seen = world_now
                out += b"event: state\ndata: {}\n\n"
            if story_now != story_seen:
                story_seen = story_now
                out += b"event: story\ndata: {}\n\n"
            if not out and time.monotonic() - last_ping > _PING_SECONDS:
                out = b": ping\n\n"
            if out:
                last_ping = time.monotonic()
                self.wfile.write(out)
                self.wfile.flush()


def run(root: Path, port: int) -> ThreadingHTTPServer:
    game = worldfs.load_game_for(root)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port),
                                     partial(_Handler, root, game))
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            raise EngineError("port_busy", f"port {port} is in use (try --port)")
        raise
    server.daemon_threads = True
    return server
