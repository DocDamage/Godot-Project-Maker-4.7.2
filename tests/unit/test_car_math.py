"""T16.12: the arithmetic of a racing game's car, and the table of cases the GDScript mirror
(``RpgCarPhysics``) is tested against."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from rpggen.core import car_math

REPO = Path(__file__).resolve().parents[2]
DT = 1.0 / 60.0


def _drive(seconds: float, throttle: float, steer: float = 0.0, surface: str = "road", **start):
    state = {"x": 0.0, "y": 0.0, "heading": 0.0, "vx": 0.0, "vy": 0.0, "boost": 0.0, **start}
    for _ in range(round(seconds / DT)):
        state = car_math.step(state, throttle, steer, surface, DT)
    return state


def test_the_table_of_cases_is_what_the_module_gives() -> None:
    """The file the GDScript test reads is written by ``python -m rpggen.core.car_math``; a
    change of the model that is not written there fails here, and then in Godot."""
    stored = json.loads((REPO / car_math.CASES_FILE).read_text(encoding="utf-8"))
    assert stored == car_math.cases()
    names = {case["fn"] for case in stored}
    public = {
        name
        for name, value in vars(car_math).items()
        if callable(value) and not name.startswith("_") and value.__module__ == car_math.__name__
    }
    # every function of the model is in the table (`step` as the drive, at the end)
    made_up = {"drive", "drive_tuned", "slide_tuned"}  # `step` and `slide` with a car's parts
    assert public - {"cases", "write_cases", "step", "move_toward"} == names - made_up
    assert [c["fn"] for c in stored[-2:]] == ["drive", "drive_tuned"]
    assert len(stored[-1]["result"]) == len(stored[-2]["result"]) == 6
    assert stored[-1]["result"] != stored[-2]["result"], "a car with parts drives another line"
    assert len(stored) > 300


def test_the_runtime_has_the_same_numbers() -> None:
    text = (REPO / "godot_templates/addons/rpg_runtime/archetypes/racing/car_physics.gd").read_text(
        encoding="utf-8"
    )
    for name in (
        "TOP", "ACCEL", "BRAKE", "DRAG", "REVERSE", "OVERSPEED", "TURN_SLOW", "TURN_FAST",
        "TURN_FROM", "TRACTION", "DRIFT_FROM", "BOUNCE", "SCRAPE", "BOOST_TOP", "BOOST_ACCEL",
        "BOOST_S", "STEER_FULL", "LEAD", "ZOOM_FAR",
    ):  # fmt: skip
        value = re.escape(repr(getattr(car_math, name)))
        assert re.search(rf"^const {name} := {value}(\s|$)", text, re.MULTILINE), name
    for part, value in car_math.PART_STEP.items():
        assert f'"{part}": {value!r}' in text, part
    assert f"const PART_LEVELS := {car_math.PART_LEVELS}" in text
    for surface, (grip, top) in car_math.SURFACES.items():
        assert f'"{surface}": [{grip!r}, {top!r}]' in text, surface
    for name, surface in car_math.SURFACE_NAMES.items():
        assert f'"{name}": "{surface}"' in text, name


def test_a_car_reaches_its_top_speed_brakes_and_reverses() -> None:
    state = _drive(1.0, 1.0)
    assert state["vx"] == pytest.approx(car_math.ACCEL, abs=0.01) and state["vy"] == 0.0
    state = _drive(3.0, 1.0)
    assert state["vx"] == pytest.approx(car_math.TOP), "and no faster"
    rolled = _drive(0.5, 0.0, vx=car_math.TOP)
    assert 0.0 < rolled["vx"] < car_math.TOP
    assert _drive(1.0, -1.0, vx=car_math.TOP)["vx"] < 0.0, "the brake stops it and reverses"
    assert _drive(3.0, -1.0)["vx"] == pytest.approx(-car_math.TOP * car_math.REVERSE)
    boosted = _drive(1.0, 1.0, vx=car_math.TOP, boost=car_math.BOOST_S)
    assert boosted["vx"] == pytest.approx(car_math.TOP * car_math.BOOST_TOP)
    after = _drive(3.0, 1.0, vx=car_math.TOP, boost=car_math.BOOST_S)
    assert after["vx"] == pytest.approx(car_math.TOP) and after["boost"] == 0.0


def test_it_turns_more_slowly_at_speed_and_not_at_all_standing() -> None:
    assert car_math.turn_rate(0.0) == 0.0
    assert car_math.turn_rate(1.0) > car_math.turn_rate(6.0) > car_math.turn_rate(car_math.TOP)
    assert car_math.turn_rate(car_math.TOP) == pytest.approx(car_math.TURN_FAST)
    assert car_math.turn_rate(99.0) == pytest.approx(car_math.TURN_FAST)
    assert car_math.turn_rate(-3.0) < 0.0, "in reverse the wheel turns the car the other way"
    assert _drive(1.0, 0.0, steer=1.0)["heading"] == 0.0
    assert _drive(1.0, 1.0, steer=1.0)["heading"] > 0.0, "to the right is clockwise"
    assert _drive(1.0, 1.0, steer=-1.0)["heading"] < 0.0


def test_the_ground_decides_the_speed_and_the_grip() -> None:
    grips = [car_math.grip(s) for s in ("road", "dirt", "grass", "oil")]
    assert grips == sorted(grips, reverse=True) and grips[-1] > 0.0
    assert _drive(3.0, 1.0, surface="grass")["vx"] == pytest.approx(car_math.top_speed("grass"))
    assert car_math.top_speed("grass") < car_math.top_speed("dirt") < car_math.top_speed("road")
    slowed = _drive(0.25, 1.0, surface="grass", vx=car_math.TOP)
    assert car_math.top_speed("grass") < slowed["vx"] < car_math.TOP, "it slows, not at once"
    for name, surface in (("Asphalt", "road"), ("sand", "dirt"), ("ICE", "oil"), ("?", "road")):
        assert car_math.surface(name) == surface
    # a hard turn at the top speed is a drift, on the road too; a gentle one is not
    hard = _drive(0.6, 1.0, steer=1.0, vx=car_math.TOP)
    assert car_math.is_drifting(hard["lateral"])
    assert not car_math.is_drifting(_drive(0.6, 1.0, steer=0.3, vx=car_math.TOP)["lateral"])
    assert not car_math.is_drifting(_drive(0.6, 0.3, steer=1.0, vx=4.0)["lateral"])
    # on oil the wheel does little and the slide stays
    assert abs(_drive(0.5, 1.0, 1.0, "oil", vx=8.0)["heading"]) < abs(
        _drive(0.5, 1.0, 1.0, "road", vx=8.0)["heading"]
    )
    assert car_math.slide(3.0, "oil", 0.5) > car_math.slide(3.0, "road", 0.5) == 0.0
    # the speed of a curve: what the grip holds
    assert car_math.curve_speed(2.0) < car_math.curve_speed(6.0) <= car_math.TOP
    assert car_math.curve_speed(100.0) == car_math.TOP
    assert car_math.curve_speed(3.0, "grass") < car_math.curve_speed(3.0)
    radius = 3.0
    speed = car_math.curve_speed(radius)
    assert speed * (speed / radius) == pytest.approx(car_math.TRACTION), "no slide is left over"


def test_a_bump_costs_speed() -> None:
    assert car_math.bump(8.0, 0.0, -1.0, 0.0) == pytest.approx((-8.0 * car_math.BOUNCE, 0.0))
    along = car_math.bump(0.0, 8.0, -1.0, 0.0)
    assert along == (0.0, 8.0), "nothing goes into a wall the car drives along"
    vx, vy = car_math.bump(6.0, 6.0, -1.0, 0.0)
    assert vx < 0.0 and 0.0 < vy < 6.0, "at an angle it comes off and scrapes on"
    assert math.hypot(vx, vy) < math.hypot(6.0, 6.0)
    assert car_math.bump(-3.0, 2.0, -1.0, 0.0) == (-3.0, 2.0), "moving away is no bump"


def test_headings_frames_and_the_camera() -> None:
    frames = [car_math.heading_frame(-math.pi / 2 + k * math.tau / 16, 16) for k in range(16)]
    assert frames == list(range(16)), "the first frame points up, then clockwise"
    assert car_math.heading_frame(0.0, 16) == 4 and car_math.heading_frame(math.pi, 16) == 12
    assert car_math.heading_frame(-math.pi / 2 + 0.19, 16) == 0, "the nearest heading"
    assert car_math.heading_frame(-math.pi / 2 + 0.2, 16) == 1
    assert car_math.heading_frame(1.0, 1) == 0
    assert car_math.heading_frame(-math.pi / 2 + 20 * math.tau, 8) == 0
    assert car_math.angle_difference(3.0, -3.0) == pytest.approx(math.tau - 6.0)
    assert car_math.steer_toward(0.0, 0.1) == pytest.approx(0.2)
    assert car_math.steer_toward(0.0, 2.0) == 1.0 and car_math.steer_toward(0.0, -2.0) == -1.0
    assert car_math.steer_toward(3.0, -3.0) > 0.0, "the short way round"
    assert car_math.look_ahead(0.0, 0.0, 360.0) == (0.0, 0.0)
    assert car_math.look_ahead(car_math.TOP, 0.0, 360.0) == pytest.approx((90.0, 0.0))
    assert car_math.look_ahead(0.0, -6.0, 360.0) == pytest.approx((0.0, -45.0))
    assert car_math.look_ahead(99.0, 0.0, 360.0) == pytest.approx((90.0, 0.0)), "no further"
    assert car_math.zoom_for(0.0) == 1.0 and car_math.zoom_for(car_math.TOP) == car_math.ZOOM_FAR
    assert car_math.ZOOM_FAR < car_math.zoom_for(6.0) < 1.0
    assert car_math.split(*car_math.join(5.0, -2.0, 0.7), 0.7) == pytest.approx((5.0, -2.0))
