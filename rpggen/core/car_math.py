"""The arithmetic of a racing game's car (T16.12), the same the runtime drives by.

``RpgCarPhysics`` (``archetypes/racing/car_physics.gd``) has every function of this module with
the same numbers; ``cases()`` is a table of inputs and results that both are tested against
(``godot_templates/tests/unit/car_math_cases.json``, written by ``python -m
rpggen.core.car_math``). The track planner of T16.13 uses it for the speed a curve can be
taken at.

The model is an arcade one. A car has a heading and a speed along it; it speeds up to a top
speed, brakes, rolls out, and reverses slowly. It turns faster when it is slow than when it is
fast. What it drives on gives it grip: on grass it is slower and slides, on oil it hardly
steers. Turning moves the heading; the speed the car had sideways to its new heading fades
with the grip, and while there is much of it the car drifts. A bump costs speed. Lengths are
in tiles and angles in radians (0 is to the right, a quarter turn clockwise is down, as on
the screen). No Qt, no Godot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# what a surface does: (grip, how much of the top speed it allows)
SURFACES: dict[str, tuple[float, float]] = {
    "road": (1.0, 1.0),
    "boost": (1.0, 1.0),
    "dirt": (0.7, 0.8),
    "grass": (0.45, 0.55),
    "oil": (0.12, 1.0),
}
DEFAULT_SURFACE = "road"
# the names the ground of a pack may have (its `surface:<name>` tag or a tile's `footstep`)
SURFACE_NAMES: dict[str, str] = {
    "asphalt": "road",
    "tarmac": "road",
    "stone": "road",
    "wood": "road",
    "metal": "road",
    "sand": "dirt",
    "gravel": "dirt",
    "mud": "dirt",
    "snow": "dirt",
    "water": "oil",
    "ice": "oil",
}

TOP = 12.0  # tiles a second
ACCEL = 9.0  # tiles a second, every second
BRAKE = 22.0
DRAG = 5.0  # rolling out with nothing held
REVERSE = 0.4  # of the top speed
OVERSPEED = 14.0  # how fast a car that is over its top speed (grass, the end of a boost) slows
TURN_SLOW = 3.4  # rad a second, at walking pace
TURN_FAST = 1.9  # at the top speed
TURN_FROM = 0.8  # tiles a second: below this a car turns less, and not at all standing
TRACTION = 16.0  # tiles a second, every second: how fast sideways speed fades at full grip
DRIFT_FROM = 0.18  # of the top speed, sideways: from here on the car drifts
BOUNCE = 0.3  # how much of the speed into a barrier comes back out
SCRAPE = 0.75  # how much of the speed along a barrier is kept
BOOST_TOP = 1.5
BOOST_ACCEL = 3.0
BOOST_S = 1.5
STEER_FULL = 0.5  # rad off the wanted heading at which absolute steering steers all the way
LEAD = 0.25  # of the screen: how far the camera looks ahead at the top speed
ZOOM_FAR = 0.85  # the camera's zoom at the top speed (1 standing)


def surface(name: str) -> str:
    """The surface of the car's model for the name the ground has."""
    key = str(name).strip().lower()
    if key in SURFACES:
        return key
    return SURFACE_NAMES.get(key, DEFAULT_SURFACE)


def grip(name: str) -> float:
    return SURFACES[surface(name)][0]


def top_speed(name: str, boosting: bool = False, top: float = TOP) -> float:
    """The speed a car gets to on a surface."""
    return top * SURFACES[surface(name)][1] * (BOOST_TOP if boosting else 1.0)


def move_toward(value: float, to: float, step: float) -> float:
    if abs(to - value) <= step:
        return to
    return value + math.copysign(step, to - value)


def accelerate(
    speed: float,
    throttle: float,
    limit: float,
    delta: float,
    boosting: bool = False,
    accel: float = ACCEL,
    brake: float = BRAKE,
) -> float:
    """The speed along the heading after ``delta`` s. ``throttle`` is 1 for the pedal, -1 for
    the brake (which reverses a car that stands), 0 for neither; ``limit`` the top speed where
    the car is."""
    throttle = max(-1.0, min(1.0, throttle))
    push = accel * (BOOST_ACCEL if boosting else 1.0)
    if speed > limit:  # too fast for where it is: it slows whatever is held
        return max(limit, speed - max(OVERSPEED, brake if throttle < 0.0 else 0.0) * delta)
    if throttle > 0.0:
        if speed < 0.0:
            return min(0.0, speed + brake * throttle * delta)
        return min(limit, speed + push * throttle * delta)
    if throttle < 0.0:
        if speed > 0.0:
            return max(0.0, speed + brake * throttle * delta)
        return max(-limit * REVERSE, speed + accel * throttle * delta)
    return move_toward(speed, 0.0, DRAG * delta)


