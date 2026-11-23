"""An assets-only project (T17.33): the packs' tile sets, the dock's scenes and the catalog, and no
game; and a short level made in it the way a user makes one, by the test-only editor plugin
tests/integration/level_probe (the Terrain tool's painting, the Assets dock's placing).

The sample packs of the repository stand for a pack seen from above (``sample_pack``) and one
seen from the side (``sample_pack_side``); ``sheet_things`` for a sheet of tiles holding the
things a level is furnished with."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from rpggen import jsonio
from rpggen.core import config, orchestrator, profiles

sys.path.insert(0, str(Path(__file__).resolve().parent))
import level_probe_run  # noqa: E402

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]


def _generate(godot_exe: Path, tmp_path: Path, pack: Path, name: str) -> orchestrator.RunResult:
    cfg = orchestrator.default_config_for_pack(pack, name, archetype="assets")
    cfg_path = tmp_path / f"{name}_cfg.json"
    config.save(cfg, cfg_path)
    result = orchestrator.run(cfg_path, tmp_path / name, godot_exe, derive_tile_size=True)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    return result


def _check_project(target: Path) -> dict:
    saved = jsonio.read(target / "rpggen/generator_config.json")
    assert saved["archetype"] == "assets" and saved["view"] in ("top", "side")
    assert list((target / "generated/tilesets").glob("*.tres")), "its tile sets"
    assert jsonio.read(target / "rpggen/object_index.json"), "things in the dock"
    assert not (target / "game/maps").exists(), "no maps"
    assert not (target / "generated/scenes/bootstrap/boot.tscn").exists(), "no boot scene"
    assert "run/main_scene" not in (target / "project.godot").read_text(encoding="utf-8")
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "## 2. A level" in readme and "Terrains" in readme
    return saved


def _check_level(report: dict) -> None:
    assert report["ok"], report.get("error")
    assert report["terrains"], "the ground is painted"
    for terrain in report["terrains"]:
        # the whole entry, not pytest's shortened dict: which terrain of which set left holes
        said = json.dumps({"terrain": terrain, "base": report.get("base")}, sort_keys=True)
        assert terrain["holes"] == 0, said
        assert terrain["wrong"] == 0, said  # every piece fits the cells around it
        if not terrain.get("strip"):
            assert terrain["main_share"] >= 0.7, terrain  # mostly the main tile
    assert len(report["places"]) >= 4, report["places"]
    for place in report["places"]:
        assert "error" not in place, place
        for sx, sy in place["scales"]:
            assert sx == int(sx) and sy == int(sy) and sx >= 1, place  # whole numbers
        assert all(f in (0, 1) for f in place["filters"]), place  # nearest (or the project's)
        assert place["parent"] == "Entities", place  # in the y-sorted holder


@pytest.fixture(autouse=True)
def _own_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test its own rpggen folders: the sample tests before these install the samples'
    profiles in the session's, and a profile read the sample otherwise (CI, 2026-10-25)."""
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "rpggen_home"))


@pytest.mark.parametrize("profile", [False, True], ids=["read", "profile"])
def test_an_assets_only_project_seen_from_above_and_a_level_made_in_it(
    godot_exe: Path, tmp_path: Path, profile: bool
) -> None:
    if profile:  # the sample as the wizard opens it: its profile installed
        profiles.install_profile(REPO / "sample_pack" / "sample.rpgprofile.json")
    result = _generate(godot_exe, tmp_path, REPO / "sample_pack", "Village Assets")
    saved = _check_project(result.target)
    assert saved["view"] == "top"
    assert (result.target / "generated/scenes/enemies").is_dir(), "the action RPG's enemies"
    assert not any(i.code == "ASSET-010" for i in result.issues), "nothing it lacks"
    assert any(i.code == "VAL-032" for i in result.issues), "no smoke run, said so"
    run = level_probe_run.make_level(result.target, tmp_path / "level", godot_exe)
    _check_level(run.report)
    assert run.report["view"] == "top_down"
    roles = {p["role"] for p in run.report["places"]}
    assert {"DECORATION", "NPC"} <= roles, roles


