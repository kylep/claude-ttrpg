import time

from ttrpg_engine import coordinator as co


def test_session_starts_with_active_pc(wroot, monkeypatch):
    from ttrpg_engine import viewer_data
    monkeypatch.setattr(viewer_data, "state_snapshot",
                        lambda *args: {"encounter": {"up": "pc-squakee"}})
    assert co._start_with_active_pc(wroot,
        ["ttrpg-meowcicles", "ttrpg-squakee", "ttrpg-spike"]) == [
            "ttrpg-squakee", "ttrpg-spike", "ttrpg-meowcicles"]


def test_monster_keeps_gm_on_floor_until_pc_is_up(wroot, monkeypatch):
    monkeypatch.setattr(co, "_current_actor", lambda root: "giant_rat-3")
    control = {"gm": "ttrpg-gm", "players": ["ttrpg-squakee", "ttrpg-spike"],
               "step": 4, "last_actor": "gm", "player_turns": 1}
    assert co._next_target(control, wroot) == "ttrpg-gm"
    monkeypatch.setattr(co, "_current_actor", lambda root: "pc-spike")
    assert co._next_target(control, wroot) == "ttrpg-spike"
    control["last_actor"] = "player"
    assert co._next_target(control, wroot) == "ttrpg-gm"


def test_table_invites_are_short_and_name_the_actor():
    invite = co._invitation(3, "ttrpg-fluffy", "ttrpg-gm", ["ttrpg-fluffy"])
    assert invite == "@ttrpg-fluffy 🎭 Your move, Fluffy."


def test_relay_budget_refusal_pauses_without_waiting_for_a_run(wroot, monkeypatch):
    monkeypatch.setattr(co, "_quota_ok", lambda: True)
    monkeypatch.setattr(co, "_messages", lambda *args: [{
        "id": "budget-notice", "author": "system:relay",
        "body": "⏸️ paused: this room has used its hourly agent budget (30/hour); try again later"}])
    c = co.Coordinator(wroot)
    co.write_control(wroot, {"state": "waiting", "channel_id": "room", "gm": "ttrpg-gm",
                                "players": ["ttrpg-fluffy"], "step": 1,
                                "player_turns": 0, "max_player_turns": 4,
                                "last_actor": "gm", "deadline": time.time() + 600,
                                "cursor": "invitation", "awaiting": "ttrpg-fluffy"})
    c.tick()
    paused = co.read_control(wroot)
    assert paused["state"] == "paused"
    assert paused["awaiting"] is None
    assert 0 < paused["remaining_seconds"] <= 600
    resumed = c.resume()
    assert resumed["state"] == "active"
    assert resumed["deadline"] > time.time() + 590
    c.pause()
    assert c.stop()["state"] == "complete"


def test_budget_notice_consumed_before_rollout_is_recovered(wroot, monkeypatch):
    monkeypatch.setattr(co, "_quota_ok", lambda: True)
    notice = {"id": "budget-notice", "author": "system:relay",
              "body": "⏸️ paused: this room has used its hourly agent budget (30/hour)"}
    monkeypatch.setattr(co, "_messages",
                        lambda channel, after: [] if after else [notice])
    co.write_control(wroot, {"state": "waiting", "channel_id": "room", "gm": "ttrpg-gm",
                                "players": ["ttrpg-fluffy"], "step": 1,
                                "player_turns": 0, "max_player_turns": 4,
                                "last_actor": "gm", "deadline": time.time() + 600,
                                "cursor": "budget-notice", "invite_id": "invitation",
                                "awaiting": "ttrpg-fluffy"})
    co.Coordinator(wroot).tick()
    assert co.read_control(wroot)["state"] == "paused"


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
    assert co.read_control(wroot)["last_actor"] == "gm"
    c.tick()
    assert len(sent) == 2 and sent[1].startswith("@pilot-a")
    used["value"] = 0.91
    c.tick()
    assert co.read_control(wroot)["state"] == "paused"
    assert len(sent) == 2