def turn_rate(speed: float, top: float = TOP) -> float:
    """How fast the car turns with the wheel all the way over, in rad a second: fast when it
    is slow, slower at speed, not at all when it stands, and the other way round in reverse."""
    pace = abs(speed)
    rate = TURN_SLOW + (TURN_FAST - TURN_SLOW) * min(1.0, pace / top if top > 0.0 else 0.0)
    rate *= min(1.0, pace / TURN_FROM)
    return -rate if speed < 0.0 else rate


def turn(
    heading: float, speed: float, steer: float, surface_name: str, delta: float, top: float = TOP
) -> float:
    """The heading after ``delta`` s with the wheel at ``steer`` (-1 left to 1 right). On a
    surface with little grip the wheel does less."""
    steer = max(-1.0, min(1.0, steer))
    bite = min(1.0, 0.25 + grip(surface_name))
    return heading + steer * turn_rate(speed, top) * bite * delta


def slide(lateral: float, surface_name: str, delta: float, grip_mul: float = 1.0) -> float:
    """The speed sideways to the heading after ``delta`` s: it fades with the grip (better
    tyres, ``grip_mul`` over 1, take it away faster)."""
    return move_toward(lateral, 0.0, TRACTION * grip(surface_name) * grip_mul * delta)


def is_drifting(lateral: float, top: float = TOP) -> bool:
    return abs(lateral) > DRIFT_FROM * top


def split(vx: float, vy: float, heading: float) -> tuple[float, float]:
    """A velocity as (speed along the heading, speed to its right)."""
    c, s = math.cos(heading), math.sin(heading)
    return vx * c + vy * s, -vx * s + vy * c


def join(forward: float, lateral: float, heading: float) -> tuple[float, float]:
    """The velocity of a speed along the heading and one to its right."""
    c, s = math.cos(heading), math.sin(heading)
    return forward * c - lateral * s, forward * s + lateral * c


def bump(vx: float, vy: float, nx: float, ny: float) -> tuple[float, float]:
    """The velocity after hitting something whose surface faces (nx, ny): what went into it
    comes back weaker, what went along it is slowed."""
    into = vx * nx + vy * ny
    if into >= 0.0:
        return vx, vy
    ax, ay = vx - into * nx, vy - into * ny
    return ax * SCRAPE - into * BOUNCE * nx, ay * SCRAPE - into * BOUNCE * ny


PART_STEP = {"speed": 0.04, "acceleration": 0.08, "tyres": 0.08}  # what a level of a part adds
PART_LEVELS = 3


def part_factor(part: str, level: int) -> float:
    """What a car's top speed, acceleration or grip is multiplied by with ``level`` of the
    part (``speed``, ``acceleration``, ``tyres``): 1 without it, more for each of three."""
    return 1.0 + PART_STEP.get(part, 0.0) * max(0, min(PART_LEVELS, int(level)))


def step(
    state: dict[str, float],
    throttle: float,
    steer: float,
    surface_name: str,
    delta: float,
    top: float = TOP,
    accel: float = ACCEL,
    grip_mul: float = 1.0,
) -> dict[str, float]:
    """One step of a car that meets nothing: ``state`` is x, y, heading, vx, vy and boost (the
    seconds of boost left); the result is the same a step later, with ``lateral``. ``top``,
    ``accel`` and ``grip_mul`` are the car's own (its parts)."""
    boosting = state.get("boost", 0.0) > 0.0
    heading = state["heading"]
    forward, _side = split(state["vx"], state["vy"], heading)
    heading = turn(heading, forward, steer, surface_name, delta, top)
    forward, lateral = split(state["vx"], state["vy"], heading)
    limit = top_speed(surface_name, boosting, top)
    forward = accelerate(forward, throttle, limit, delta, boosting, accel)
    lateral = slide(lateral, surface_name, delta, grip_mul)
    vx, vy = join(forward, lateral, heading)
    return {
        "x": state["x"] + vx * delta,
        "y": state["y"] + vy * delta,
        "heading": heading,
        "vx": vx,
        "vy": vy,
        "boost": max(0.0, state.get("boost", 0.0) - delta),
        "lateral": lateral,
    }


