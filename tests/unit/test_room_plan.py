"""T14.06: the rooms of a metroidvania: the plan, its bounds, the stored plan and extending it."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from rpggen import jsonio, schema
from rpggen.core import config, lockkey, room_plan, world_plan
from rpggen.errors import RpgGenError

ALL = list(room_plan.ABILITIES)
PACK = config.PackRef("cave", "/packs/cave", "0" * 64, "folder")


def _plan(rooms: int = 6, abilities: list[str] | None = None, seed: int = 12345, **more: Any):
    options = {
        "rooms": rooms,
        "abilities": ["double_jump", "dash"] if abilities is None else abilities,
    }
    return room_plan.plan({**options, **more}, seed)


def _room(plan: dict[str, Any], ident: str) -> dict[str, Any]:
    found = room_plan.room_of(plan, ident)
    assert found is not None
    return found


def _at(room: dict[str, Any], cell: list[int]) -> str:
    return room["tiles"][cell[1]][cell[0]]


# --------------------------------------------------------------------------- options


def test_the_defaults_are_the_archetypes_starter_world() -> None:
    assert room_plan.defaults() == {
        "rooms": 6,
        "room_size": [40, 23],
        "abilities": ["double_jump", "dash"],
        "enemies": 2,
        "pickups": 4,
    }
    assert config.starter_map_defaults("metroidvania") == room_plan.defaults()
    assert "rooms" not in config.starter_map_defaults("turn_based")
    assert "rooms" not in config.starter_map_defaults("arpg")
    cfg = config.default_for("Cave", [PACK], archetype="metroidvania")
    assert "starter_map" not in cfg.to_json(), "the defaults are left out of the file"
    cfg.starter_map = {"rooms": 8, "abilities": ["dash"], "pickups": 0}
    again = config.GeneratorConfig.from_json(cfg.to_json())
    assert again.starter_map_options() == {
        "rooms": 8, "room_size": [40, 23], "abilities": ["dash"], "enemies": 2, "pickups": 0,
    }  # fmt: skip
    schema.validate("config", cfg.to_json())


def test_normalized_orders_the_abilities_and_checks_every_bound() -> None:
    opts = room_plan.normalized({"abilities": ["dash", "double_jump"], "rooms": 5})
    assert opts["abilities"] == ["double_jump", "dash"], "the table's order"
    assert room_plan.normalized(None) == room_plan.defaults()
    bad: list[dict[str, Any]] = [
        {"rooms": 4},
        {"rooms": 13},
        {"rooms": True},
        {"abilities": ["fly"]},
        {"abilities": ["dash", "dash"]},
        {"abilities": "dash"},
        {"room_size": [20, 23]},
        {"room_size": [40, 10]},
        {"room_size": [40]},
        {"enemies": 5},
        {"pickups": -1},
        {"added_rooms": [{"join": "Room 1"}]},
        {"added_rooms": "x"},
    ]
    for options in bad:
        with pytest.raises(room_plan.RoomPlanError):
            room_plan.normalized(options)


@pytest.mark.parametrize("count", range(6))
def test_rooms_must_be_at_least_abilities_plus_three(count: int) -> None:
    abilities = ALL[:count]
    least = max(5, count + 3)
    assert room_plan.min_rooms(abilities) == least
    room_plan.normalized({"rooms": least, "abilities": abilities})
    cfg = config.default_for("Cave", [PACK], archetype="metroidvania")
    cfg.starter_map = {"rooms": least, "abilities": abilities}
    schema.validate("config", cfg.to_json())
    if least > 5:
        with pytest.raises(room_plan.RoomPlanError, match="need at least"):
            room_plan.normalized({"rooms": least - 1, "abilities": abilities})
        cfg.starter_map = {"rooms": least - 1, "abilities": abilities}
        with pytest.raises(RpgGenError):  # the schema refuses it too
            schema.validate("config", cfg.to_json())


# --------------------------------------------------------------------------- reach


def test_what_the_player_reaches() -> None:
    assert room_plan.vertical_reach([]) == 3.25
    assert room_plan.vertical_reach(["double_jump"]) == 6.5
    assert room_plan.vertical_reach(["high_jump"]) == 4.5
    assert 4.5 < room_plan.horizontal_reach([]) < 5.0, "a plain jump crosses under five tiles"
    assert room_plan.horizontal_reach(["dash"]) > room_plan.horizontal_reach([]) + 3.5
    # the gates of the card: a 5-tile ledge for the double jump, a 6-tile gap for the dash
    assert room_plan.gate_size("double_jump", []) == 5
    assert room_plan.gate_size("dash", []) == 6
    assert room_plan.gate_size("high_jump", []) == 4
    assert room_plan.gate_size("break_blocks", ["dash"]) == 1


@pytest.mark.parametrize("ability", ["double_jump", "high_jump", "dash", "wall_jump"])
def test_a_gate_is_out_of_reach_before_its_ability_and_in_reach_with_it(ability: str) -> None:
    others = [a for a in ALL if a not in (ability, "break_blocks")]
    for n in range(len(others) + 1):
        before = [a for a in ALL if a in others[:n]]
        size = room_plan.gate_size(ability, before)
        if ability == "dash":
            assert room_plan.horizontal_reach(before) + 0.5 < size, (before, size)
            assert room_plan.horizontal_reach([*before, ability]) >= size + 1.0, (before, size)
        elif ability == "wall_jump":
            assert room_plan.vertical_reach(before) + 1.0 < size <= 15, (before, size)
        else:
            assert room_plan.vertical_reach(before) < size, (before, size)
            assert room_plan.vertical_reach([*before, ability]) >= size + 0.5, (before, size)


# --------------------------------------------------------------------------- the plan


def test_the_plan_is_deterministic_and_fits_its_schema() -> None:
    first = _plan()
    assert _plan() == first
    assert _plan(seed=7) != first
    schema.validate("world_plan", room_plan.world(first, 12345))
    assert room_plan.summary(first) == "6 rooms, 2 abilities, a guardian"
    assert room_plan.describe({"rooms": 6}) == "6 rooms, 2 abilities, a guardian"
    assert room_plan.describe({"rooms": 5, "abilities": []}) == "5 rooms, 0 abilities"
    assert room_plan.summary(_plan(5, ["dash"])) == "5 rooms, 1 ability, a guardian"


@pytest.mark.parametrize(("rooms", "count"), [(5, 0), (5, 2), (6, 2), (8, 5), (12, 5), (12, 1)])
def test_the_rooms_of_a_plan(rooms: int, count: int) -> None:
    abilities = ALL[:count]
    plan = _plan(rooms, abilities, seed=rooms * 31 + count)
    listed = plan["list"]
    assert len(listed) == rooms
    assert [r["id"] for r in listed] == [f"room_{i + 1:02d}" for i in range(rooms)]
    kinds = [r["kind"] for r in listed]
    assert kinds[0] == "start" and kinds[-1] == "end"
    assert kinds.count("guardian") == (1 if count else 0)
    assert kinds.count("pickup") == max(0, count - 1), "the guardian has the first ability"
    assert kinds.count("shaft") <= 1
    assert plan["start"] == "room_01" and plan["end"] == listed[-1]["id"]
    cells = [tuple(r["cell"]) for r in listed]
    assert len(set(cells)) == rooms, "no two rooms in one cell of the grid"
    for room in listed:
        assert len(room["tiles"]) == 23 and {len(row) for row in room["tiles"]} == {40}
        assert room["map"] == f"game/maps/rooms/{room['id']}.tscn"
    assert room_plan.check(plan) == {"unreachable": [], "unpaired": []}


def test_exits_pair_up_on_shared_edges() -> None:
    plan = _plan(8, ALL[:3], seed=3)
    by_id = {r["id"]: r for r in plan["list"]}
    for room in plan["list"]:
        for exit_ in room["exits"]:
            other = by_id[exit_["to"]]
            partner = next(e for e in other["exits"] if e["id"] == exit_["to_exit"])
            assert partner["to"] == room["id"] and partner["to_exit"] == exit_["id"]
            assert partner["edge"] == room_plan.OPPOSITE[exit_["edge"]]
            step = room_plan.STEP[exit_["edge"]]
            assert other["cell"] == [room["cell"][0] + step[0], room["cell"][1] + step[1]]
            x, y = exit_["cell"]
            if exit_["edge"] in ("E", "W"):
                # an opening three tiles high above the floor, on the edge column
                assert x == (39 if exit_["edge"] == "E" else 0) and y == 19
                assert [room["tiles"][r][x] for r in (17, 18, 19, 20)] == [".", ".", ".", "#"]
                assert partner["cell"][1] == y, "both sides at the same height"
            else:
                assert _at(room, [x, y]) == "H", "a ladder leads through the ceiling or the floor"
                assert partner["cell"][0] == x


def test_the_critical_path_and_the_lock_and_key_order() -> None:
    for seed in range(30):
        plan = _plan(9, ALL, seed=seed)
        ids = [r["id"] for r in plan["list"]]
        graph = room_plan.graph_of(plan)
        placed = room_plan.placements(plan)
        assert list(placed) == ALL, "every ability lies somewhere, in the table's order"
        assert plan["path"][0] == ids[0] and plan["path"][-1] == ids[-1]
        held: list[str] = []
        for ability in ALL:
            reach = lockkey.reachable(graph, ids[0], held)
            assert placed[ability] in reach, f"{ability} is reachable with the ones before it"
            assert ids[-1] not in reach, "the end room needs them all"
            held.append(ability)
        assert ids[-1] in lockkey.reachable(graph, ids[0], held)
        assert room_plan.room_of(plan, placed[ALL[0]])["kind"] == "guardian"
        assert plan["guardian"] == placed[ALL[0]]
        gates = [g["ability"] for r in plan["list"] for g in r["gates"]]
        assert gates == ALL, "the gates come in the order of the abilities"


def test_no_plan_has_an_unreachable_room_or_an_unpaired_exit_over_200_seeds() -> None:
    for seed in range(200):
        count = seed % 6
        rooms = max(5, count + 3) + seed % 4
        plan = _plan(min(12, rooms), ALL[:count], seed=seed, enemies=seed % 5, pickups=seed % 13)
        assert room_plan.check(plan) == {"unreachable": [], "unpaired": []}, seed
        schema.validate("world_plan", room_plan.world(plan, seed))


def test_the_start_room_teaches() -> None:
    start = _plan()["list"][0]
    assert start["spawn"] == [3, 19] and start["sign"] == [5, 19] and start["station"] == [8, 19]
    floor = start["tiles"][20]
    assert floor[13:16] == "..." and start["tiles"][21][13:16] == "^^^", "a 3-tile gap over spikes"
    assert start["tiles"][17][19:23] == "====", "a one-way platform three tiles up"
    assert start["tiles"][19][26] == "^", "spikes on the floor"
    assert [e["edge"] for e in start["exits"]] == ["E"] and "needs" not in start["exits"][0]
    assert start["gates"] == [] and start["enemies"] == []


def test_things_stand_on_the_floor_and_away_from_each_other() -> None:
    for seed in range(40):
        plan = _plan(10, ALL[:4], seed=seed, enemies=4, pickups=12)
        for room in plan["list"]:
            feet: list[list[int]] = [*room["enemies"], *room["items"]]
            for key in ("spawn", "sign", "station", "npc", "chest"):
                if key in room:
                    feet.append(room[key])
            if "guardian" in room:
                feet.append(room["guardian"]["cell"])
            if "pickup" in room:
                feet.append(room["pickup"]["cell"])
            for x, y in feet:
                assert room["tiles"][y][x] in ".", (seed, room["id"], x, y)
                assert room["tiles"][y + 1][x] in "#=", (seed, room["id"], x, y)
            assert len({tuple(c) for c in feet}) == len(feet), (seed, room["id"])
            for x, _y in room["enemies"]:
                assert x >= 8, "an enemy is not at the door"


def test_a_room_with_a_gate_has_nothing_to_stand_on_but_the_floor() -> None:
    for seed in range(60):
        plan = _plan(8, ALL, seed=seed)
        for room in plan["list"]:
            if not room["gates"]:
                continue
            gate = room["gates"][0]
            x = gate["cell"][0]
            before = [row[2:x] for row in room["tiles"][2:19]]
            assert all("=" not in row for row in before), (seed, room["id"])
            if gate["kind"] in ("ledge", "gap"):
                # (a ladder that comes up through the floor is not a place to jump from)
                assert all(set(row) <= {".", "H"} for row in before), (seed, room["id"])
            assert room["tiles"][19][gate["cell"][0]] == "."


def test_the_gates_are_drawn_to_their_size() -> None:
    plan = _plan(6, ["double_jump", "dash"])
    ledge = next(g for r in plan["list"] for g in r["gates"] if g["kind"] == "ledge")
    room = next(r for r in plan["list"] if ledge in r["gates"])
    x = ledge["cell"][0] + 1
    assert ledge["size"] == 5
    column = [row[x + 2] for row in room["tiles"]]
    assert column[15:20] == ["#"] * 5 and column[14] == ".", "a block five tiles high"
    assert room["tiles"][15][x : x + 2] == "##" and room["tiles"][16][x : x + 2] == "..", (
        "its top reaches out over the face"
    )
    gap = next(g for r in plan["list"] for g in r["gates"] if g["kind"] == "gap")
    room = next(r for r in plan["list"] if gap in r["gates"])
    x = gap["cell"][0] + 1
    assert gap["size"] == 9, "with the double jump in hand a dash gap is nine tiles"
    assert room["tiles"][20][x : x + 9] == "." * 9 and room["tiles"][21][x : x + 9] == "^" * 9
    assert room["tiles"][20][x - 1] == "#" and room["tiles"][20][x + 9] == "#"
    only_dash = _plan(5, ["dash"])
    assert [g["size"] for r in only_dash["list"] for g in r["gates"]] == [6], (
        "the card's 6-tile gap"
    )
    walls = _plan(5, ["break_blocks"])
    wall = next(g for r in walls["list"] for g in r["gates"])
    room = next(r for r in walls["list"] if wall in r["gates"])
    x = wall["cell"][0] + 1
    assert [row[x] for row in room["tiles"]][2:20] == ["#"] * 16 + ["B", "B"]


def test_a_shaft_joins_two_rooms_by_a_ladder() -> None:
    found = 0
    for seed in range(40):
        plan = _plan(8, ["double_jump"], seed=seed)
        shafts = [r for r in plan["list"] if r["kind"] == "shaft"]
        if not shafts:
            continue
        found += 1
        shaft = shafts[0]
        up = next(e for e in shaft["exits"] if e["edge"] == "N")
        above = _room(plan, up["to"])
        assert above["cell"] == [shaft["cell"][0], shaft["cell"][1] - 1]
        assert above["kind"] != "guardian"
        x = up["cell"][0]
        assert {row[x] for row in shaft["tiles"][0:20]} == {"H"}, "a ladder from the floor up"
        column = [row[x] for row in above["tiles"]]
        assert column[18:23] == ["H", "H", "T", "H", "H"], (
            "out of the floor, with a platform on the hole"
        )
    assert found > 20


# --------------------------------------------------------------------------- the stored plan


def test_the_stored_plan_is_reused_once_a_room_exists(tmp_path: Path) -> None:
    project = tmp_path / "project"
    options = {"rooms": 6}
    first, notes = room_plan.for_project(project, options, 1)
    assert notes == [] and first["rooms"]["list"][0]["id"] == "room_01"
    world_plan.save(project, first)
    assert world_plan.load(project) == first
    assert not room_plan.exists(project)
    # nothing is built yet: another seed still gives another plan
    other, _ = room_plan.for_project(project, options, 2)
    assert other["rooms"] != first["rooms"] and other["seed"] == 2
    # one room exists: the plan is kept whatever the seed and the options say
    room = project / "game/maps/rooms/room_03.tscn"
    room.parent.mkdir(parents=True)
    room.write_text("[gd_scene]\n", encoding="utf-8")
    assert room_plan.exists(project)
    assert room_plan.existing_rooms(project, first["rooms"]) == {"room_03"}
    kept, notes = room_plan.for_project(project, {"rooms": 9, "abilities": ALL}, 99)
    assert kept == first and notes == []


def test_record_hashes_notes_the_rooms_this_run_built(tmp_path: Path) -> None:
    project = tmp_path / "project"
    plan, _ = room_plan.for_project(project, {"rooms": 5}, 1)
    for ident in ("room_01", "room_02"):
        path = project / f"game/maps/rooms/{ident}.tscn"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(ident, encoding="utf-8")
    assert world_plan.record_hashes(project, plan)
    assert sorted(plan["maps"]) == ["room_01", "room_02"]
    assert not world_plan.record_hashes(project, plan), "nothing new the second time"
    world_plan.save(project, plan)


def test_an_added_room_is_appended_and_joined(tmp_path: Path) -> None:
    project = tmp_path / "project"
    plan, _ = room_plan.for_project(project, {"rooms": 5}, 4)
    world_plan.save(project, plan)
    built = project / "game/maps/rooms/room_01.tscn"
    built.parent.mkdir(parents=True)
    built.write_text("x", encoding="utf-8")
    before = copy.deepcopy(plan["rooms"]["list"])
    options = {"rooms": 5, "added_rooms": [{"name": "Hidden Grotto", "join": "Room 1"}]}
    grown, notes = room_plan.for_project(project, options, 4)
    assert notes == ["The world kept its plan; added: room_hidden_grotto."]
    rooms = grown["rooms"]
    assert rooms["list"][:5] == before, "no room that was planned before changes"
    new = rooms["list"][5]
    assert new["id"] == "room_hidden_grotto" and new["name"] == "Hidden Grotto"
    assert new["kind"] == "corridor" and new["added"] is True and new["gates"] == []
    start = rooms["list"][0]
    assert new["cell"] == [start["cell"][0] - 1, start["cell"][1]], "on the start room's free side"
    assert [(e["edge"], e["to"], e["to_exit"]) for e in new["exits"]] == [
        ("E", "room_01", "room_01_exit_w")
    ]
    assert grown["grid"]["room_hidden_grotto"] == new["cell"]
    schema.validate("world_plan", grown)
    # the neighbour's side is the repair's to make: until then the new exit is unpaired
    assert room_plan.check(rooms) == {
        "unreachable": ["room_hidden_grotto"],
        "unpaired": ["room_hidden_grotto_exit_e"],
    }
    # the same row again adds nothing; a second row finds another free side
    again, added = room_plan.extend(rooms, options["added_rooms"], 4)
    assert added == [] and again == rooms
    more, added = room_plan.extend(rooms, [{"name": "Annex", "join": "Room 1"}], 4)
    assert added == ["room_annex"]
    assert tuple(more["list"][-1]["cell"]) not in {tuple(r["cell"]) for r in rooms["list"]}


def test_a_plan_file_without_rooms_is_still_a_world_plan(tmp_path: Path) -> None:
    """The areas of a top-down world validate as before; `rooms` is an optional section."""
    plan = world_plan.plan(world_plan.default_areas(), 5)
    assert "rooms" not in plan
    schema.validate("world_plan", plan)
    jsonio.write(tmp_path / "plan.json", plan)
