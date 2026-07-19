import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def _mk_two(wroot):
    make_pc(name="Borin")
    make_pc(name="Ada", cls="rogue", race="human",
            assign="DEX=15,WIS=14,CON=13,INT=12,STR=10,CHA=8",
            skills="stealth,perception")
    return "pc-borin", "pc-ada"


def _enc(wroot):
    return worldfs.read_yaml(wroot / "state" / "encounter.yaml")


def test_formation_persists_and_validates(wroot):
    a, b = _mk_two(wroot)
    res = runner.invoke(app, ["party", "formation", "--order", f"{b},{a}"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["formation"] == [b, a]
    assert worldfs.read_yaml(worldfs.state(wroot, "party"))["formation"] == [b, a]
    # a non-member is rejected
    res = runner.invoke(app, ["party", "formation", "--order", f"{a},pc-ghost"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "not_found"


def test_combat_seats_pcs_by_formation(wroot):
    a, b = _mk_two(wroot)
    # Ada (b) leads, Borin (a) behind
    runner.invoke(app, ["party", "formation", "--order", f"{b},{a}"])
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    enc = _enc(wroot)
    # skirmish foes sit on the right; the front-most spawn (closest to them) is
    # [2,3], so the front of the formation (Ada) takes it, Borin the next one
    assert enc["positions"][b] == [2, 3]
    assert enc["positions"][a] == [2, 4]


def test_no_formation_keeps_spawn_order(wroot):
    a, b = _mk_two(wroot)
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    enc = _enc(wroot)
    # members order (Borin, Ada) onto the map's file spawn order
    assert enc["positions"][a] == [1, 3]
    assert enc["positions"][b] == [2, 3]
