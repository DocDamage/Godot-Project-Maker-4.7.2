"""Write godot_templates/tests/fixtures/map_plan_cases.json: 20 option sets with the plan that
rpggen.core.map_preview.plan returns. The GDScript test of MapBuild.plan checks the same file, so
the two planners cannot drift apart.

It also writes room_plan_cases.json (T14.06): a few worlds of rooms as rpggen.core.room_plan
plans them. The rooms recipe has no planner of its own (it paints what the plan says), so these
are not compared against a second implementation: the GDScript tests build real rooms from them.

Usage: python tools/make_map_plan_cases.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from rpggen.core import config, map_preview, room_plan  # noqa: E402

OUT = REPO / "godot_templates" / "tests" / "fixtures" / "map_plan_cases.json"
BUILDINGS = {
    "none": {},
    "house": {"size": [5, 4], "door": [2, 4]},
    "big": {"size": [8, 6], "door": [4, 6]},
}

OVERRIDES: list[tuple[str, str, dict, int]] = [  # (archetype, building, options, seed)
    ("turn_based", "house", {}, 12345),
    ("arpg", "house", {}, 12345),
    ("turn_based", "none", {}, 12345),
    ("turn_based", "house", {"size": [32, 20]}, 12345),
    ("turn_based", "house", {"size": [64, 40], "buildings": 4}, 7),
    ("arpg", "house", {"size": [64, 40], "buildings": 4, "enemies": 8, "npcs": 6}, 99),
    ("turn_based", "house", {"buildings": 0}, 5),
    ("turn_based", "house", {"buildings": 2}, 5),
    ("turn_based", "big", {"buildings": 3, "size": [40, 24]}, 1),
    ("turn_based", "house", {"npcs": 0, "chests": 0, "enemies": 0}, 42),
    ("turn_based", "house", {"decorations": 40, "ground_patches": 20}, 2024),
    ("turn_based", "house", {"decorations": 0, "ground_patches": 0}, 2024),
    ("arpg", "none", {"size": [24, 24], "enemies": 4}, 77),
    ("turn_based", "house", {"chests": 4, "npcs": 6}, 31337),
    ("turn_based", "house", {"size": [96, 96], "buildings": 4, "decorations": 40}, 8),
    ("turn_based", "big", {"size": [24, 24], "buildings": 4}, 3),
    ("arpg", "house", {"enemies": 3}, 12345),
    ("turn_based", "house", {"ground_patches": 3}, 0),
    ("turn_based", "house", {"decorations": 9}, 12345),
    ("turn_based", "house", {"size": [40, 24], "ground_patches": 7}, 1),
]


def cases() -> list[dict]:
    out = []
    for archetype, building, overrides, seed in OVERRIDES:
        options = {**config.starter_map_defaults(archetype)}
        options.update({k: v for k, v in overrides.items() if k in options})
        out.append(
            {
                "archetype": archetype,
                "building": BUILDINGS[building],
                "options": options,
                "seed": seed,
                "plan": map_preview.plan(options, seed, BUILDINGS[building], archetype),
            }
        )
    return out


ROOMS_OUT = OUT.with_name("room_plan_cases.json")
ROOM_CASES: dict[str, tuple[dict, int]] = {  # name -> (options, seed)
    "default": ({}, 12345),
    "every_ability": ({"rooms": 9, "abilities": list(room_plan.ABILITIES)}, 7),
    "small": ({"rooms": 5, "abilities": [], "enemies": 0, "pickups": 0}, 3),
}


def room_cases() -> dict:
    """name -> the world plan file of a metroidvania made from those options."""
    return {
        name: room_plan.world(room_plan.plan(options, seed), seed)
        for name, (options, seed) in ROOM_CASES.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = json.dumps(cases(), indent=1, sort_keys=True) + "\n"
    rooms_text = json.dumps(room_cases(), indent=1, sort_keys=True) + "\n"
    if args.check:
        same = OUT.is_file() and OUT.read_text(encoding="utf-8") == text
        rooms_same = ROOMS_OUT.is_file() and ROOMS_OUT.read_text(encoding="utf-8") == rooms_text
        return 0 if same and rooms_same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    ROOMS_OUT.write_text(rooms_text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
    print(f"wrote {ROOMS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