def heading_frame(heading: float, count: int) -> int:
    """The frame of a sheet of ``count`` headings for a heading: the first frame points up,
    each next one a step clockwise (``heading_order: up_cw``)."""
    if count <= 1:
        return 0
    turned = (heading + math.pi * 0.5) / (math.tau / count)
    return int(math.floor(turned + 0.5)) % count


def angle_difference(a: float, b: float) -> float:
    """The shortest way from angle ``a`` to ``b``, from -pi to pi."""
    return (b - a + math.pi) % math.tau - math.pi


def steer_toward(heading: float, wanted: float) -> float:
    """The wheel for *absolute* steering: toward the heading the stick points to."""
    return max(-1.0, min(1.0, angle_difference(heading, wanted) / STEER_FULL))


def look_ahead(vx: float, vy: float, view: float, top: float = TOP) -> tuple[float, float]:
    """How far from the car the camera looks, along the car's velocity: ``LEAD`` of the
    screen (``view`` px) at the top speed (velocities in tiles a second)."""
    pace = math.hypot(vx, vy)
    if pace <= 0.0 or top <= 0.0:
        return 0.0, 0.0
    reach = view * LEAD * min(1.0, pace / top)
    return vx / pace * reach, vy / pace * reach


def zoom_for(pace: float, top: float = TOP) -> float:
    """The camera's zoom at a speed: 1 standing, ``ZOOM_FAR`` at the top speed and beyond."""
    part = min(1.0, abs(pace) / top) if top > 0.0 else 0.0
    return 1.0 + (ZOOM_FAR - 1.0) * part


def curve_speed(radius: float, surface_name: str = "road") -> float:
    """The speed (tiles a second) at which a curve of ``radius`` tiles can be taken without
    sliding: where the sideways speed a turn makes is no more than the grip takes away."""
    if radius <= 0.0:
        return 0.0
    return min(top_speed(surface_name), math.sqrt(TRACTION * grip(surface_name) * radius))


# --------------------------------------------------------------------------- the shared table

CASES_FILE = "godot_templates/tests/unit/car_math_cases.json"


def _r(value: float) -> float:
    return round(float(value), 6)


