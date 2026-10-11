"""T16.10: the plan of a run and gun's stages: chunks of ground the soldier's jump can cross,
the enemies of each on a difficulty curve, a trap, a boss arena, stored in the project and grown
by *Added stages*."""

from __future__ import annotations

import copy
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
