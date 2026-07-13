import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()

CLERIC = dict(name="Mira", cls="cleric", race="human",
              assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
              skills="insight,medicine")
FIGHTER2 = dict(name="Dorn", cls="fighter", race="dwarf",
                assign="STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8",
                skills="athletics,perception")
CLERIC2 = dict(name="Elin", cls="cleric", race="human",
               assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
               skills="insight,medicine")


def _sheet(wroot, pc):
    return worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")


def _latest_event(wroot):
    path = sorted((wroot / "timeline").glob("*.yaml"))[-1]
    return worldfs.read_yaml(path)


def test_split_travel_moves_only_named_pcs(wroot):
    make_pc()            # pc-borin
    make_pc(**CLERIC)    # pc-mira
    make_pc(**FIGHTER2)  # pc-dorn
    make_pc(**CLERIC2)   # pc-elin

    res = runner.invoke(app, ["travel", "--to", "cave", "--pcs", "pc-borin,pc-mira"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["from"] == "town" and data["to"] == "cave" and data["hours"] == 4

    assert _sheet(wroot, "pc-borin")["location"] == "cave"
    assert _sheet(wroot, "pc-mira")["location"] == "cave"
    assert _sheet(wroot, "pc-dorn")["location"] == "town"
    assert _sheet(wroot, "pc-elin")["location"] == "town"

    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["location"] == "town"  # anchor untouched by a split travel

    ev = _latest_event(wroot)
    assert ev["type"] == "travel"
    assert set(ev["actors"]) == {"pc-borin", "pc-mira"}  # event lists the movers


def test_split_travel_rejects_mismatched_locations(wroot):
    make_pc()          # pc-borin
    make_pc(**CLERIC)  # pc-mira, stays at town
    runner.invoke(app, ["travel", "--to", "cave", "--pcs", "pc-borin"])

    res = runner.invoke(app, ["travel", "--to", "cave", "--pcs", "pc-borin,pc-mira"])
    assert res.exit_code == 1
    err = json.loads(res.stdout)["error"]
    assert err["code"] == "split_party"
    assert "pc-mira" in err["message"]


def test_encounter_subset_participants_and_xp(wroot):
    make_pc()          # pc-borin: joins the fight
    make_pc(**CLERIC)  # pc-mira: stays home

    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml", "--pcs", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert set(enc["order"]) == {"pc-borin", "goblin-1", "goblin-2"}
    assert enc["pcs"] == ["pc-borin"]

    res = runner.invoke(app, ["--seed", "2", "encounter", "end"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["xp_each"] == 100  # 2 goblins * 50 / 1 participant

    assert _sheet(wroot, "pc-borin")["xp"] == 100
    assert _sheet(wroot, "pc-mira")["xp"] == 0  # non-participant untouched


def test_default_encounter_start_skips_dead_pc(wroot):
    make_pc()          # pc-borin: will be dead
    make_pc(**CLERIC)  # pc-mira: alive
    combat.set_effect(wroot, "pc-borin", "dead", -1)

    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert "pc-borin" not in enc["order"]
    assert "pc-borin" not in enc["positions"]
    assert enc["pcs"] == ["pc-mira"]


def test_split_rest_heals_only_named_pcs(wroot):
    make_pc()          # pc-borin
    make_pc(**CLERIC)  # pc-mira
    combat.apply_damage(wroot, "pc-borin", 6, source="test")
    combat.apply_damage(wroot, "pc-mira", 4, source="test")
    mira_before = _sheet(wroot, "pc-mira")["hp"]

    res = runner.invoke(app, ["--seed", "8", "rest", "--type", "short", "--pcs", "pc-borin"])
    assert res.exit_code == 0, res.stdout

    assert _sheet(wroot, "pc-borin")["hp"] > 13 - 6  # healed
    assert _sheet(wroot, "pc-mira")["hp"] == mira_before  # untouched


def test_pc_without_location_key_falls_back_to_party_location(wroot):
    make_pc()  # pc-borin, location "town" set explicitly at creation
    sheet = _sheet(wroot, "pc-borin")
    assert sheet["location"] == "town"
    del sheet["location"]
    worldfs.write_yaml(wroot / "state" / "party" / "pc-borin.yaml", sheet)

    res = runner.invoke(app, ["travel", "--to", "cave", "--pcs", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["from"] == "town" and data["to"] == "cave"
    assert _sheet(wroot, "pc-borin")["location"] == "cave"
