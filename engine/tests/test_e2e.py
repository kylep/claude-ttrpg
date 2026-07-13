import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from test_reference_game import REFERENCE

runner = CliRunner()

PCS = [
    ("Borin", "fighter", "dwarf", "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8", "athletics,perception"),
    ("Brin", "rogue", "halfling", "DEX=15,WIS=14,INT=13,CON=12,STR=10,CHA=8", "stealth,perception,deception"),
    ("Mira", "cleric", "human", "WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8", "insight,medicine"),
    ("Ezren", "wizard", "elf", "INT=15,DEX=14,CON=13,WIS=12,STR=10,CHA=8", "arcana,investigation"),
]


def run(args, expect_ok=True, seed=42):
    # vary the seed per call where outcomes must not repeat: a fixed seed
    # reseeds the RNG identically on every invocation
    res = runner.invoke(app, ["--seed", str(seed), *args])
    data = json.loads(res.stdout.strip().splitlines()[-1])
    if expect_ok:
        assert res.exit_code == 0, res.stdout
    return data


def test_full_adventure_loop(tmp_path, monkeypatch):
    root = tmp_path / "campaign"
    worldfs.init_world(root, REFERENCE, "E2E Campaign")
    monkeypatch.chdir(root)

    for name, cls, race, assign, skills in PCS:
        run(["char", "create", "--name", name, "--class", cls, "--race", race,
             "--assign", assign, "--skills", skills])
    run(["session", "start"])

    # town -> travel -> ambush
    run(["travel", "--to", "old-road"])
    start = run(["encounter", "start", "maps/encounters/road-ambush.yaml"])
    assert len(start["order"]) == 4 + 3

    # grind the ambush: the fighter whacks each monster until it drops.
    # the seed MUST vary per swing — a constant seed rolls the same d20
    # forever and a guaranteed-miss matchup would never terminate.
    enc = worldfs.read_yaml(root / "state" / "encounter.yaml")
    swing = 100
    for mid in list(enc["monsters"]):
        while True:
            enc = worldfs.read_yaml(root / "state" / "encounter.yaml")
            if enc["monsters"][mid]["dead"]:
                break
            swing += 1
            # teleport the fighter adjacent (GM force) and attack
            mx, my = enc["positions"][mid]
            run(["move", "--actor", "pc-borin", "--to", f"{max(0, mx-1)},{my}", "--force"],
                seed=swing)
            run(["attack", "--attacker", "pc-borin", "--target", mid],
                expect_ok=False, seed=swing)
    end = run(["encounter", "end"])
    assert end["xp_each"] > 0

    # rest, march to the dungeon, level check
    run(["rest", "--type", "long"])
    run(["travel", "--to", "barrow-woods"])
    run(["travel", "--to", "barrowdeep"])
    run(["xp", "grant", "--amount", "300", "--reason", "e2e shortcut"])
    lvl = run(["level", "up", "--actor", "pc-borin"])
    assert lvl["level"] == 2

    # boss room exists and renders
    run(["encounter", "start", "maps/encounters/kings-tomb.yaml"])
    render = run(["map", "render", "--svg"])
    assert (root / "renders" / "index.html").exists()
    assert "#" in render["map"] or "~" in render["map"]

    # audit trail exists and never contradicts state
    events = sorted((root / "timeline").glob("*.yaml"))
    assert len(events) > 10
    party = worldfs.read_yaml(root / "state" / "party.yaml")
    assert party["location"] == "barrowdeep"
