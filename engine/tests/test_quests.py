import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc
from test_spells import CLERIC

runner = CliRunner()


def _sheet(wroot, pc):
    return worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")


def _quest(wroot, quest_id):
    return worldfs.read_yaml(wroot / "state" / "quests" / f"{quest_id}.yaml")


def _npcs(wroot):
    path = wroot / "state" / "npcs.yaml"
    return worldfs.read_yaml(path) if path.exists() else {}


def _latest_event(wroot):
    files = sorted((wroot / "timeline").glob("*.yaml"))
    return worldfs.read_yaml(files[-1])


def _offer(**kwargs):
    args = ["quest", "offer"]
    for k, v in kwargs.items():
        if isinstance(v, bool):
            if v:
                args.append(f"--{k.replace('_', '-')}")
        else:
            args += [f"--{k.replace('_', '-')}", str(v)]
    return runner.invoke(app, args)


def test_pc_offers_gold_and_item_quest_escrows_and_debits(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "2"])
    res = _offer(title="Fetch Firewood", desc="bring wood back", giver=f"pc:{pc}",
                 gold=5, items="torch")
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    quest_id = payload["id"]
    assert quest_id == "fetch-firewood"

    sheet = _sheet(wroot, pc)
    assert sheet["gold"] == 5  # fighter starts with 10
    assert {"item": "torch", "qty": 1} in sheet["inventory"]

    quest = _quest(wroot, quest_id)
    assert quest["status"] == "offered"
    assert quest["giver"] == {"type": "pc", "id": pc}
    assert quest["escrow"] == {"gold": 5, "items": ["torch"]}
    assert quest["escrow_from"] == {"type": "pc", "id": pc}
    assert quest["reward"] == {"gold": 5, "items": ["torch"], "xp": 0, "spawn": False}


def test_npc_offer_beyond_holdings_not_enough(wroot):
    res = _offer(title="Too Rich", desc="x", giver="npc:mayor", gold=999)
    assert json.loads(res.stdout)["error"]["code"] == "not_enough"
    # failed transaction must not partially write npc holdings state
    assert not (wroot / "state" / "npcs.yaml").exists()


def test_npc_lazy_seed_from_canon(wroot):
    res = _offer(title="Council Errand", desc="x", giver="npc:mayor", gold=10, items="torch")
    assert res.exit_code == 0, res.stdout
    npcs = _npcs(wroot)
    assert npcs["mayor"]["gold"] == 40          # seeded 50, spent 10
    assert {"item": "torch", "qty": 1} in npcs["mayor"]["inventory"]  # seeded 2, spent 1


def test_unknown_npc_giver_rejected(wroot):
    res = _offer(title="Ghost Giver", desc="x", giver="npc:nobody", gold=1)
    assert json.loads(res.stdout)["error"]["code"] == "unknown_npc"


def test_xp_reward_rejected_for_pc_and_npc_givers(wroot):
    pc = make_pc()
    res = _offer(title="PC XP Quest", desc="x", giver=f"pc:{pc}", xp=10)
    assert json.loads(res.stdout)["error"]["code"] == "no_xp_reward"
    res = _offer(title="NPC XP Quest", desc="x", giver="npc:mayor", xp=10)
    assert json.loads(res.stdout)["error"]["code"] == "no_xp_reward"


def test_spawn_flag_rejected_for_pc_and_npc_givers(wroot):
    pc = make_pc()
    res = _offer(title="PC Spawn Quest", desc="x", giver=f"pc:{pc}", spawn=True)
    assert json.loads(res.stdout)["error"]["code"] == "spawn_world_only"
    res = _offer(title="NPC Spawn Quest", desc="x", giver="npc:mayor", spawn=True)
    assert json.loads(res.stdout)["error"]["code"] == "spawn_world_only"


def test_world_quest_needs_spawn_or_escrow_from(wroot):
    res = _offer(title="No Funding", desc="x", giver="world", gold=5)
    assert json.loads(res.stdout)["error"]["code"] == "no_funding"


def test_unknown_item_rejected_for_spawn_quest(wroot):
    res = _offer(title="Dragon Scale Quest", desc="x", giver="world", spawn=True,
                 items="dragon_scale")
    assert json.loads(res.stdout)["error"]["code"] == "unknown_item"


