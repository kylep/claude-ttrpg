from ttrpg_engine import coordinator as co


def test_session_starts_with_active_pc(wroot, monkeypatch):
    from ttrpg_engine import viewer_data
    monkeypatch.setattr(viewer_data, "state_snapshot",
                        lambda *args: {"encounter": {"up": "pc-squakee"}})
    assert co._start_with_active_pc(wroot,
        ["ttrpg-meowcicles", "ttrpg-squakee", "ttrpg-spike"]) == [
            "ttrpg-squakee", "ttrpg-spike", "ttrpg-meowcicles"]


def test_coordinator_calls_one_turn_at_a_time_and_stops_on_quota(wroot, monkeypatch):
    monkeypatch.setenv("TTRPG_GM_AGENT", "pilot-gm")
    monkeypatch.setenv("TTRPG_PLAYERS", "pilot-a,pilot-b")
    used = {"value": 0.48}
    sent = []

    def api(method, path, body=None):
        if path == "/api/quota":
            return {"codex": {"seven_day": {"utilization": used["value"]},
                              "stale": False}}
        if path == "/api/relay/channels":
            return [{"id": "room", "name": "ttrpg-table", "archived_at": None}]
        if path == "/api/relay/channels/room/messages?limit=100":
            return []
        if path == "/api/relay/channels/room/messages?limit=100&after=invite-0":
            return [{"id": "reply-0", "author": "agent:pilot-gm", "run_id": "r0"}]
        if path == "/api/relay/channels/room/messages?limit=100&after=reply-0":
            return []
        if path == "/api/runs/r0":
            return {"state": "succeeded"}
        if method == "POST" and path == "/api/relay/channels/room/messages":
            sent.append(body["body"])
            return {"id": f"invite-{len(sent)-1}"}
        raise AssertionError((method, path))

    monkeypatch.setattr(co, "_api", api)
    c = co.Coordinator(wroot)
    assert c.start(max_player_turns=2)["state"] == "active"
    c.tick()
    assert len(sent) == 1 and sent[0].startswith("@pilot-gm")
    assert co.read_control(wroot)["state"] == "waiting"
    c.tick()
    waiting = co.read_control(wroot)
    assert waiting["candidate_run_id"] == "r0"
    waiting["candidate_at"] -= 3
    co.write_control(wroot, waiting)
    c.tick()
    assert co.read_control(wroot)["step"] == 1
    c.tick()
    assert len(sent) == 2 and sent[1].startswith("@pilot-a")
    used["value"] = 0.91
    c.tick()
    assert co.read_control(wroot)["state"] == "paused"
    assert len(sent) == 2
