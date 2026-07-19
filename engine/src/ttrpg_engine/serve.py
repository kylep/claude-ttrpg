"""Read-only live viewer for a world: engine serve.

Serves a player lens (/) and a GM lens (/gm) over the world's files. The
story feed reads the engine-written story log (state/story.jsonl) — never
the Claude transcript — and /api/entity resolves live entity cards.
Never writes anything.
"""
import errno
import json
import time
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ttrpg_engine import bookexport, story_log, viewer_data, worldfs
from ttrpg_engine import export as export_mod
from ttrpg_engine.errors import EngineError

_POLL_SECONDS = 0.3
_PING_SECONDS = 15


def _sniff_ctype(data: bytes) -> str | None:
    """Recognize a raster image by its magic bytes, so a mislabeled file (e.g. a
    JPEG saved with a .png name) is still served with the right Content-Type.
    Returns None when unrecognized — the caller falls back to the extension."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


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
    try:
        return (root / "state" / "story.jsonl").stat().st_mtime
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
                try:
                    offset = max(0, int(query.get("offset", ["0"])[0]))
                except ValueError:
                    offset = 0
                entries, offset = story_log.read(self.root, offset, lens=lens)
                self._json({"entries": entries, "cursor": {"offset": offset}})
            elif path.startswith("/api/entity/"):
                lens = "gm" if query.get("lens", ["player"])[0] == "gm" else "player"
                ref = path.removeprefix("/api/entity/")
                try:
                    self._json(viewer_data.entity_card(self.root, self.game, ref, lens))
                except EngineError as e:
                    self._json({"error": e.code}, 404)
            elif path == "/events":
                self._events()
            elif path.startswith("/renders/"):
                self._render_file(path.removeprefix("/renders/"))
            elif path.startswith("/art/"):
                self._content_art_file(path.removeprefix("/art/"))
            elif path == "/api/glossary":
                src = export_mod.resolve_source(self.root, None)
                self._json(bookexport.glossary_manifest(src))
            elif path.startswith("/api/glossary/"):
                name = path.removeprefix("/api/glossary/")
                lens = "gm" if query.get("lens", ["player"])[0] == "gm" else "player"
                src = export_mod.resolve_source(self.root, None)
                try:
                    self._json(bookexport.glossary_section(src, name, lens))
                except KeyError:
                    self._json({"error": "not found"}, 404)
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
        """Serve a file from the world's renders/ dir; the resolved-path check
        rejects any `name` that would escape it (path traversal)."""
        renders = (self.root / "renders").resolve()
        target = (renders / name).resolve()
        if not target.is_relative_to(renders) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        ctype = {"svg": "image/svg+xml", "html": "text/html; charset=utf-8",
                 "png": "image/png"}.get(target.suffix.lstrip("."),
                                         "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def _content_art_file(self, name: str) -> None:
        """Serve an image asset from the game's content/art dir (e.g. a bestiary
        portrait a monster card points at). The resolved-path check rejects any
        `name` that would escape it (path traversal), and only image suffixes
        are served — never the game's yaml content. Read-only."""
        content = self.game.get("content_dir")
        if content is None:
            self._json({"error": "not found"}, 404)
            return
        art = (Path(content) / "art").resolve()
        target = (art / name).resolve()
        if not target.is_relative_to(art) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        by_suffix = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "webp": "image/webp", "gif": "image/gif",
                     "svg": "image/svg+xml"}.get(target.suffix.lstrip(".").lower())
        if by_suffix is None:                   # images only, not yaml/lore
            self._json({"error": "not found"}, 404)
            return
        data = target.read_bytes()
        # trust the bytes over the extension: our generated portraits are often
        # JPEG saved as .png, and a wrong Content-Type is worth avoiding.
        self._send(200, data, _sniff_ctype(data) or by_suffix)

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