def test_world_spawn_quest_with_xp_grants_recipients_only(wroot):
    borin = make_pc()
    make_pc(**CLERIC)  # pc-mira, does not accept the quest

    res = _offer(title="Clear the Barrow", desc="seal it up", giver="world",
                 spawn=True, gold=100, items="torch", xp=50)
    assert res.exit_code == 0, res.stdout
    quest_id = json.loads(res.stdout)["id"]

    res = runner.invoke(app, ["quest", "accept", quest_id, "--pcs", borin])
    assert res.exit_code == 0, res.stdout

    res = runner.invoke(app, ["quest", "complete", quest_id])
    assert res.exit_code == 0, res.stdout

    borin_sheet = _sheet(wroot, borin)
    assert borin_sheet["gold"] == 110       # 10 + 100
    assert {"item": "torch", "qty": 1} in borin_sheet["inventory"]
    assert borin_sheet["xp"] == 50

    mira_sheet = _sheet(wroot, "pc-mira")
    assert mira_sheet["gold"] == 15          # unchanged (cleric starting gold)
    assert mira_sheet["xp"] == 0
    assert not any(l["item"] == "torch" for l in mira_sheet["inventory"])

    quest = _quest(wroot, quest_id)
    assert quest["status"] == "completed"
    assert quest["escrow"] == {"gold": 0, "items": []}


def test_complete_splits_gold_with_remainder_to_first(wroot):
    borin = make_pc()
    make_pc(**CLERIC)
    toren = make_pc(name="Toren")

    res = _offer(title="Split Test", desc="x", giver="world", spawn=True, gold=10)
    quest_id = json.loads(res.stdout)["id"]
    runner.invoke(app, ["quest", "accept", quest_id, "--pcs", f"{borin},pc-mira,{toren}"])
    res = runner.invoke(app, ["quest", "complete", quest_id])
    assert res.exit_code == 0, res.stdout

    assert _sheet(wroot, borin)["gold"] == 10 + 4     # remainder to first
    assert _sheet(wroot, "pc-mira")["gold"] == 15 + 3
    assert _sheet(wroot, toren)["gold"] == 10 + 3


