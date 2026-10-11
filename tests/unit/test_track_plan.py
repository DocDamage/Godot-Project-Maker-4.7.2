"""T16.13: the tracks of a racing game: closed loops that never cross, with a start, checkpoints
in order and waypoints a car can follow; stored once and grown by *Added tracks*; the picture of
them."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import pytest

from rpggen import jsonio, schema
from rpggen.core import car_math, config, map_preview, options, track_plan, world_plan

FACTS = {"view": [640, 360], "tile": 16}
SURFACE = {"r": "road", "s": "road", "g": "grass", "d": "dirt", "o": "oil", "b": "boost"}


def _drive(track: dict, tile: int, laps: int = 1) -> dict:
    """A simple driver on the car's own arithmetic, the one the smoke step of a generated game
    uses: head for the next waypoint, brake down to its speed in time, no pedal while still
    turning at speed. Returns how many steps it took, how many of them on grass, and how many
    checkpoints it passed in their order."""
    rows, way, start = track["rows"], track["waypoints"], track["start"]
    points = [[p["position"][0] / tile, p["position"][1] / tile] for p in track["checkpoints"]]
    state = {
        "x": start["position"][0] / tile,
        "y": start["position"][1] / tile,
        "heading": start["heading"],
        "vx": 0.0,
        "vy": 0.0,
        "boost": 0.0,
    }
    steps = grass = passed = 0
    for n in range(laps * len(way) + 1):
        goal = way[n % len(way)]
        gx, gy = goal["position"][0] / tile, goal["position"][1] / tile
        for _ in range(60 * 25):
            dx, dy = gx - state["x"], gy - state["y"]
            dist = math.hypot(dx, dy)
            if dist < 4.0:
                break
            speed, _lateral = car_math.split(state["vx"], state["vy"], state["heading"])
            off = car_math.angle_difference(state["heading"], math.atan2(dy, dx))
            wheel = car_math.steer_toward(state["heading"], math.atan2(dy, dx))
            limit = goal["speed"]
            room = (speed * speed - limit * limit) / (2 * car_math.BRAKE) + 2.5
            slow = speed > limit and dist < room
            pedal = -1.0 if slow else (0.0 if abs(off) > 0.45 and speed > 6.0 else 1.0)
            steer = 1.0 if wheel > 0.15 else -1.0 if wheel < -0.15 else 0.0
            cx, cy = math.floor(state["x"]), math.floor(state["y"])
            inside = 0 <= cy < len(rows) and 0 <= cx < len(rows[0])
            surface = SURFACE[rows[cy][cx]] if inside else "grass"
            state = car_math.step(state, pedal, steer, surface, 1 / 60)
            steps += 1
            grass += surface == "grass"
            if points:
                px, py = points[passed % len(points)]
                passed += math.hypot(px - state["x"], py - state["y"]) < 4.0
        else:
            return {"ok": False, "steps": steps, "grass": grass, "passed": passed}
    return {"ok": True, "steps": steps, "grass": grass, "passed": passed}


def test_the_plan_is_the_same_for_the_same_seed_and_fits_the_schema() -> None:
    first = track_plan.plan({}, 12345, FACTS)
    assert first == track_plan.plan({}, 12345, FACTS)
    assert first != track_plan.plan({}, 12346, FACTS)
    assert (first["kind"], first["block"], first["road"]) == ("racing", 9, 5)
    assert [t["id"] for t in first["list"]] == ["stage_01", "stage_02", "stage_03", "stage_04"]
    schema.validate("world_plan", track_plan.world(first, 12345))
    assert track_plan.check(first) == []
    for track in first["list"]:
        assert (track["axis"], track["exit"], track["waves"]) == ("none", "custom", [])
        assert track["scene"] == f"res://generated/scenes/stages/{track['id']}.tscn"
        assert track["laps"] == 3
        cols, rows = track["cells"]
        assert len(track["rows"]) == rows * 9 + 2 and len(track["rows"][0]) == cols * 9 + 2
        assert set("".join(track["rows"])) <= set("rgdobs")
        assert track["par_time_s"] > 0
    assert track_plan.summary(first).startswith("4 tracks of 3 laps, ")
    # the size of the screen does not change a track; the size of a tile scales its places
    wide = track_plan.plan({}, 12345, {"view": [1280, 720], "tile": 16})
    assert [t["rows"] for t in wide["list"]] == [t["rows"] for t in first["list"]]
    big = track_plan.plan({}, 12345, {"view": [640, 360], "tile": 32})
    assert big["list"][0]["rows"] == first["list"][0]["rows"]
    assert big["list"][0]["start"]["position"] == [
        v * 2 for v in first["list"][0]["start"]["position"]
    ]


def test_a_loop_is_closed_never_crosses_and_starts_on_a_straight() -> None:
    for seed in range(60):
        for size, (cols, rows) in track_plan.SIZES.items():
            for difficulty in track_plan.DIFFICULTIES:
                plan = track_plan.plan({"track_size": size, "difficulty": difficulty}, seed, FACTS)
                assert track_plan.check(plan) == []
                for track in plan["list"]:
                    loop = [tuple(c) for c in track["loop"]]
                    where = (seed, size, difficulty, track["id"])
                    assert len(set(loop)) == len(loop) >= 8, where
                    for i, cell in enumerate(loop):
                        step = (cell[0] - loop[i - 1][0], cell[1] - loop[i - 1][1])
                        assert abs(step[0]) + abs(step[1]) == 1, where
                        assert 0 <= cell[0] < cols and 0 <= cell[1] < rows, where
                    # cut to the loop: it touches every edge of its field
                    assert min(c[0] for c in loop) == 0 and min(c[1] for c in loop) == 0
                    assert track["cells"] == [
                        max(c[0] for c in loop) + 1,
                        max(c[1] for c in loop) + 1,
                    ]
                    # the first two cells are one straight: the cars have room to get going
                    way = (loop[1][0] - loop[0][0], loop[1][1] - loop[0][1])
                    assert (loop[0][0] - loop[-1][0], loop[0][1] - loop[-1][1]) == way, where
                    assert (loop[2][0] - loop[1][0], loop[2][1] - loop[1][1]) == way, where
                    start = track["start"]
                    assert start["heading"] == pytest.approx(math.atan2(way[1], way[0]), abs=1e-5)
                    ahead = (start["line"][0] - start["position"][0]) * way[0] + (
                        start["line"][1] - start["position"][1]
                    ) * way[1]
                    assert ahead == 2 * 16, "the line is two tiles ahead of the car"
                    # an even number of cells, as every loop on a grid has
                    assert len(loop) % 2 == 0


def test_the_checkpoints_are_in_the_order_of_the_loop_and_the_waypoints_on_the_road() -> None:
    plan = track_plan.plan({"track_size": "large", "difficulty": "hard"}, 5, FACTS)
    for track in plan["list"]:
        loop = [tuple(c) for c in track["loop"]]
        rows = track["rows"]
        order = [loop.index(tuple(p["cell"])) for p in track["checkpoints"]]
        assert order == sorted(order) and order[0] > 0, "after the start, one after the other"
        assert len(order) == (len(loop) - 1) // 2, "every second cell"
        assert [p["id"] for p in track["checkpoints"]] == [
            f"c{i + 1:02d}" for i in range(len(order))
        ]
        for point in track["checkpoints"]:
            assert point["width"] == 9 * 16, "as wide as its cell: the verge counts"
        assert [tuple(w["cell"]) for w in track["waypoints"]] == loop, "one a cell, in order"
        for i, point in enumerate(track["waypoints"]):
            x, y = (math.floor(v / 16) for v in point["position"])
            assert rows[y][x] in track_plan.ROAD_LETTERS
            straight = track_plan._is_straight(loop, i)
            surface = {"d": "dirt", "o": "oil"}.get(rows[y][x], "road")
            if straight:
                assert point["speed"] == pytest.approx(car_math.top_speed(surface), abs=0.01)
            else:
                assert point["speed"] < car_math.TOP, "a corner is taken slowly"
                assert point["speed"] == pytest.approx(
                    car_math.curve_speed(track_plan.CORNER_RADIUS, surface), abs=0.01
                )
        # tyres at the outside of every corner, on the grass
        corners = [i for i in range(len(loop)) if not track_plan._is_straight(loop, i)]
        assert len(track["tyres"]) == len(corners) >= 4
        for x, y in track["tyres"]:
            assert rows[math.floor(y / 16)][math.floor(x / 16)] == "g"
        # barriers: the four edges, and every cell the loop does not use
        cols, cells_y = track["cells"]
        assert track["barriers"][:4] == [
            [0, 0, cols * 9 + 2, 1],
            [0, cells_y * 9 + 1, cols * 9 + 2, 1],
            [0, 0, 1, cells_y * 9 + 2],
            [cols * 9 + 1, 0, 1, cells_y * 9 + 2],
        ]
        covered = sum(w * h for _x, _y, w, h in track["barriers"][4:])
        assert covered == (cols * cells_y - len(loop)) * 81
        for x, y, w, h in track["barriers"][4:]:
            for row in rows[y : y + h]:
                assert set(row[x : x + w]) == {"g"}, "no barrier on the road"
        assert len(track["decoration"]) == 2 * (cols * cells_y - len(loop))
        for point in track["pickups"]:
            assert point["kind"] in track_plan.PICKUPS
            x, y = (math.floor(v / 16) for v in point["position"])
            assert rows[y][x] in track_plan.ROAD_LETTERS


def test_later_tracks_are_longer_and_have_more_on_them() -> None:
    cells, corners, hazards = [0] * 4, [0] * 4, [0] * 4
    for seed in range(40):
        plan = track_plan.plan({"track_size": "large"}, seed, FACTS)
        for i, track in enumerate(plan["list"]):
            loop = [tuple(c) for c in track["loop"]]
            cells[i] += len(loop)
            corners[i] += sum(not track_plan._is_straight(loop, k) for k in range(len(loop)))
            hazards[i] += sum("".join(track["rows"]).count(c) for c in "do")
    assert cells == sorted(cells) and cells[0] < cells[-1], cells
    assert corners == sorted(corners) and corners[0] < corners[-1], corners
    assert hazards[0] < hazards[-1], hazards
    easy, hard = (track_plan.counts_of(2, d) for d in ("easy", "hard"))
    assert easy["oil"] < hard["oil"] and easy["dirt"] < hard["dirt"]
    assert track_plan.counts_of(0, "easy")["boost"] >= 1, "every track has a boost arrow"
    # what lies on the road is never where the race starts
    for track in track_plan.plan({"difficulty": "hard", "tracks": 8}, 3, FACTS)["list"]:
        for cell in track["loop"][:2]:
            ox, oy = 1 + cell[0] * 9, 1 + cell[1] * 9
            block = "".join(row[ox : ox + 9] for row in track["rows"][oy : oy + 9])
            assert set(block) <= set("rgs")
    small = track_plan.plan({"track_size": "small", "tracks": 8, "difficulty": "hard"}, 1, FACTS)
    assert max(len(t["loop"]) for t in small["list"]) <= 12, "a small field is full at 12 cells"


def test_every_planned_track_can_be_driven_lap_after_lap() -> None:
    worst = 0.0
    for seed in range(12):
        for size in track_plan.SIZES:
            plan = track_plan.plan({"track_size": size, "difficulty": "hard"}, seed, FACTS)
            for track in plan["list"]:
                drove = _drive(track, 16, laps=2)
                where = (seed, size, track["id"])
                assert drove["ok"], where
                assert drove["passed"] == 2 * len(track["checkpoints"]), where
                worst = max(worst, drove["grass"] / drove["steps"])
    assert worst < 0.05, f"the driver was on the grass for {worst:.0%} of a drive"
    # a tile of another size is the same track
    big = track_plan.plan({}, 4, {"view": [640, 360], "tile": 32})
    assert _drive(big["list"][0], 32)["ok"]


def test_a_track_that_cannot_be_raced_is_reported() -> None:
    from rpggen.errors_table import CODES

    assert CODES["VAL-029"].severity == "warning"
    plan = track_plan.plan({"tracks": 1}, 9, FACTS)
    track = plan["list"][0]
    assert track_plan.check_track(track, 16) == []

    def broken(change) -> list[str]:
        other = copy.deepcopy(track)
        change(other)
        return track_plan.check_track(other, 16)

    def cut(t: dict) -> None:  # a strip of grass across the road of the third cell
        ox, oy = 1 + t["loop"][2][0] * 9, 1 + t["loop"][2][1] * 9
        rows = [list(r) for r in t["rows"]]
        for k in range(9):
            rows[oy + 4][ox + k] = rows[oy + k][ox + 4] = "g"
        t["rows"] = ["".join(r) for r in rows]

    assert any("waypoint 3 is not on the road" in p for p in broken(cut))

    def island(t: dict) -> None:  # a piece of road nothing leads to
        rows = [list(r) for r in t["rows"]]
        cols, cells = t["cells"]
        free = next((x, y) for y in range(cells) for x in range(cols) if [x, y] not in t["loop"])
        rows[1 + free[1] * 9 + 4][1 + free[0] * 9 + 4] = "r"
        t["rows"] = ["".join(r) for r in rows]

    loose = track_plan.plan({"tracks": 1, "track_size": "large"}, 2, FACTS)["list"][0]
    assert len(loose["loop"]) < 24, "a track with a cell to spare"
    other = copy.deepcopy(loose)
    island(other)
    assert track_plan.check_track(other, 16) == ["1 tiles of road cannot be reached from the start"]

    def swapped(t: dict) -> None:
        t["checkpoints"][0], t["checkpoints"][1] = t["checkpoints"][1], t["checkpoints"][0]

    assert any("is not after the one before it" in p for p in broken(swapped))

    def crossing(t: dict) -> None:
        t["loop"][3] = t["loop"][1]

    found = broken(crossing)
    assert "the loop crosses itself" in found and any("not closed" in p for p in found)

    def narrow(t: dict) -> None:  # one tile of road through the fourth cell
        ox, oy = 1 + t["loop"][3][0] * 9, 1 + t["loop"][3][1] * 9
        rows = [list(r) for r in t["rows"]]
        for y in range(9):
            for x in range(9):
                if x != 4 and y != 4:
                    rows[oy + y][ox + x] = "g"
        t["rows"] = ["".join(r) for r in rows]

    assert any("the road is 1 tiles wide" in p for p in broken(narrow))
    assert broken(lambda t: t.update(checkpoints=[])) == ["no checkpoint"]
    assert broken(lambda t: t["start"].update(line=[8.0, 8.0])) == [
        "the start line is not on the road"
    ]
    assert track_plan.check_track({"loop": [], "rows": []}, 16) == ["no loop"]
    both = copy.deepcopy(plan)
    swapped(both["list"][0])
    assert track_plan.check(both)[0].startswith("stage_01: checkpoint ")


def test_the_options_and_what_is_wrong_with_them() -> None:
    assert track_plan.defaults() == {
        "tracks": 4,
        "laps": 3,
        "track_size": "medium",
        "difficulty": "normal",
        "steering": "relative",
        "camera": "follow",
        "added_tracks": [],
    }
    assert config.starter_map_defaults("racing") == track_plan.defaults()
    assert len(track_plan.plan({"tracks": 7, "laps": 5}, 1, FACTS)["list"]) == 7
    assert track_plan.plan({"laps": 5}, 1, FACTS)["list"][0]["laps"] == 5
    assert track_plan.describe({"tracks": 2, "added_tracks": [{"name": "Dunes"}]}) == (
        "3 tracks of 3 laps"
    )
    assert track_plan.describe({"tracks": 1, "laps": 1}) == "1 track of 1 lap"
    assert options.stages_text("racing", {}) == "4 tracks of 3 laps"
    assert options.stages_text("racing", {"tracks": 99}) == ""
    for bad, word in (
        ({"tracks": 0}, "tracks"),
        ({"tracks": 9}, "tracks"),
        ({"laps": True}, "laps"),
        ({"track_size": "huge"}, "track_size"),
        ({"difficulty": "brutal"}, "difficulty"),
        ({"steering": "tank"}, "steering"),
        ({"camera": "chase"}, "camera"),
        ({"stages": 3}, "unknown option"),
        ({"added_tracks": [{"name": "A"}, {"name": "a"}]}, "two added tracks"),
        ({"added_tracks": [{}]}, "needs a name"),
    ):
        with pytest.raises(track_plan.TrackPlanError, match=word):
            track_plan.plan(bad, 1, FACTS)
    ref = config.PackRef("p", "p", "0" * 64, "folder")
    cfg = config.default_for("R", [ref], archetype="racing")
    cfg.starter_map = {"tracks": 6, "track_size": "large", "added_tracks": [{"name": "Dunes"}]}
    data = cfg.to_json()
    schema.validate("config", data)
    assert data["starter_map"]["laps"] == 3 and data["starter_map"]["tracks"] == 6
    assert config.GeneratorConfig.from_json(data).to_json() == data


def test_added_tracks_grow_the_plan_and_a_project_keeps_what_it_stored(tmp_path: Path) -> None:
    stored = track_plan.plan({"tracks": 2}, 8, FACTS)
    grown, added = track_plan.extend(stored, [{"name": "Dunes"}, {"name": "Harbour"}], 8)
    assert added == ["Dunes", "Harbour"] and grown["added"] == ["Dunes", "Harbour"]
    assert grown["list"][:2] == stored["list"], "what was planned stays as it is"
    assert [t["title"] for t in grown["list"]] == ["", "", "Dunes", "Harbour"]
    assert [t["level"] for t in grown["list"]] == [0, 1, 2, 3]
    assert track_plan.check(grown) == []
    again, added = track_plan.extend(grown, [{"name": "dunes"}, {"name": "Harbour"}], 99)
    assert added == [] and again == grown
    full = track_plan.plan({"tracks": 8}, 1, FACTS)
    full, _ = track_plan.extend(full, [{"name": str(i)} for i in range(4)], 1)
    with pytest.raises(track_plan.TrackPlanError, match="12 tracks at most"):
        track_plan.extend(full, [{"name": "one more"}], 1)
    # a project: a fresh plan first, then the stored one, whatever the options and the seed say
    project = tmp_path / "game"
    project.mkdir()
    first, notes = track_plan.for_project(project, {"tracks": 2}, 8, FACTS)
    assert notes == [] and first["stages"] == stored
    world_plan.save(project, first)
    assert not track_plan.exists(project), "the game has no list of its tracks yet"
    jsonio.write(project / track_plan.STAGES_FILE, {"stages": []})
    assert track_plan.exists(project)
    kept, notes = track_plan.for_project(
        project,
        {"tracks": 6, "track_size": "small", "added_tracks": [{"name": "Dunes"}]},
        4711,
        FACTS,
    )
    assert notes == ["The game kept its tracks; added: Dunes."]
    assert kept["stages"]["list"][:2] == stored["list"]
    assert len(kept["stages"]["list"]) == 3 and kept["stages"]["track_size"] == "medium"
    schema.validate("world_plan", kept)


def test_the_picture_of_the_tracks_is_drawn_from_the_plan() -> None:
    plan = track_plan.plan({}, 7, FACTS)
    track = plan["list"][0]
    one = map_preview.render_track(track, scale=4)
    assert one.size == (len(track["rows"][0]) * 4, len(track["rows"]) * 4)
    grass, road = map_preview.TRACK_COLORS["g"], map_preview.TRACK_COLORS["r"]
    wall = map_preview.TRACK_WALL
    assert one.getpixel((1, 1)) == wall, "the edge of the field"
    x, y = (math.floor(v / 16) for v in track["waypoints"][1]["position"])
    assert one.getpixel((x * 4 + 6, y * 4 + 6)) == road, "the road of a cell of the loop"
    tx, ty = (math.floor(v / 16 * 4) for v in track["tyres"][0])
    assert one.getpixel((tx, ty)) == grass
    cx, cy = (math.floor(v / 16 * 4) for v in track["checkpoints"][0]["position"])
    assert one.getpixel((cx, cy)) == map_preview.TRACK_CHECKPOINT
    sx, sy = (math.floor(v / 16 * 4) for v in track["start"]["position"])
    assert one.getpixel((sx, sy)) == (220, 60, 60), "the car at the start"
    colors = {color for _count, color in one.getcolors(1 << 16)}
    assert map_preview.TRACK_COLORS["s"] in colors, "the start line"
    # all of them, side by side
    rects = map_preview.track_rects(plan, 4)
    assert list(rects) == [t["id"] for t in plan["list"]]
    whole = map_preview.render_tracks(plan, 4)
    last = rects["stage_04"]
    assert whole.size == (last[0] + last[2], max(r[3] for r in rects.values()))
    assert rects["stage_02"][0] == rects["stage_01"][2] + map_preview.TRACK_GAP
    left, top, width, height = rects["stage_02"]
    assert whole.crop((left, top, left + width, top + height)).tobytes() == (
        map_preview.render_track(plan["list"][1], 4).tobytes()
    )
    # a plan of bigger tiles is the same picture
    big = track_plan.plan({}, 7, {"view": [640, 360], "tile": 32})
    assert map_preview.render_tracks(big, 4).tobytes() == whole.tobytes()
