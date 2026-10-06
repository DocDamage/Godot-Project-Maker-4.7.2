from __future__ import annotations

import copy
from typing import Any

import pytest

from rpggen import schema

H = "a" * 64

CONFIG: dict[str, Any] = {
    "config_version": 1,
    "generator_version": "0.1.0",
    "godot_version": "4.7.2",
    "project_name": "Demo",
    "archetype": "turn_based",
    "packs": [{"pack_id": "basic16", "source": "C:/p", "source_sha256": H, "kind": "folder"}],
    "base_tile_size": 16,
    "resolution": [640, 360],
    "window_size": [1280, 720],
    "map_layers": ["Ground", "GroundDetails", "Walls", "Props", "Overhead"],
    "features": {"tilesets": True, "navigation": False},
    "validation": {"smoke_test": True},
    "seed": 12345,
    "input": {
        "move_up": {"keys": ["W", "Up"], "joy_buttons": [11], "joy_axes": [[1, -1.0]]},
        "attack": {"keys": ["J"], "mouse_buttons": [1], "joy_buttons": [2]},
    },
}

INVENTORY: dict[str, Any] = {
    "inventory_version": 1,
    "pack_id": "forest_pack",
    "source_sha256": H,
    "files": [
        {
            "path": "Tilesets/grass.png",
            "sha256": H,
            "size": 4210,
            "ext": ".png",
            "kind": "image",
            "image": {"w": 256, "h": 128, "mode": "RGBA", "has_alpha": True, "frames": 1},
        },
        {"path": "LICENSE.txt", "sha256": H, "size": 812, "ext": ".txt", "kind": "license"},
    ],
    "skipped": [{"path": "__MACOSX/._grass.png", "reason": "os_junk"}],
}

FACETS: dict[str, Any] = {
    "role": "GROUND",
    "usage": "tiles",
    "grid": {"cell": [16, 16], "margin": [0, 0], "separation": [0, 0]},
    "tileset": "overworld",
    "collision": {"profile": "NONE"},
    "tile_overrides": {"0,1": {"collision": {"profile": "FULL"}, "skip": False}},
    "animations": {"walk_down": {"frames": [[0, 0], [1, 0]], "fps": 8.0, "loop": True}},
    "tags": ["chest"],
}

CATALOG: dict[str, Any] = {
    "catalog_version": 2,
    "generator_version": "0.1.0",
    "packs": [
        {
            "pack_id": "forest_pack",
            "source_sha256": H,
            "root": "assets/packs/forest_pack",
            "license_files": ["assets/packs/forest_pack/LICENSE.txt"],
            "adapters_matched": ["tiled", "generic_grid"],
            "profile_id": None,
            "warnings": ["rpgmaker_rtp_detected"],
        }
    ],
    "assets": [
        {
            "id": "forest_pack.tilesets.grass",
            "pack_id": "forest_pack",
            "path": "assets/packs/forest_pack/Tilesets/grass.png",
            "sha256": H,
            "kind": "image",
            "status": "AUTO_DETECTED",
            "detected": FACETS,
            "overrides": {"role": "WALL", "collision": None},
            "detected_by": "generic_grid",
            "confidence": 0.94,
        }
    ],
    "objects": [
        {
            "id": "forest_pack.tilesets.town#house_red",
            "sheet": "forest_pack.tilesets.town",
            "name": "House (red)",
            "role": "BUILDING",
            "region": [0, 64, 80, 64],
            "origin": [40, 63],
            "footprint": [0, 40, 80, 24],
            "collision": {
                "profile": "CUSTOM",
                "polygon": [[0, 40], [80, 40], [80, 64], [0, 64]],
            },
            "tags": ["door"],
            "door": [36, 63],
            "status": "CONFIRMED",
            "source": "user",
        }
    ],
    "tilesets": [
        {
            "name": "overworld",
            "tile_size": [16, 16],
            "sources": [{"asset": "forest_pack.tilesets.grass", "source_id": 0}],
            "terrain_sets": [
                {
                    "name": "ground",
                    "mode": "corners_and_sides",
                    "terrains": [{"name": "grass", "color": "#4caf50"}],
                }
            ],
            "physics_layers": [{"name": "world", "layer_bits": 1, "mask_bits": 0}],
            "custom_data": [
                {"name": "asset_id", "type": "string"},
                {"name": "move_cost", "type": "float"},
            ],
            "navigation": False,
            "patterns_from_objects": True,
        }
    ],
    "id_allocations": {
        "tilesets": {"overworld": {"next_source_id": 3, "retired": [1]}},
        "entities": {"starter_map": {"npc": 2, "enemy": 1, "chest": 1}},
    },
    "folder_rules": [
        {"pack_id": "forest_pack", "glob": "Characters/Enemies/**", "set": {"role": "ENEMY"}}
    ],
}

