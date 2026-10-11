"""T16.06: the plan of a shoot 'em up's stages: the same for the same seed, harder from wave to
wave and from stage to stage, checked against a budget, stored in the project and grown by
*Added stages*."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import jsonio, schema
from rpggen.core import config, options, wave_plan, world_plan
from rpggen.errors import CODES

FACTS = {"view": [640, 360], "tile": 16}


def test_the_plan_is_the_same_for_the_same_seed_and_fits_the_schema() -> None:
    one = wave_plan.plan({}, 12345, FACTS)
    assert one == wave_plan.plan({}, 12345, FACTS)
    assert one != wave_plan.plan({}, 12346, FACTS)
    assert wave_plan.check(one) == [] and one["notes"] == []
    schema.validate("world_plan", wave_plan.world(one, 12345))
    assert wave_plan.summary(one) == "3 stages, 3 bosses, scrolling up"
    assert [s["id"] for s in one["list"]] == ["stage_01", "stage_02", "stage_03"]
    first = one["list"][0]
    assert first["scene"] == "res://generated/scenes/stages/stage_01.tscn"
    assert (first["axis"], first["exit"], first["speed"]) == ("up", "reach_end", 40.0)
    assert first["length"] == 6 * 360, "a medium stage is six screens long"
    assert len(first["waves"]) == 10 and [w["id"] for w in first["waves"]][:2] == ["w01", "w02"]
    kinds = [w["enemy"] for w in first["waves"]]
    assert kinds[5] == "carrier" and kinds.count("carrier") == 1, "a carrier in the middle"
    assert set(kinds) <= {"popcorn", "turret", "asteroid", "carrier"}
    assert [w["at"] for w in first["waves"]] == sorted(w["at"] for w in first["waves"])
    for wave in first["waves"]:
        assert wave["trigger"] == "progress" and wave["count"] >= 1
        if wave["enemy"] in ("turret", "asteroid"):
            assert wave["anchor"] == "stage", "what sits on the background is placed in the stage"
        else:
            assert wave["position"][1] == -(180 + 24), "just beyond the top of the screen"
        if wave["enemy"] == "popcorn":
            assert wave["formation"] in wave_plan.FORMATIONS and wave["bonus"] == 500
    sideways = wave_plan.plan({"orientation": "horizontal"}, 12345, FACTS)
    assert sideways["list"][0]["axis"] == "right" and sideways["list"][0]["length"] == 6 * 640
    assert sideways["list"][0]["waves"][0]["position"][0] == 320 + 24, "beyond the right edge"
    assert wave_plan.summary(sideways).endswith("scrolling right")


def test_the_length_and_the_number_of_stages_come_from_the_options() -> None:
    for name, screens in wave_plan.LENGTHS.items():
        made = wave_plan.plan({"length": name, "stages": 1}, 1, FACTS)
        (stage,) = made["list"]
        assert stage["length"] == screens * 360
        assert len(stage["waves"]) == screens * 2 - 2
        assert stage["waves"][-1]["at"] < stage["length"] - 180, "the last screen is the boss's"
    assert len(wave_plan.plan({"stages": 8}, 1, FACTS)["list"]) == 8
    assert wave_plan.describe({"stages": 5, "added_stages": [{"name": "Extra"}]}) == (
        "6 stages, scrolling up"
    )
    for bad, word in (
        ({"stages": 0}, "stages"),
        ({"stages": 9}, "stages"),
        ({"stages": True}, "stages"),
        ({"length": "endless"}, "length"),
        ({"difficulty": "brutal"}, "difficulty"),
        ({"orientation": "diagonal"}, "orientation"),
        ({"lives": 0}, "lives"),
        ({"bombs": 10}, "bombs"),
        ({"auto_fire": "yes"}, "auto_fire"),
        ({"rooms": 3}, "unknown option"),
        ({"added_stages": [{"name": " "}]}, "needs a name"),
        ({"added_stages": [{"name": "A"}, {"name": "a"}]}, "two added stages"),
    ):
        with pytest.raises(wave_plan.WavePlanError, match=word):
            wave_plan.plan(bad, 1, FACTS)


def test_difficulty_rises_along_a_stage_and_from_stage_to_stage() -> None:
    made = wave_plan.plan({"stages": 8, "length": "long"}, 7, FACTS)
    threats = [w["threat"] for s in made["list"] for w in s["waves"]]
    assert threats == sorted(threats), "never easier than the wave before"
    assert threats[0] == 0 and threats[-1] == 8 * wave_plan.THREAT_PER_STAGE
    fast = [w["fast"] for s in made["list"] for w in s["waves"]]
    tough = [w["tough"] for s in made["list"] for w in s["waves"]]
    assert fast == sorted(fast) and tough == sorted(tough)
    assert fast[-1] > fast[0] and tough[-1] > tough[0]
    counts = [w["count"] for s in made["list"] for w in s["waves"] if w["enemy"] == "popcorn"]
    assert counts == sorted(counts) and counts[0] == 4 and counts[-1] == 8
    fans = [w["fan"] for s in made["list"] for w in s["waves"] if w["enemy"] == "turret"]
    assert fans == sorted(fans) and fans[-1] > fans[0]
    bosses = [s["boss"] for s in made["list"]]
    health = [b["health"] for b in bosses]
    assert health == sorted(health) and len(set(health)) == 8, "every boss tougher than the last"
    assert [len(b["phases"]) for b in bosses] == [2, 3, 4, 4, 4, 4, 4, 4], "two to four phases"
    assert [b["points"] for b in bosses][:3] == [5000, 10000, 15000]
    for boss in bosses:
        untils = [p["until"] for p in boss["phases"]]
        assert untils == sorted(untils, reverse=True) and untils[-1] == 0.0
        patterns = [p["attacks"][0] for p in boss["phases"]]
        assert len(set(patterns)) == len(patterns) and set(patterns) <= set(wave_plan.BOSS_PATTERNS)
    # the setting: easy has slower and fewer bullets and a weaker boss than hard
    easy = wave_plan.plan({"difficulty": "easy"}, 7, FACTS)["list"][0]
    hard = wave_plan.plan({"difficulty": "hard"}, 7, FACTS)["list"][0]
    assert easy["waves"][0]["fast"] < hard["waves"][0]["fast"]
    assert easy["boss"]["health"] < hard["boss"]["health"]
    assert easy["boss"]["phases"][0]["count"] <= hard["boss"]["phases"][0]["count"]
    assert wave_plan.hardness(0, "easy")["fan"] < wave_plan.hardness(0, "hard")["fan"]


def test_the_budget_rejects_a_plan_that_cannot_be_finished() -> None:
    good = wave_plan.plan({}, 3, FACTS)
    swamped = copy.deepcopy(good)
    for wave in swamped["list"][1]["waves"]:
        wave.update({"enemy": "turret", "count": 8, "fan": 40})
    (problem,) = wave_plan.check(swamped)
    assert problem.startswith("stage_02: up to ") and "bullets at once" in problem
    late = copy.deepcopy(good)
    late["list"][0]["waves"][-1]["at"] = late["list"][0]["length"]
    assert wave_plan.check(late) == ["stage_01: wave w10 comes after the stage has ended"]
    wall = copy.deepcopy(good)
    wall["list"][2]["boss"]["phases"][0].update({"count": 200, "interval": 0.5})
    assert [p.split(":")[0] for p in wave_plan.check(wall)] == ["stage_03"]
    empty = copy.deepcopy(good)
    empty["list"][0].update({"waves": [], "boss": {}})
    assert wave_plan.check(empty) == ["stage_01: no wave and no boss"]
    # every plan the options can make passes, at every seed that was tried
    for seed in range(40):
        for difficulty in wave_plan.DIFFICULTIES:
            made = wave_plan.plan(
                {"difficulty": difficulty, "stages": 8, "length": "long"}, seed, FACTS
            )
            assert wave_plan.check(made) == [], (seed, difficulty)
    assert CODES["VAL-029"].severity == "warning"


def test_a_plan_that_fails_is_planned_again_with_the_next_seed(monkeypatch) -> None:
    real = wave_plan.check
    monkeypatch.setattr(
        wave_plan, "check", lambda stages: ["stage_01: no"] if stages["seed"] < 12 else real(stages)
    )
    made = wave_plan.plan({}, 10, FACTS)
    assert made["seed"] == 12
    assert made["notes"] == [
        "The stages were planned with seed 12: the plan of seed 10 could not be finished."
    ]
    monkeypatch.setattr(wave_plan, "check", lambda stages: ["stage_01: never"])
    with pytest.raises(wave_plan.WavePlanError, match="no plan that can be finished"):
        wave_plan.plan({}, 10, FACTS)


def test_added_stages_grow_the_plan_by_one_and_leave_the_rest(tmp_path: Path) -> None:
    stored = wave_plan.plan({}, 5, FACTS)
    more, added = wave_plan.extend(stored, [{"name": "Asteroid Belt"}], 5)
    assert added == ["Asteroid Belt"] and len(more["list"]) == 4
    assert more["list"][:3] == stored["list"], "the stages it had are what they were"
    last = more["list"][3]
    assert (last["id"], last["title"], last["level"]) == ("stage_04", "Asteroid Belt", 3)
    assert last["boss"]["health"] > stored["list"][2]["boss"]["health"], "harder than the last"
    assert more["added"] == ["Asteroid Belt"] and wave_plan.check(more) == []
    again, nothing = wave_plan.extend(more, [{"name": "asteroid belt"}], 5)
    assert nothing == [] and again == more, "a stage is added once"
    # in a project: the plan is stored, kept on the next run, and only grows
    project = tmp_path / "game"
    plan, notes = wave_plan.for_project(project, {}, 5, FACTS)
    assert notes == [] and plan["stages"] == stored
    world_plan.save(project, plan)
    assert not wave_plan.exists(project), "no list of stages yet: nothing was built"
    fresh, _ = wave_plan.for_project(project, {"stages": 2}, 99, FACTS)
    assert len(fresh["stages"]["list"]) == 2, "until the game has its stages the options count"
    (project / "game/data").mkdir(parents=True)
    jsonio.write(project / wave_plan.STAGES_FILE, {"stages": []})
    assert wave_plan.exists(project)
    kept, notes = wave_plan.for_project(project, {"stages": 2, "difficulty": "hard"}, 99, FACTS)
    assert kept["stages"] == stored and notes == [], "never planned again"
    grown, notes = wave_plan.for_project(project, {"added_stages": [{"name": "Bonus"}]}, 5, FACTS)
    assert notes == ["The run kept its plan; added: Bonus."]
    assert [s["id"] for s in grown["stages"]["list"]] == [f"stage_0{n}" for n in (1, 2, 3, 4)]
    world_plan.save(project, grown)
    assert world_plan.load(project)["stages"]["added"] == ["Bonus"]
    with pytest.raises(wave_plan.WavePlanError, match="12 stages at most"):
        full = wave_plan.plan({"stages": 8}, 1, FACTS)
        wave_plan.extend(full, [{"name": f"S{n}"} for n in range(8)], 1)


def test_the_options_of_a_shoot_em_up_in_the_config() -> None:
    assert config.starter_map_defaults("shmup") == wave_plan.defaults()
    ref = config.PackRef("p", "p", "0" * 64, "folder")
    cfg = config.default_for("S", [ref], archetype="shmup")
    cfg.starter_map = {"stages": 5, "length": "long", "lives": 5, "bombs": 1, "auto_fire": False,
                       "difficulty": "hard", "added_stages": [{"name": "Extra"}]}  # fmt: skip
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["starter_map"]["orientation"] == "vertical" and data["starter_map"]["stages"] == 5
    assert config.GeneratorConfig.from_json(data).to_json() == data
    for bad in ({"stages": 9}, {"lives": 0}, {"difficulty": "x"}, {"added_stages": [{}]}):
        with pytest.raises(Exception):  # noqa: B017, PT011
            schema.validate("config", {**data, "starter_map": bad})
    text = options.stages_text("shmup", cfg.starter_map_options())
    assert text == "6 stages, scrolling up"
    assert options.stages_text("shmup", {"stages": 99}) == "", "options that make no plan"
