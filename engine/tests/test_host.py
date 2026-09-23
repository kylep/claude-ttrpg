"""The hosted view's identity boundary and command retry contract."""
import http.client
import json
import threading
from types import SimpleNamespace

from ttrpg_engine import host


def _req(port, method, path, *, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, raw, headers or {})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def test_hosted_player_cannot_choose_gm_lens_or_bypass_login(wroot, monkeypatch):
    monkeypatch.setenv("AP_API_TOKEN", "test-app-key")
    server = host.run(wroot, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        assert _req(port, "GET", "/apps/ttrpg/")[0] == 401
        reader = {"X-AP-User": "player", "X-AP-Role": "reader"}
        status, page = _req(port, "GET", "/apps/ttrpg/", headers=reader)
        assert status == 200 and b'VIEW_ROOT' in page
        assert _req(port, "GET", "/apps/ttrpg/gm", headers=reader)[0] == 403
        status, raw = _req(port, "GET", "/apps/ttrpg/api/state?lens=gm", headers=reader)
        assert status == 200
        state = json.loads(raw)
        assert "internals" not in state and "timeline" not in state
        assert _req(port, "GET", "/apps/ttrpg/renders/secret.html", headers=reader)[0] == 403
        assert _req(port, "GET", "/_internal/view")[0] == 401
        status, raw = _req(port, "GET", "/_internal/view", headers={
            "Authorization": "Bearer test-app-key", "X-Tool-Caller-Agent": "pc-fluffy"})
        assert status == 200 and "state" in json.loads(raw)
        assert _req(port, "GET", "/_internal/gm-view", headers={
            "Authorization": "Bearer test-app-key", "X-Tool-Caller-Agent": "pc-fluffy"})[0] == 403
    finally:
        server.shutdown()
        server.server_close()


def test_only_gm_commands_and_retries_are_idempotent(wroot, monkeypatch):
    monkeypatch.setenv("AP_API_TOKEN", "test-app-key")
    monkeypatch.setenv("TTRPG_GM_AGENT", "test-gm")
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr="")

    monkeypatch.setattr(host.subprocess, "run", fake_run)
    server = host.run(wroot, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        body = {"request_id": "turn-1", "argv": ["story", "scene", "--title", "A door"]}
        base = {"Authorization": "Bearer test-app-key", "Content-Type": "application/json"}
        assert _req(port, "POST", "/_internal/command", headers={
            **base, "X-Tool-Caller-Agent": "player"}, body=body)[0] == 403
        gm = {**base, "X-Tool-Caller-Agent": "test-gm"}
        status, raw = _req(port, "POST", "/_internal/command", headers=gm, body=body)
        assert status == 200 and json.loads(raw)["exit_code"] == 0
        assert _req(port, "POST", "/_internal/command", headers=gm, body=body)[0] == 200
        assert len(calls) == 1
        prefixed = {"request_id": "a" * 32 + ":" + "quarterstaff-giant-rat-4" * 2,
                    "argv": ["attack", "--attacker", "pc-meowcicles",
                             "--target", "giant_rat-4"]}
        assert _req(port, "POST", "/_internal/command", headers=gm, body=prefixed)[0] == 200
        assert len(calls) == 2
        bad = {"request_id": "turn-2", "argv": ["export", "book", "--out", "/tmp"]}
        assert _req(port, "POST", "/_internal/command", headers=gm, body=bad)[0] == 400
        assert len(calls) == 2
    finally:
        server.shutdown()
        server.server_close()