LEDGER: dict[str, Any] = {
    "ledger_version": 1,
    "generator_version": "0.1.0",
    "files": {
        "generated/scenes/actors/player.tscn": {
            "sha256": H,
            "written_by": "player_recipe",
            "owner": "generated",
        },
        "game/maps/starter_map.tscn": {
            "sha256": H,
            "written_by": "starter_map_recipe",
            "owner": "user_seed",
        },
    },
    "deleted_by_user": ["generated/scenes/objects/old_sign.tscn"],
}

PROFILE: dict[str, Any] = {
    "profile_version": 1,
    "profile_id": "vendor_forest_v2",
    "title": "Forest Pack v2 by Vendor",
    "fingerprint": {"required_files": {"Tilesets/grass.png": H}, "min_match": 0.8},
    "assets": {"Tilesets/grass.png": {"role": "GROUND"}},
    "objects": [
        {
            "sheet_path": "Tilesets/town.png",
            "name": "House",
            "role": "BUILDING",
            "region": [0, 64, 80, 64],
            "origin": [40, 63],
            "footprint": [0, 40, 80, 24],
            "collision": {"profile": "FULL"},
            "tags": [],
            "status": "CONFIRMED",
            "source": "user",
        }
    ],
    "folder_rules": [{"pack_id": "x", "glob": "a/**", "set": {"role": "NPC"}}],
    "tilesets": [
        {
            "name": "overworld",
            "tile_size": [16, 16],
            "sources": [{"asset": "forest_pack.tilesets.grass"}],
            "physics_layers": [],
            "custom_data": [],
        }
    ],
    "author": "someone",
    "license": "CC0-1.0",
}

RESULTS: dict[str, Any] = {
    "results_version": 1,
    "phase": "build",
    "ok": True,
    "started_ms": 0,
    "elapsed_ms": 18234,
    "issues": [{"code": "TILE-003", "severity": "warning", "message": "m", "file": "f"}],
    "items": [
        {
            "recipe": "tileset_recipe",
            "output": "generated/tilesets/overworld.tres",
            "action": "written",
        }
    ],
}

EXAMPLES: dict[str, dict[str, Any]] = {
    "config": CONFIG,
    "inventory": INVENTORY,
    "catalog": CATALOG,
    "ledger": LEDGER,
    "profile": PROFILE,
    "results": RESULTS,
}


@pytest.mark.parametrize("kind", sorted(EXAMPLES))
def test_valid_example_passes(kind: str) -> None:
    schema.validate(kind, EXAMPLES[kind])


@pytest.mark.parametrize("kind", sorted(EXAMPLES))
def test_missing_required_field_fails(kind: str) -> None:
    optional = {"author", "license"}
    for key in list(EXAMPLES[kind]):
        if key in optional:
            continue
        bad = copy.deepcopy(EXAMPLES[kind])
        del bad[key]
        with pytest.raises(ValueError, match=kind):
            schema.validate(kind, bad)


@pytest.mark.parametrize("kind", sorted(EXAMPLES))
def test_unknown_field_fails(kind: str) -> None:
    bad = copy.deepcopy(EXAMPLES[kind])
    bad["surprise"] = 1
    with pytest.raises(ValueError):
        schema.validate(kind, bad)


def test_enum_violations() -> None:
    bad = copy.deepcopy(CATALOG)
    bad["assets"][0]["status"] = "WHATEVER"
    with pytest.raises(ValueError, match="/assets/0/status"):
        schema.validate("catalog", bad)
    bad = copy.deepcopy(CONFIG)
    bad["base_tile_size"] = 15
    with pytest.raises(ValueError):
        schema.validate("config", bad)


def test_config_map_layers_must_contain_ground() -> None:
    bad = copy.deepcopy(CONFIG)
    bad["map_layers"] = ["Walls"]
    with pytest.raises(ValueError):
        schema.validate("config", bad)


def test_custom_collision_requires_polygon() -> None:
    bad = copy.deepcopy(CATALOG)
    bad["objects"][0]["collision"] = {"profile": "CUSTOM"}
    with pytest.raises(ValueError):
        schema.validate("catalog", bad)


def test_unknown_kind() -> None:
    with pytest.raises(KeyError):
        schema.validate("nope", {})
