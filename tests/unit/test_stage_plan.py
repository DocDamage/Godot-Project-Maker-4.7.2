"""T16.10: the plan of a run and gun's stages: chunks of ground the soldier's jump can cross,
the enemies of each on a difficulty curve, a trap, a boss arena, stored in the project and grown
by *Added stages*."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

from rpggen import jsonio, schema
from rpggen.core import config, options, room_plan, stage_plan, world_plan

FACTS = {"view": [640, 360], "tile": 16}


def test_the_plan_is_the_same_for_the_same_seed_and_fits_the_schema() -> None:
    one = stage_plan.plan({}, 12345, FACTS)
    assert one == stage_plan.plan({}, 12345, FACTS)
    assert one != stage_plan.plan({}, 12346, FACTS)
    assert stage_plan.check(one) == [] and one["notes"] == []
    schema.validate("world_plan", stage_plan.world(one, 12345))
    assert stage_plan.summary(one) == "3 stages, 3 bosses, seen from the side"
    assert (one["kind"], one["chunk_cols"], one["rows"]) == ("run_and_gun", 20, 23)
    first = one["list"][0]
    assert first["scene"] == "res://generated/scenes/stages/stage_01.tscn"
    assert (first["axis"], first["speed"], first["exit"]) == ("right", 0.0, "reach_end")
    chunks = first["chunks"]
    assert len(chunks) == 3 + 9 + 2, "the start, a medium stage of nine chunks, the arena"
    assert chunks[:3] == ["flat"] * 3 and chunks[-2:] == ["arena"] * 2
    assert chunks.count("trap") == 1 and chunks[chunks.index("trap") - 1] == "flat"
    assert set(chunks) <= {*stage_plan.FEATURES, "trap", "arena"}
    tiles = first["tiles"]
    assert len(tiles) == 23 and {len(row) for row in tiles} == {14 * 20}
    assert set("".join(tiles)) <= set("#.=^"), "the alphabet of the room plan"
    assert first["length"] == 14 * 20 * 16 - 640, "the camera stops with the arena on the screen"
    assert first["start"] == [56.0, 20 * 16.0], "on the floor, in the first chunk"
    assert tiles[20][:60] == "#" * 60 and tiles[19][:60] == "." * 60, "the start is flat"
    assert tiles[20][-40:] == "#" * 40 and tiles[19][-40:] == "." * 40, "and so is the arena"


def test_every_stage_can_be_walked_and_a_gap_wider_than_a_jump_cannot() -> None:
    # the soldier's reach is the room plan's: the numbers the platform actor moves by
    assert stage_plan.JUMP_UP == int(room_plan.vertical_reach(())) == 3
    assert stage_plan.JUMP_ACROSS == int(room_plan.horizontal_reach(())) == 4
    floor = ["." * 12] * 4 + ["#" * 12] * 2
    assert stage_plan.walk(floor) == []

    def with_gap(width: int, landing_up: int = 0) -> list[str]:
        rows = [list("." * 12) for _ in range(4)] + [list("#" * 12) for _ in range(2)]
        for x in range(3, 3 + width):
            rows[4][x] = rows[5][x] = "."
        for x in range(3 + width, 12):
            for up in range(landing_up):
                rows[3 - up][x] = "#"
        return ["".join(r) for r in rows]

    assert stage_plan.walk(with_gap(4)) == [], "four tiles: the widest jump"
    (problem,) = stage_plan.walk(with_gap(5))
    assert problem == "column 3: a gap of 5 tiles (a jump crosses 4)"
    assert stage_plan.walk(with_gap(3, landing_up=2)) == [], "three across and two up"
    (problem,) = stage_plan.walk(with_gap(4, landing_up=1))
    assert "a gap of 4 tiles up 1 (a jump crosses 3)" in problem, "a rise costs a tile of reach"
    step = ["." * 6] * 4 + ["#" * 6] * 2
    step[0] = step[1] = step[2] = step[3] = "...###"
    (problem,) = stage_plan.walk(step)
    assert problem == "column 3: a step of 4 tiles (a jump rises 3)"
    step[0] = "......"
    assert stage_plan.walk(step) == [], "three tiles up is a jump"
    edge = ["......", "###..."]
    assert stage_plan.walk(edge) == ["column 3: the ground ends and does not begin again"]
    planks = ["......", "..==..", "......", "######"]
    assert stage_plan.walk(planks) == [], "a plank is something to stand on, not a wall"
    # in a whole plan the check names the stage
    plan = stage_plan.plan({}, 5, FACTS)
    broken = copy.deepcopy(plan)
    rows = [list(r) for r in broken["list"][1]["tiles"]]
    for y in range(20, 23):
        for x in range(100, 106):
            rows[y][x] = "."
    for y in range(0, 20):  # and nothing above to stand on
        for x in range(100, 106):
            rows[y][x] = "."
    broken["list"][1]["tiles"] = ["".join(r) for r in rows]
    found = stage_plan.check(broken)
    assert len(found) == 1 and found[0].startswith("stage_02: column 100: a gap of 6 tiles")
    late = copy.deepcopy(plan)
    late["list"][0]["waves"][-1]["at"] = late["list"][0]["length"] + 1
    assert stage_plan.check(late)[0].endswith("comes after the stage has ended")
    loud = copy.deepcopy(plan)
    loud["list"][2]["boss"]["phases"][0].update({"count": 300, "interval": 0.3})
    assert "bullets of the boss at once" in stage_plan.check(loud)[0]
    # every plan the options can make passes, at every seed that was tried
    for seed in range(40):
        for difficulty in stage_plan.DIFFICULTIES:
            for length in stage_plan.LENGTHS:
                made = stage_plan.plan(
                    {"difficulty": difficulty, "stages": 4, "length": length}, seed, FACTS
                )
                assert stage_plan.check(made) == [] and made["notes"] == [], (seed, length)


def test_the_enemies_of_a_stage_stand_on_its_ground_and_difficulty_rises() -> None:
    made = stage_plan.plan({"stages": 6, "length": "long"}, 7, FACTS)
    threats = [w["threat"] for s in made["list"] for w in s["waves"]]
    assert threats == sorted(threats), "never easier than the wave before"
    fast = [w["fast"] for s in made["list"] for w in s["waves"]]
    tough = [w["tough"] for s in made["list"] for w in s["waves"]]
    assert fast == sorted(fast) and tough == sorted(tough) and fast[-1] > fast[0]
    health = [s["boss"]["health"] for s in made["list"]]
    assert health == sorted(health) and len(set(health)) == 6, "every boss tougher than the last"
    assert [len(s["boss"]["phases"]) for s in made["list"]] == [2, 3, 4, 4, 4, 4]
    kinds = {s["boss"]["kind"] for s in made["list"]}
    assert kinds == set(stage_plan.BOSSES), "the wall, the walker and the flyer all come"
    for stage in made["list"]:
        tops = stage_plan.ground(stage["tiles"])
        planks = [
            {y for y, row in enumerate(stage["tiles"]) if row[x] == "="} for x in range(len(tops))
        ]
        assert [w["at"] for w in stage["waves"]] == sorted(w["at"] for w in stage["waves"])
        (trap,) = [w for w in stage["waves"] if w.get("blocking")]
        assert (trap["enemy"], trap["count"]) == ("turret", 2)
        assert stage["chunks"][trap["chunk"]] == "trap"
        assert 0.6 * 640 < trap["position"][0] - trap["at"] < 0.85 * 640, "on the screen it stops"
        assert not [w for w in stage["waves"] if w["chunk"] < stage_plan.START_CHUNKS]
        assert [w for w in stage["waves"] if w["enemy"] == "pickup"], "weapons on their carriers"
        for wave in stage["waves"]:
            assert wave["at"] <= stage["length"] and wave["anchor"] == "stage"
            if wave["enemy"] in ("pickup", "wall_cannon"):
                continue
            # what walks stands on ground or on a plank, every one of the wave
            first = wave["position"][0] - (wave["count"] - 1) * wave["gap"] * 0.5
            row = int(wave["position"][1] // 16)
            for n in range(wave["count"]):
                x = int((first + n * wave["gap"]) // 16)
                assert tops[x] == row or row in planks[x], (stage["id"], wave["id"], x, row)
            if wave["enemy"] != "turret":
                assert wave["position"][0] - wave["at"] > 640 * 0.7, "it comes from ahead"
        boss = stage["boss"]
        floor_y = 20 * 16 - 180
        assert boss["position"][1] == (floor_y if boss["kind"] != "flyer" else floor_y - 112)
        assert 0 < boss["position"][0] < 320, "in the right half of the arena"
    # the first stage starts with runners only; later the others join
    early = {w["enemy"] for w in made["list"][0]["waves"][:2]}
    assert early <= {"runner", "wall_cannon", "pickup"}
    everyone = {w["enemy"] for s in made["list"] for w in s["waves"]}
    assert everyone == {"runner", "jumper", "sniper", "turret", "wall_cannon", "pickup"}
    easy = stage_plan.plan({"difficulty": "easy"}, 7, FACTS)["list"][0]
    hard = stage_plan.plan({"difficulty": "hard"}, 7, FACTS)["list"][0]
    assert easy["waves"][0]["fast"] < hard["waves"][0]["fast"]
    assert easy["boss"]["health"] < hard["boss"]["health"]


def test_the_options_and_what_is_wrong_with_them() -> None:
    assert stage_plan.defaults() == {
        "stages": 3,
        "length": "medium",
        "lives": 3,
        "health": 1,
        "keep_weapon": False,
        "left_edge_kills": True,
        "difficulty": "normal",
        "added_stages": [],
        "grapple": False,
        "jump": True,
    }
    assert config.starter_map_defaults("run_and_gun") == stage_plan.defaults()
    for name, chunks in stage_plan.LENGTHS.items():
        (stage,) = stage_plan.plan({"length": name, "stages": 1}, 1, FACTS)["list"]
        assert len(stage["chunks"]) == 3 + chunks + 2
    assert stage_plan.describe({"stages": 5, "added_stages": [{"name": "Extra"}]}) == (
        "6 stages, seen from the side"
    )
    assert options.stages_text("run_and_gun", {}) == "3 stages, seen from the side"
    assert options.stages_text("run_and_gun", {"stages": 99}) == ""
    for bad, word in (
        ({"stages": 0}, "stages"),
        ({"health": 6}, "health"),
        ({"lives": True}, "lives"),
        ({"length": "endless"}, "length"),
        ({"difficulty": "brutal"}, "difficulty"),
        ({"keep_weapon": "yes"}, "keep_weapon"),
        ({"grapple": 1}, "grapple"),
        ({"jump": False}, "jump can be off only when grapple is on"),
        ({"orientation": "vertical"}, "unknown option"),
        ({"added_stages": [{"name": "A"}, {"name": "a"}]}, "two added stages"),
    ):
        with pytest.raises(stage_plan.StagePlanError, match=word):
            stage_plan.plan(bad, 1, FACTS)
    ref = config.PackRef("p", "p", "0" * 64, "folder")
    cfg = config.default_for("S", [ref], archetype="run_and_gun")
    cfg.starter_map = {"stages": 5, "length": "long", "health": 3, "keep_weapon": True}
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["starter_map"]["left_edge_kills"] is True and data["starter_map"]["stages"] == 5
    assert config.GeneratorConfig.from_json(data).to_json() == data


def test_added_stages_grow_the_plan_and_a_project_keeps_what_it_stored(tmp_path: Path) -> None:
    stored = stage_plan.plan({}, 5, FACTS)
    more, added = stage_plan.extend(stored, [{"name": "The Docks"}], 5)
    assert added == ["The Docks"] and len(more["list"]) == 4
    assert more["list"][:3] == stored["list"]
    last = more["list"][3]
    assert (last["id"], last["title"], last["level"]) == ("stage_04", "The Docks", 3)
    assert last["boss"]["health"] > stored["list"][2]["boss"]["health"]
    assert stage_plan.check(more) == []
    again, nothing = stage_plan.extend(more, [{"name": "the docks"}], 5)
    assert nothing == [] and again == more
    project = tmp_path / "game"
    plan, notes = stage_plan.for_project(project, {}, 5, FACTS)
    assert notes == [] and plan["stages"] == stored
    world_plan.save(project, plan)
    assert not stage_plan.exists(project)
    (project / "game/data").mkdir(parents=True)
    jsonio.write(project / stage_plan.STAGES_FILE, {"stages": []})
    kept, notes = stage_plan.for_project(project, {"stages": 1, "difficulty": "hard"}, 99, FACTS)
    assert kept["stages"] == stored and notes == [], "never planned again"
    grown, notes = stage_plan.for_project(project, {"added_stages": [{"name": "Bonus"}]}, 5, FACTS)
    assert notes == ["The run kept its plan; added: Bonus."]
    assert len(grown["stages"]["list"]) == 4
    world_plan.save(project, grown)
    assert world_plan.load(project)["stages"]["kind"] == "run_and_gun"


# --------------------------------------------------------------------------- the grapple (T16.11)

BIONIC = {"grapple": True, "jump": False}


def _flat(width: int = 30) -> list[list[str]]:
    """Twelve rows: nine of air and three of ground (its top is row 9)."""
    return [list("." * width) for _ in range(9)] + [list("#" * width) for _ in range(3)]


def _rows(grid: list[list[str]]) -> list[str]:
    return ["".join(row) for row in grid]


def test_the_pendulum_is_the_one_the_runtime_steps() -> None:
    # the numbers of the platform actor at 16 px tiles: test_grapple.gd has the same period
    gravity = 2 * room_plan.JUMP_TILES * 16 / room_plan.TIME_TO_PEAK**2
    period = stage_plan.swing_period(64.0, gravity, math.pi / 4)
    assert period == pytest.approx(1.947866, abs=1e-6)
    assert period > math.tau * math.sqrt(64.0 / gravity), "a wide swing takes longer"
    assert stage_plan.swing_period(64.0, gravity, 1e-6) == pytest.approx(
        math.tau * math.sqrt(64.0 / gravity)
    )
    for hertz in (30, 60, 120):
        stepped = stage_plan.simulate_swing(64.0, gravity, math.pi / 4, 1 / hertz)
        assert stepped == pytest.approx(period, rel=0.01), hertz
    assert stage_plan.swing_period(0.0, gravity, 1.0) == 0.0


def test_a_plan_without_jumping_has_a_swing_point_over_every_gap() -> None:
    assert stage_plan.PRESETS["bionic"] == BIONIC
    for seed in range(40):
        for length in stage_plan.LENGTHS:
            plan = stage_plan.plan({**BIONIC, "length": length}, seed, FACTS)
            assert plan["seed"] == seed, "no plan of the options has to be planned again"
            assert (plan["grapple"], plan["jump"]) == (True, False)
            assert stage_plan.check(plan) == [] and stage_plan.check_grapple(plan) == []
            schema.validate("world_plan", stage_plan.world(plan, seed))
            for stage in plan["list"]:
                tiles = stage["tiles"]
                tops = stage_plan.ground(tiles)
                floor = stage_plan.floor_row(plan["rows"])
                x = 0
                while x < len(tops):
                    if stage_plan._standable(tiles, tops, x):
                        x += 1
                        continue
                    end = x
                    while not stage_plan._standable(tiles, tops, end):
                        end += 1
                    hook = stage_plan.swing_point(tiles, x, end - 1, floor)
                    assert hook is not None, (seed, stage["id"], x)
                    assert x - 2 <= hook[0] <= end + 2, "the hook holds over the gap"
                    assert tiles[int(hook[1]) - 1][int(hook[0])] == "#", "on a block"
                    reach = (floor - stage_plan.HAND - hook[1]) * math.sqrt(2.0)
                    assert reach <= stage_plan.GRAPPLE_REACH
                    x = end
                # what is higher has a plank to be hoisted on to
                for x in range(len(tops) - 1):
                    here, nxt = tops[x], tops[x + 1]
                    both = stage_plan._standable(tiles, tops, x) and stage_plan._standable(
                        tiles, tops, x + 1
                    )
                    if both and nxt < here:  # type: ignore[operator]
                        assert tiles[nxt][x] == "=", (seed, stage["id"], x)
                # and the enemies still stand on ground
                for wave in stage["waves"]:
                    if wave["enemy"] in ("runner", "jumper", "turret"):
                        col = int(wave["position"][0] // 16)
                        assert tops[col] == wave["position"][1] // 16, (seed, wave)
    kinds = {
        kind
        for seed in range(10)
        for stage in stage_plan.plan(BIONIC, seed, FACTS)["list"]
        for kind in stage["chunks"]
    }
    assert kinds >= {"gap", "spikes", "step", "wall", "planks"}, "the same features, for the arm"
    # a plan with jumping is what it was before the grapple: no block in the air
    plain = stage_plan.plan({}, 3, FACTS)
    assert (plain["grapple"], plain["jump"]) == (False, True)
    assert stage_plan.check_grapple(plain) == []
    assert stage_plan.plan({"grapple": True}, 3, FACTS)["list"] == plain["list"]
    for stage in plain["list"]:
        floor = stage_plan.floor_row(plain["rows"])
        assert all("#" not in row for row in stage["tiles"][: floor - 3])


def test_a_stage_with_nothing_to_swing_from_is_val_030() -> None:
    from rpggen.errors_table import CODES

    assert CODES["VAL-030"].severity == "warning"
    assert stage_plan.climb(_rows(_flat())) == []
    # a gap of three tiles and nothing over it
    gap = _flat()
    for x in (14, 15, 16):
        for y in (9, 10, 11):
            gap[y][x] = "."
    (problem,) = stage_plan.climb(_rows(gap))
    assert "column 14" in problem and "nothing above them to swing from" in problem
    assert stage_plan.walk(_rows(gap)) == [], "a soldier that jumps crosses it"
    # a block five tiles over it: the hook holds, the swing ends over the far side
    for x in (13, 14, 15, 16, 17):
        gap[3][x] = "#"
    assert stage_plan.climb(_rows(gap)) == []
    hook = stage_plan.swing_point(_rows(gap), 14, 16, 9)
    assert hook is not None and hook[1] == 4.0
    # too high for the hook, and it is no swing point
    high = _flat()
    high = [list("." * 30) for _ in range(6)] + high
    for x in (14, 15, 16):
        for y in (15, 16, 17):
            high[y][x] = "."
    for x in (13, 14, 15, 16, 17):
        high[0][x] = "#"
    assert len(stage_plan.climb(_rows(high))) == 1
    # a wider gap than the swing carries over
    wide = _flat()
    for x in range(12, 20):
        for y in (9, 10, 11):
            wide[y][x] = "."
    for x in (13, 14, 15):
        wide[3][x] = "#"
    assert len(stage_plan.climb(_rows(wide))) == 1
    # spikes are not walked either
    spikes = _flat()
    spikes[8][15] = "^"
    (problem,) = stage_plan.climb(_rows(spikes))
    assert "1 tiles that cannot be walked" in problem
    # a step needs a plank that reaches out from it
    step = _flat()
    for x in range(15, 30):
        step[8][x] = step[7][x] = "#"
    (problem,) = stage_plan.climb(_rows(step))
    assert "a step of 2 tiles and no plank" in problem
    step[7][14] = step[7][13] = "="
    assert stage_plan.climb(_rows(step)) == []
    # the whole plan: a plan made for jumping, played without it
    plain = stage_plan.plan({}, 3, FACTS)
    assert stage_plan.check_grapple(plain) == []
    problems = stage_plan.check_grapple(plain, jump=False)
    assert problems and all(p.startswith("stage_0") for p in problems)
    assert stage_plan.check_grapple(stage_plan.plan(BIONIC, 3, FACTS), jump=True) == []


def test_the_grapple_options_are_kept_by_the_config_and_the_stored_plan(tmp_path: Path) -> None:
    assert (
        stage_plan.describe(BIONIC) == "3 stages, seen from the side, with the grapple and no jump"
    )
    assert stage_plan.describe({"grapple": True}).endswith("with the grapple")
    ref = config.PackRef("p", "p", "0" * 64, "folder")
    cfg = config.default_for("S", [ref], archetype="run_and_gun")
    cfg.starter_map = dict(BIONIC)
    data = cfg.to_json()
    schema.validate("config", data)
    assert (data["starter_map"]["grapple"], data["starter_map"]["jump"]) == (True, False)
    assert config.GeneratorConfig.from_json(data).to_json() == data
    assert config.default_input("run_and_gun")["grapple"] == {
        "keys": ["L", "V"],
        "joy_buttons": [1],
    }
    # an added stage of a stored plan is for the arm too
    stored = stage_plan.plan({**BIONIC, "stages": 1, "length": "short"}, 4, FACTS)
    grown, added = stage_plan.extend(stored, [{"name": "The Tower"}], 4)
    assert added == ["The Tower"] and stage_plan.check_grapple(grown) == []
    assert grown["jump"] is False and len(grown["list"]) == 2
