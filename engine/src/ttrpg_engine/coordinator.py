"""A bounded turn caller for an agent table in Relay.

This service chooses *who* has the floor, never what a character does. Agent
answers come through Relay's ordinary invocation path and keep its existing
hop/rate guards. Durable control state lets a restart resume without emitting
a second invitation for the same turn.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CONTROL_FILE = "state/table-control.json"
POLL_SECONDS = 3


def _path(root: Path) -> Path:
    return root / CONTROL_FILE


def read_control(root: Path) -> dict:
    path = _path(root)
    return json.loads(path.read_text()) if path.exists() else {"state": "idle"}


def write_control(root: Path, value: dict) -> None:
    path = _path(root)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, separators=(",", ":")))
    tmp.replace(path)


def _api(method: str, path: str, body: dict | None = None):
    base = os.environ.get("AP_API_URL", "http://agent-platform-api:8000").rstrip("/")
    token = os.environ["AP_API_TOKEN"]
    payload = json.dumps(body).encode() if body is not None else None
    request = Request(base + path, data=payload, method=method,
                      headers={"Authorization": "Bearer " + token,
                               "Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def _channel_id(name: str) -> str:
    for ch in _api("GET", "/api/relay/channels"):
        if ch.get("name") == name and ch.get("archived_at") is None:
            return ch["id"]
    raise RuntimeError(f"Relay channel #{name} is missing")


def _messages(channel_id: str, after: str | None) -> list[dict]:
    query = "?limit=100" + ("&" + urlencode({"after": after}) if after else "")
    return _api("GET", f"/api/relay/channels/{channel_id}/messages{query}")


def _quota_ok() -> bool:
    quota = _api("GET", "/api/quota")
    codex = quota.get("codex") or {}
    seven_day = codex.get("seven_day") or {}
    use = seven_day.get("utilization")
    # Fail closed if the reading is absent/stale; no blind spend.
    return (not codex.get("stale", False) and isinstance(use, (int, float))
            and use < 0.90)


def _cast() -> tuple[str, list[str]]:
    gm = os.environ.get("TTRPG_GM_AGENT", "ttrpg-gm")
    players = [x.strip() for x in os.environ.get("TTRPG_PLAYERS", "").split(",") if x.strip()]
    if not players:
        raise RuntimeError("TTRPG_PLAYERS is empty")
    return gm, players


def _start_with_active_pc(root: Path, players: list[str]) -> list[str]:
    """Begin a new bounded session with the PC whose combat turn is active.

    The pilot's player agent names mirror their PC ids. Outside combat (or
    with a different cast naming scheme) the configured order remains valid.
    """
    from ttrpg_engine import viewer_data, worldfs
    state = viewer_data.state_snapshot(root, worldfs.load_game_for(root), "player")
    up = (state.get("encounter") or {}).get("up")
    for index, agent in enumerate(players):
        if up == "pc-" + agent.removeprefix("ttrpg-"):
            return players[index:] + players[:index]
    return players


def _target(step: int, gm: str, players: list[str]) -> str:
    return gm if step % 2 == 0 else players[((step - 1) // 2) % len(players)]


def _invitation(step: int, target: str, gm: str, players: list[str]) -> str:
    if step == 0:
        ask = ("Open a short scene from the current world. Read the player view, "
               "check the engine state, tell the table what is happening, and "
               "leave a clear choice to the party. Do not decide for any PC.")
    elif target == gm:
        ask = ("Resolve the preceding player's intent with the engine. State the "
               "outcome and what changes. Give the next player room to act. "
               "If the game/UI/tool feels wrong, file a Ticket while it is fresh.")
    else:
        ask = ("Read the current player view with the ttrpg tool, then make one "
               "specific choice for your own PC. Speak to the table in character "
               "if it helps. You may file a Ticket during play if something is "
               "confusing or broken. Do not invent a roll or mutate the world.")
    return f"@{target} — Table turn {step + 1}: {ask}"


class Coordinator:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.lock = threading.Lock()

    def start(self, *, max_player_turns: int = 8, max_minutes: int = 60) -> dict:
        if not 1 <= max_player_turns <= 12 or not 5 <= max_minutes <= 120:
            raise ValueError("turns must be 1–12 and minutes 5–120")
        gm, players = _cast()
        players = _start_with_active_pc(self.root, players)
        with self.lock:
            old = read_control(self.root)
            if old.get("state") in {"active", "waiting", "paused"}:
                raise ValueError("a session is already open")
            if not _quota_ok():
                raise ValueError("Codex weekly quota is at/above 90% used or unavailable")
            channel_id = _channel_id(os.environ.get("TTRPG_CHANNEL", "ttrpg-table"))
            latest = _messages(channel_id, None)
            cursor = latest[0]["id"] if latest else None
            control = {"state": "active", "channel_id": channel_id,
                       "gm": gm, "players": players, "step": 0,
                       "max_player_turns": max_player_turns,
                       "deadline": time.time() + max_minutes * 60,
                       "cursor": cursor, "awaiting": None}
            write_control(self.root, control)
        return control

    def pause(self) -> dict:
        with self.lock:
            control = read_control(self.root)
            if control.get("state") not in {"active", "waiting"}:
                raise ValueError("no active session")
            control["state"] = "paused"
            write_control(self.root, control)
            return control

    def resume(self) -> dict:
        with self.lock:
            control = read_control(self.root)
            if control.get("state") != "paused":
                raise ValueError("session is not paused")
            if not _quota_ok():
                raise ValueError("Codex weekly quota is at/above 90% used or unavailable")
            control["state"] = "waiting" if control.get("awaiting") else "active"
            write_control(self.root, control)
            return control

    def tick(self) -> None:
        with self.lock:
            c = read_control(self.root)
            if c.get("state") not in {"active", "waiting"}:
                return
            if time.time() > c["deadline"]:
                c["state"] = "paused"
                c["reason"] = "session time limit"
            elif not _quota_ok():
                c["state"] = "paused"
                c["reason"] = "Codex weekly allowance below 10% free or unavailable"
            if c["state"] == "paused":
                write_control(self.root, c)
                return
            if c["state"] == "active":
                if c["step"] > c["max_player_turns"] * 2:
                    c["state"] = "complete"
                    write_control(self.root, c)
                    _api("POST", f"/api/relay/channels/{c['channel_id']}/messages",
                         {"body": "Session complete. The table is paused for review and ticket triage."})
                    return
                target = _target(c["step"], c["gm"], c["players"])
                # Mark the invitation as in-flight BEFORE posting it. An
                # ambiguous timeout stops here for inspection; no double wake.
                c["state"] = "posting"
                c["awaiting"] = target
                write_control(self.root, c)
                result = _api("POST", f"/api/relay/channels/{c['channel_id']}/messages",
                              {"body": _invitation(c["step"], target, c["gm"], c["players"])})
                c["invite_id"] = result["id"]
                c["cursor"] = result["id"]
                c["state"] = "waiting"
                write_control(self.root, c)
                return
            messages = _messages(c["channel_id"], c.get("cursor"))
            for msg in messages:
                c["cursor"] = msg["id"]
                if msg.get("author") == "agent:" + c["awaiting"] and msg.get("run_id"):
                    c["candidate_run_id"] = msg["run_id"]
                    c["candidate_at"] = time.time()
            # Tool posts carry the agent's run ID too. Wait for the run's
            # terminal state plus a brief recorder grace, not its first post.
            if c.get("candidate_run_id") and time.time() - c["candidate_at"] >= 2:
                run = _api("GET", "/api/runs/" + c["candidate_run_id"])
                if run.get("state") in {"succeeded", "failed", "cancelled", "rejected"}:
                    if run["state"] != "succeeded":
                        c["state"] = "paused"
                        c["reason"] = f"{c['awaiting']} run {run['state']}"
                    else:
                        c["step"] += 1
                        c["awaiting"] = None
                        c["candidate_run_id"] = None
                        c["state"] = "active"
            write_control(self.root, c)

    def run_forever(self) -> None:
        while True:
            try:
                self.tick()
            except (HTTPError, URLError, OSError, ValueError, RuntimeError, KeyError) as exc:
                # Stay stopped after an ambiguous post rather than reissue it.
                print(f"coordinator tick: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(POLL_SECONDS)