def test_an_assets_only_project_seen_from_the_side_and_a_level_made_in_it(
    godot_exe: Path, tmp_path: Path
) -> None:
    result = _generate(godot_exe, tmp_path, REPO / "sample_pack_side", "Side Assets")
    saved = _check_project(result.target)
    assert saved["view"] == "side", "decided from the pack"
    assert "jump" in saved["input"], "the side-view body jumps"
    tileset = next((result.target / "generated/tilesets").glob("*.tres")).read_text("utf-8")
    assert 'name = "ladder"' in tileset or "ladder" in tileset, "ladders as tile data"
    run = level_probe_run.make_level(result.target, tmp_path / "level", godot_exe)
    _check_level(run.report)
    assert run.report["view"] == "side"
    kinds = {s["kind"] for s in run.report["specials"]}
    assert {"one_way", "ladder"} <= kinds, kinds


def test_the_things_of_a_sheet_of_tiles_are_placed_from_the_dock(
    godot_exe: Path, tmp_path: Path
) -> None:
    pack = REPO / "test_packs" / "synthetic" / "sheet_things"
    result = _generate(godot_exe, tmp_path, pack, "Sheet Things")
    index = jsonio.read(result.target / "rpggen/object_index.json")
    assert len(index) == 4, index  # the rock, the bucket, the flower and the tree
    run = level_probe_run.make_level(result.target, tmp_path / "level", godot_exe)
    assert run.report["ok"], run.report.get("error")
    placed = [p for p in run.report["places"] if p["role"] == "DECORATION"]
    assert len(placed) == 4
    assert sum(1 for p in placed if p["shapes"] > 0) == 3, "all but the flower collide"


def test_corner_terrain_outer_edges_are_not_reported_as_bad_joins(
    godot_exe: Path, tmp_path: Path
) -> None:
    """A complete corner terrain: Tiled's zero corners are legal outside the painted area.

    The old judge required all four corners on every cell, falsely flagging the perimeter
    of LPC Floors despite Godot successfully painting its authored corner pieces.
    """
    pack = tmp_path / "Corner Floors"
    pack.mkdir()
    sheet = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(sheet)
    tiles = []
    for mask in range(16):
        x, y = (mask % 4) * 16, (mask // 4) * 16
        for bit, (dx, dy) in enumerate(((8, 0), (8, 8), (0, 8), (0, 0))):
            if mask & (1 << bit):
                draw.rectangle((x + dx, y + dy, x + dx + 7, y + dy + 7), fill=(90, 140, 80, 255))
        corners = [1 if mask & (1 << b) else 0 for b in range(4)]
        wang = ",".join(str(v) for c in corners for v in (0, c))
        tiles.append(f'<wangtile tileid="{mask}" wangid="{wang}"/>')
    sheet.save(pack / "floors.png")
    (pack / "floors.tsx").write_text(
        '<tileset name="floors" tilewidth="16" tileheight="16" columns="4" tilecount="16">'
        '<image source="floors.png" width="64" height="64"/>'
        '<wangsets><wangset name="floor" type="corner">'
        '<wangcolor name="grass" color="#5a8c50" tile="15"/>'
        + "".join(tiles)
        + "</wangset></wangsets></tileset>",
        encoding="utf-8",
    )
    result = _generate(godot_exe, tmp_path, pack, "Corner Edges")
    run = level_probe_run.make_level(result.target, tmp_path / "corner_level", godot_exe)
    assert run.report["ok"] and run.report["terrains"]
    for terrain in run.report["terrains"]:
        assert terrain["holes"] == 0 and terrain["wrong"] == 0, terrain


def test_the_dock_is_exercised_for_character_packs_without_ground(
    godot_exe: Path, tmp_path: Path
) -> None:
    pack = tmp_path / "Battlers"
    pack.mkdir()
    image = Image.new("RGBA", (512, 480))
    ImageDraw.Draw(image).ellipse((10, 8, 502, 470), fill=(160, 50, 30, 255))
    image.save(pack / "rtdragon1.png")
    result = _generate(godot_exe, tmp_path, pack, "Battler Assets")
    run = level_probe_run.make_level(result.target, tmp_path / "battler_level", godot_exe)
    assert run.report["ok"], run.report.get("error")
    assert run.report["terrains"] == []
    assert any(p["role"] == "ENEMY" for p in run.report["places"]), run.report
    shot = tmp_path / "battler.png"
    ok, log = level_probe_run.picture_level(run.project, godot_exe, shot)
    assert ok, log
    with Image.open(shot) as rendered:
        pixels = np.asarray(rendered.convert("RGB"), dtype=np.int16)
        red = (pixels[:, :, 0] > 2 * pixels[:, :, 1]) & (pixels[:, :, 0] > 2 * pixels[:, :, 2])
        assert red.any()
        assert not (red[0].any() or red[-1].any() or red[:, 0].any() or red[:, -1].any()), (
            "the camera must include the complete battler"
        )