def cases() -> list[dict[str, Any]]:
    """Inputs and results of every function, for the GDScript mirror to be tested against."""
    out: list[dict[str, Any]] = []

    def add(fn: str, args: list[Any], result: Any) -> None:
        if isinstance(result, tuple):
            result = [_r(v) for v in result]
        elif isinstance(result, float):
            result = _r(result)
        out.append({"fn": fn, "args": args, "result": result})

    for name in ("road", "dirt", "grass", "oil", "boost", "asphalt", "sand", "ice", "", "lava"):
        add("surface", [name], surface(name))
        add("grip", [name], grip(name))
        add("top_speed", [name, False], top_speed(name, False))
        add("top_speed", [name, True], top_speed(name, True))
    for speed in (0.0, 3.0, 11.9, 12.0, 15.0, -2.0, -4.8):
        for throttle in (1.0, 0.5, 0.0, -1.0):
            for limit in (12.0, 6.6):
                for boosting in (False, True):
                    add(
                        "accelerate",
                        [speed, throttle, limit, 0.05, boosting],
                        accelerate(speed, throttle, limit, 0.05, boosting),
                    )
    for speed in (0.0, 0.4, 0.8, 3.0, 6.0, 12.0, 18.0, -3.0):
        add("turn_rate", [speed], turn_rate(speed))
        for name in ("road", "grass", "oil"):
            add("turn", [1.0, speed, -0.7, name, 0.05], turn(1.0, speed, -0.7, name, 0.05))
    for lateral in (0.0, 0.2, 3.0, -5.0):
        for name in ("road", "grass", "oil"):
            add("slide", [lateral, name, 0.05], slide(lateral, name, 0.05))
        add("is_drifting", [lateral], is_drifting(lateral))
        add("slide_tuned", [lateral, "grass", 0.05, 1.24], slide(lateral, "grass", 0.05, 1.24))
    for part in ("speed", "acceleration", "tyres", "paint"):
        for level in (0, 1, 3, 7):
            add("part_factor", [part, level], part_factor(part, level))
    for heading in (0.0, 0.7, -2.0, 3.0):
        add("split", [4.0, -3.0, heading], split(4.0, -3.0, heading))
        add("join", [6.0, 1.5, heading], join(6.0, 1.5, heading))
    for vx, vy, nx, ny in (
        (8.0, 0.0, -1.0, 0.0),
        (6.0, 6.0, 0.0, -1.0),
        (-3.0, 2.0, -1.0, 0.0),
        (5.0, -5.0, -0.6, 0.8),
    ):
        add("bump", [vx, vy, nx, ny], bump(vx, vy, nx, ny))
    for count in (16, 8, 4, 1):
        for k in range(-3, 20):
            heading = k * 0.37 - 1.0
            add("heading_frame", [_r(heading), count], heading_frame(_r(heading), count))
    for k in range(16):  # every heading of a sheet of sixteen has its own frame
        heading = _r(-math.pi * 0.5 + k * math.tau / 16)
        add("heading_frame", [heading, 16], heading_frame(heading, 16))
    for a, b in ((0.0, 1.0), (3.0, -3.0), (-3.0, 3.0), (1.0, 1.2), (0.5, -2.0)):
        add("angle_difference", [a, b], angle_difference(a, b))
        add("steer_toward", [a, b], steer_toward(a, b))
    for vx, vy in ((0.0, 0.0), (6.0, 0.0), (0.0, -12.0), (9.0, 12.0)):
        add("look_ahead", [vx, vy, 640.0], look_ahead(vx, vy, 640.0))
        add("zoom_for", [_r(math.hypot(vx, vy))], zoom_for(_r(math.hypot(vx, vy))))
    for radius in (0.0, 1.0, 3.0, 8.0):
        for name in ("road", "grass"):
            add("curve_speed", [radius, name], curve_speed(radius, name))
    # a drive: a car that starts, turns hard at speed over grass and oil, with a boost
    state = {"x": 0.0, "y": 0.0, "heading": -math.pi * 0.5, "vx": 0.0, "vy": 0.0, "boost": 0.0}
    drive: list[list[Any]] = []
    plan = [(60, 1.0, 0.0, "road"), (30, 1.0, 1.0, "road"), (30, 1.0, -1.0, "grass"),
            (20, 0.0, 1.0, "oil"), (30, -1.0, 0.0, "road"), (30, -1.0, 0.3, "road")]  # fmt: skip
    for n, (frames, throttle, steer, name) in enumerate(plan):
        if n == 1:
            state["boost"] = BOOST_S
        for _ in range(frames):
            state = step(state, throttle, steer, name, 1.0 / 60.0)
        drive.append(
            [frames, throttle, steer, name, n == 1]
            + [_r(state[k]) for k in ("x", "y", "heading", "vx", "vy", "lateral")]
        )
    out.append({"fn": "drive", "args": [], "result": drive})
    # the same drive with every part at its third level
    tuned = [TOP * part_factor("speed", 3), ACCEL * part_factor("acceleration", 3)]
    tuned.append(part_factor("tyres", 3))
    state = {"x": 0.0, "y": 0.0, "heading": -math.pi * 0.5, "vx": 0.0, "vy": 0.0, "boost": 0.0}
    legs: list[list[Any]] = []
    for frames, throttle, steer, name in plan:
        for _ in range(frames):
            state = step(state, throttle, steer, name, 1.0 / 60.0, *tuned)
        legs.append(
            [frames, throttle, steer, name, False]
            + [_r(state[k]) for k in ("x", "y", "heading", "vx", "vy", "lateral")]
        )
    out.append({"fn": "drive_tuned", "args": [_r(v) for v in tuned], "result": legs})
    return out


def write_cases(repo: Path) -> Path:
    path = repo / CASES_FILE
    path.write_text(json.dumps(cases(), indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":  # pragma: no cover
    print(write_cases(Path(__file__).resolve().parents[2]))