def test_cancel_refunds_giver_exactly(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch"])
    res = _offer(title="Errand", desc="x", giver=f"pc:{pc}", gold=3, items="torch")
    quest_id = json.loads(res.stdout)["id"]
    assert _sheet(wroot, pc)["gold"] == 7

    res = runner.invoke(app, ["quest", "cancel", quest_id])
    assert res.exit_code == 0, res.stdout

    sheet = _sheet(wroot, pc)
    assert sheet["gold"] == 10
    assert {"item": "torch", "qty": 1} in sheet["inventory"]
    quest = _quest(wroot, quest_id)
    assert quest["status"] == "cancelled"
    assert quest["escrow"] == {"gold": 0, "items": []}


def test_deadline_in_past_rejected(wroot):
    res = _offer(title="Already Late", desc="x", giver="world", spawn=True,
                 gold=1, deadline="1203-04-01")
    assert json.loads(res.stdout)["error"]["code"] == "bad_deadline"


def test_expiry_via_list_then_accept_errors(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch"])
    res = _offer(title="Short Fuse", desc="x", giver=f"pc:{pc}", gold=2, items="torch",
                 deadline="1203-04-18")
    quest_id = json.loads(res.stdout)["id"]
    assert _sheet(wroot, pc)["gold"] == 8

    clk = worldfs.read_yaml(wroot / "state" / "clock.yaml")
    clk["date"] = "1203-04-19"
    worldfs.write_yaml(wroot / "state" / "clock.yaml", clk)

    res = runner.invoke(app, ["quest", "list"])
    assert res.exit_code == 0, res.stdout
    listed = {q["id"]: q for q in json.loads(res.stdout)["quests"]}
    assert listed[quest_id]["status"] == "expired"

    quest = _quest(wroot, quest_id)
    assert quest["status"] == "expired"
    assert quest["escrow"] == {"gold": 0, "items": []}
    sheet = _sheet(wroot, pc)
    assert sheet["gold"] == 10
    assert {"item": "torch", "qty": 1} in sheet["inventory"]

    res = runner.invoke(app, ["quest", "accept", quest_id, "--pcs", pc])
    assert json.loads(res.stdout)["error"]["code"] == "expired"

    ev = _latest_event(wroot)
    assert ev["type"] == "quest" and "expired" in ev["summary"]


def test_equipped_item_cannot_be_escrowed(wroot):
    pc = make_pc()
    res = _offer(title="Give Away Sword", desc="x", giver=f"pc:{pc}", items="longsword")
    assert json.loads(res.stdout)["error"]["code"] == "equipped"
    sheet = _sheet(wroot, pc)
    assert sheet["gold"] == 10  # untouched


def test_timeline_events_for_offer_accept_complete_cancel(wroot):
    pc = make_pc()

    res = _offer(title="Offer Event", desc="x", giver=f"pc:{pc}", gold=1)
    qid1 = json.loads(res.stdout)["id"]
    ev = _latest_event(wroot)
    assert ev["type"] == "quest" and "offered" in ev["summary"]

    runner.invoke(app, ["quest", "accept", qid1, "--pcs", pc])
    ev = _latest_event(wroot)
    assert ev["type"] == "quest" and "accepted" in ev["summary"]

    runner.invoke(app, ["quest", "complete", qid1])
    ev = _latest_event(wroot)
    assert ev["type"] == "quest" and "completed" in ev["summary"]

    res = _offer(title="Cancel Event", desc="x", giver=f"pc:{pc}", gold=1)
    qid2 = json.loads(res.stdout)["id"]
    runner.invoke(app, ["quest", "cancel", qid2])
    ev = _latest_event(wroot)
    assert ev["type"] == "quest" and "cancelled" in ev["summary"]


def test_world_quest_escrow_from_named_holder(wroot):
    borin = make_pc()
    res = _offer(title="Council Bounty", desc="x", giver="world", gold=20, items="torch",
                 xp=5, escrow_from="npc:mayor")
    assert res.exit_code == 0, res.stdout
    quest_id = json.loads(res.stdout)["id"]

    npcs = _npcs(wroot)
    assert npcs["mayor"]["gold"] == 30
    assert {"item": "torch", "qty": 1} in npcs["mayor"]["inventory"]

    quest = _quest(wroot, quest_id)
    assert quest["giver"] == {"type": "world", "id": None}
    assert quest["escrow_from"] == {"type": "npc", "id": "mayor"}

    runner.invoke(app, ["quest", "accept", quest_id, "--pcs", borin])
    res = runner.invoke(app, ["quest", "complete", quest_id])
    assert res.exit_code == 0, res.stdout

    sheet = _sheet(wroot, borin)
    assert sheet["gold"] == 30       # 10 + 20
    assert {"item": "torch", "qty": 1} in sheet["inventory"]
    assert sheet["xp"] == 5


def test_duplicate_quest_id_rejected(wroot):
    res = _offer(title="One Of A Kind", desc="x", giver="world", spawn=True, gold=1)
    assert res.exit_code == 0, res.stdout
    res = _offer(title="One Of A Kind", desc="x", giver="world", spawn=True, gold=1)
    assert json.loads(res.stdout)["error"]["code"] == "exists"


def test_no_recipients_error_on_complete(wroot):
    res = _offer(title="No Recipients", desc="x", giver="world", spawn=True, gold=5)
    quest_id = json.loads(res.stdout)["id"]
    res = runner.invoke(app, ["quest", "complete", quest_id])
    assert json.loads(res.stdout)["error"]["code"] == "no_recipients"


def test_bad_status_for_complete_and_cancel_after_completion(wroot):
    pc = make_pc()
    res = _offer(title="Bad Status Test", desc="x", giver="world", spawn=True, gold=1)
    quest_id = json.loads(res.stdout)["id"]
    res = runner.invoke(app, ["quest", "complete", quest_id, "--to", pc])
    assert res.exit_code == 0, res.stdout

    res = runner.invoke(app, ["quest", "complete", quest_id, "--to", pc])
    assert json.loads(res.stdout)["error"]["code"] == "bad_status"

    res = runner.invoke(app, ["quest", "cancel", quest_id])
    assert json.loads(res.stdout)["error"]["code"] == "bad_status"


def test_list_filters_by_status(wroot):
    pc = make_pc()
    res = _offer(title="Filter Offered", desc="x", giver="world", spawn=True, gold=1)
    offered_id = json.loads(res.stdout)["id"]
    res = _offer(title="Filter Completed", desc="x", giver="world", spawn=True, gold=1)
    completed_id = json.loads(res.stdout)["id"]
    runner.invoke(app, ["quest", "complete", completed_id, "--to", pc])

    res = runner.invoke(app, ["quest", "list", "--status", "offered"])
    ids = {q["id"] for q in json.loads(res.stdout)["quests"]}
    assert ids == {offered_id}

    res = runner.invoke(app, ["quest", "list", "--status", "completed"])
    ids = {q["id"] for q in json.loads(res.stdout)["quests"]}
    assert ids == {completed_id}


def test_accept_requires_existing_and_living_pc(wroot):
    pc = make_pc()
    res = _offer(title="Accept Checks", desc="x", giver="world", spawn=True, gold=1)
    quest_id = json.loads(res.stdout)["id"]

    res = runner.invoke(app, ["quest", "accept", quest_id, "--pcs", "pc-nobody"])
    assert json.loads(res.stdout)["error"]["code"] == "not_found"

    combat.set_effect(wroot, pc, "dead", -1)
    res = runner.invoke(app, ["quest", "accept", quest_id, "--pcs", pc])
    assert json.loads(res.stdout)["error"]["code"] == "dead"
