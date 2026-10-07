from __future__ import annotations

from pathlib import Path

from PIL import Image

from rpggen.core import map_preview


def _project(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    for x in range(16):
        for y in range(16):
            sheet.putpixel((x, y), (10, 200, 10, 255))  # tile (0, 0): green
            sheet.putpixel((16 + x, y), (200, 10, 10, 255))  # tile (1, 0): red
    sheet.save(tmp_path / "assets" / "tiles.png")
    sprite = Image.new("RGBA", (16, 24), (0, 0, 255, 255))
    sprite.save(tmp_path / "assets" / "hero.png")
    return tmp_path


def _view() -> dict:
    return {
        "tile_size": [16, 16],
        "sources": {
            "0": {
                "path": "res://assets/tiles.png",
                "region_size": [16, 16],
                "margins": [0, 0],
                "separation": [0, 0],
            }
        },
        "layers": [
            {
                "name": "Ground",
                "z": 0,
                "cells": [[x, y, 0, 0, 0] for x in range(4) for y in range(3)],
            },
            {"name": "Walls", "z": 0, "cells": [[0, 0, 0, 1, 0]]},
        ],
        "entities": [
            {
                "name": "Hero",
                "scene": "res://generated/scenes/actors/player.tscn",
                "entity_id": "",
                "x": 40.0,
                "y": 40.0,
                "sprite": {
                    "path": "res://assets/hero.png",
                    "region": [0, 0, 16, 24],
                    "offset": [-8, -23],
                },
            },
            {
                "name": "Slime",
                "scene": "res://x/enemy_slime.tscn",
                "entity_id": "e1",
                "x": 8.0,
                "y": 24.0,
                "sprite": {},
            },
        ],
    }


def test_cells_are_cut_from_the_project_atlas_and_entities_are_drawn(tmp_path: Path) -> None:
    image = map_preview.render_view(_view(), _project(tmp_path), scale=1)
    assert image.size == (64, 48)
    assert image.getpixel((55, 20))[:3] == (10, 200, 10)  # a ground tile
    assert image.getpixel((2, 2))[:3] == (200, 10, 10)  # the wall tile painted on top at (0, 0)
    assert image.getpixel((40, 30))[:3] == (
        0,
        0,
        255,
    )  # the hero's picture above its feet at (40, 40)
    assert image.getpixel((8, 16))[:3] == (229, 57, 53)  # an enemy without a picture: a red marker


def test_scale_doubles_the_picture(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert map_preview.render_view(_view(), root, scale=2).size == (128, 96)


def test_a_missing_atlas_does_not_stop_the_picture(tmp_path: Path) -> None:
    view = _view()
    view["sources"]["0"]["path"] = "res://assets/gone.png"
    image = map_preview.render_view(view, _project(tmp_path), scale=1)
    assert image.size == (64, 48)
