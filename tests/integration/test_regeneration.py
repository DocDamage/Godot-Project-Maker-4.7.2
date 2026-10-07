"""Milestone M5: the three regeneration invariants, on the sample pack with real Godot.

1. Tile invariant: painted cells never change.
2. Ownership invariant: nothing the user owns or modified is touched.
3. Atomicity invariant: a failed generation leaves the target byte-identical.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from rpggen import jsonio, paths
from rpggen.core import (
    archive,
    catalog,
    config,
    godot,
    inventory,
    mapping,
    orchestrator,
    profiles,
    promote,
    vcs,
)

pytestmark = pytest.mark.integration

SAMPLE = Path(__file__).resolve().parents[2] / "sample_pack"
# .git/ is left out: git may repack in the background; vcs.is_clean checks the repository
SKIPPED_DIRS = (".git/", ".godot/", ".rpggen_failed/", ".rpggen_staging/", ".rpggen_backups/")
VOLATILE = (
    "rpggen/logs/",
    "rpggen/results/",
    "GENERATION_REPORT.md",
    "rpggen/generation_report.json",
)

PAINT_SCRIPT = """extends SceneTree
func _find(node: Node, out: Array) -> void:
	if node is TileMapLayer:
		out.append(node)
	for child in node.get_children():
		_find(child, out)

func _initialize() -> void:
	var path := "res://game/maps/starter_map.tscn"
	var packed := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	var root := packed.instantiate(PackedScene.GEN_EDIT_STATE_MAIN)
	var layers: Array = []
	_find(root, layers)
	var painted := 0
	for layer in layers:
		var ts: TileSet = layer.tile_set
		if ts == null or ts.get_source_count() == 0:
			continue
		var source_id := ts.get_source_id(0)
		var coords := (ts.get_source(source_id) as TileSetAtlasSource).get_tile_id(0)
		for i in 12:
			layer.set_cell(Vector2i(28 + i % 6, 16 + i / 6), source_id, coords)
			painted += 1
	var out := PackedScene.new()
	out.pack(root)
	var err := ResourceSaver.save(out, path)
	print("painted %d cells, save error %d" % [painted, err])
	quit(0 if err == OK and painted >= 50 else 1)
"""


@pytest.fixture(scope="module", autouse=True)
def _profile(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(tmp_path_factory.mktemp("cache"))
    try:
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        yield
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


# --------------------------------------------------------------------------- helpers


def _make_pack(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(SAMPLE, pack)
    return pack


def _generate(exe: Path, pack: Path, target: Path, git_message: str | None = None):
    opened = archive.open_pack(pack, set(), pack_id="sample_pack")
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for("Sample RPG", [config.pack_ref_from_source(pack, "sample_pack")])
    cfg.starter = mapping.default_starter(cat, "turn_based")
    result = orchestrator.run_in_memory(cfg, None, target, exe, git_message=git_message)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    return result


def _regenerate(exe: Path, target: Path):
    return orchestrator.run(target / paths.CONFIG, target, exe, force_while_open=True)


def _codes(result) -> list[str]:
    return [i.code for i in result.issues]


def _snapshot(target: Path, volatile: bool = False) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(target.rglob("*")):
        rel = p.relative_to(target).as_posix()
        if not p.is_file() or rel.startswith(SKIPPED_DIRS):
            continue
        if volatile and rel.startswith(VOLATILE):
            continue
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _stable(target: Path) -> dict[str, str]:
    return _snapshot(target, volatile=True)


def _diff(a: dict[str, str], b: dict[str, str]) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _godot(exe: Path, target: Path, args: list[str], log_name: str) -> godot.GodotRun:
    run = godot.run_godot(
        godot.find_console_exe(exe),
        target,
        args,
        timeout_s=godot.BUILD_TIMEOUT_S,
        log_name=log_name,
        log_dir=target.parent / "tool_logs",
    )
    assert run.returncode == 0, run.stdout + run.stderr
    return run


def _dump_cells(exe: Path, target: Path) -> dict[str, Any]:
    out = target.parent / "cells.json"
    out.unlink(missing_ok=True)
    _godot(
        exe,
        target,
        ["--script", "res://generated/builder/tools/dump_map_cells.gd", "--", f"--out={out}"],
        "dump_cells",
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data, "no maps were dumped"
    return data  # type: ignore[no-any-return]


def _cell_count(cells: dict[str, Any]) -> int:
    return sum(len(c) for layers in cells.values() for c in layers.values())


def _tweak_png(path: Path) -> None:
    """Same size, different pixels."""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        for x in range(0, min(6, img.width)):
            img.putpixel((x, 1), (255, 0, 255, 255))
        img.save(path)


def _tileset_text(target: Path) -> str:
    """The TileSet file with Godot's random sub-resource ids (patterns) normalized."""
    text = (target / "generated/tilesets/overworld.tres").read_text(encoding="utf-8")
    return re.sub(r"(TileMapPattern|TileSetAtlasSource)_[0-9a-z]{5}", r"_x", text)


# --------------------------------------------------------------------------- scenarios


def test_1_noop_regeneration_changes_nothing(godot_exe: Path, tmp_path: Path) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(
        godot_exe, pack, target, git_message="first generation" if vcs.git_available() else None
    )
    before = _stable(target)
    result = _regenerate(godot_exe, target)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert _diff(before, _stable(target)) == []
    assert not (target / ".rpggen_backups").exists(), "a run with no changes makes no backup"
    if vcs.git_available():
        assert vcs.is_clean(target), "git status must be empty after a no-op regeneration"


def test_2_user_paint_and_files_survive(godot_exe: Path, tmp_path: Path) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(godot_exe, pack, target)
    before_cells = _dump_cells(godot_exe, target)
    script = tmp_path / "paint.gd"
    script.write_text(PAINT_SCRIPT, encoding="utf-8", newline="\n")
    _godot(godot_exe, target, ["--script", str(script)], "paint")
    painted = _dump_cells(godot_exe, target)
    assert _cell_count(painted) >= _cell_count(before_cells) + 50 - 20  # some cells overlap
    mine = target / "game/scripts/my_thing.gd"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text("extends Node\n\nvar mine := true\n", encoding="utf-8", newline="\n")
    my_hash = hashlib.sha256(mine.read_bytes()).hexdigest()
    game_before = {k: v for k, v in _snapshot(target).items() if k.startswith("game/")}

    result = _regenerate(godot_exe, target)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert _dump_cells(godot_exe, target) == painted, "tile invariant"
    assert hashlib.sha256(mine.read_bytes()).hexdigest() == my_hash
    game_after = {k: v for k, v in _snapshot(target).items() if k.startswith("game/")}
    for rel, digest in game_before.items():
        assert game_after.get(rel) == digest, f"{rel} changed"  # ownership invariant


def test_3_user_edited_generated_scene_is_not_overwritten(godot_exe: Path, tmp_path: Path) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(godot_exe, pack, target)
    index = jsonio.read(target / "rpggen/object_index.json")
    rel = index["sample_pack.objects.town#tree_1"].removeprefix("res://")
    scene = target / rel
    text = scene.read_text(encoding="utf-8")
    first_node = text.index("[node ")
    eol = text.index("\n", first_node) + 1
    edited = text[:eol] + 'metadata/user_note = "mine"\n' + text[eol:]
    scene.write_text(edited, encoding="utf-8", newline="\n")
    # the user (or the audit) also changes the object's footprint in the catalog
    cat_path = target / paths.CATALOG
    cat = catalog.load(cat_path)
    tree = next(o for o in cat.objects if o.id == "sample_pack.objects.town#tree_1")
    tree.footprint = [
        tree.footprint[0],
        tree.footprint[1],
        tree.footprint[2] + 2,
        tree.footprint[3],
    ]
    tree.source = "user"
    catalog.save(cat, cat_path)

    result = _regenerate(godot_exe, target)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert scene.read_text(encoding="utf-8") == edited, "the user's file was not overwritten"
    assert (target / (rel + ".rpggen-new")).is_file()
    assert "REGEN-001" in _codes(result)
    new_text = (target / (rel + ".rpggen-new")).read_text(encoding="utf-8")
    assert "user_note" not in new_text and new_text != text


def test_4_pack_update_keeps_cells_and_sources(godot_exe: Path, tmp_path: Path) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(godot_exe, pack, target)
    cells = _dump_cells(godot_exe, target)
    old_cat = catalog.load(target / paths.CATALOG)
    old_next = {
        name: entry["next_source_id"] for name, entry in old_cat.id_allocations["tilesets"].items()
    }
    water_id = next(
        s["source_id"]
        for t in old_cat.tilesets
        for s in t.sources
        if s["asset"] == "sample_pack.tilesets.water"
    )
    _tweak_png(pack / "tilesets/walls.png")  # same size, changed pixels
    extra = pack / "tilesets/ground_extra.png"  # a new sheet
    shutil.copyfile(pack / "tilesets/ground.png", extra)
    _tweak_png(extra)
    (pack / "tilesets/water.png").unlink()  # a removed sheet

    result = _regenerate(godot_exe, target)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert _dump_cells(godot_exe, target) == cells, "tile invariant"
    new_cat = catalog.load(target / paths.CATALOG)
    new_source = next(
        (t.name, s["source_id"])
        for t in new_cat.tilesets
        for s in t.sources
        if s["asset"] == "sample_pack.tilesets.ground_extra"
    )
    assert new_source[1] == old_next.get(new_source[0], 0), "the new source takes next_source_id"
    assert f"sources/{water_id} = " in _tileset_text(target), "the removed sheet's source stays"
    assert "REGEN-003" in _codes(result)
    assert (target / "assets/packs/sample_pack/tilesets/water.png").is_file()


def test_5_resized_sheet_is_a_conflict(godot_exe: Path, tmp_path: Path) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(godot_exe, pack, target)
    cells = _dump_cells(godot_exe, target)
    before = _tileset_text(target)
    walls = pack / "tilesets/walls.png"
    with Image.open(walls) as img:
        img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(walls)

    result = _regenerate(godot_exe, target)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    new_cat = catalog.load(target / paths.CATALOG)
    status = {a.id: a.status for a in new_cat.assets}
    assert status["sample_pack.tilesets.walls"] == "CONFLICT"
    assert "TILE-004" in _codes(result)
    assert _tileset_text(target) == before, "the conflicting source was left untouched"
    assert _dump_cells(godot_exe, target) == cells


def test_6_failed_generation_leaves_the_target_byte_identical(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(godot_exe, pack, target)
    _tweak_png(pack / "tilesets/ground.png")  # a real change for the failing run to apply
    before = _snapshot(target)
    monkeypatch.setenv("RPGGEN_DEV", "1")
    monkeypatch.setenv("RPGGEN_TEST_SABOTAGE", "broken_player")
    result = _regenerate(godot_exe, target)
    assert not result.ok
    assert result.failed_staging is not None and result.failed_staging.is_dir()
    assert _diff(before, _snapshot(target)) == [], "atomicity invariant"
    assert not (target / ".rpggen_staging").exists()


def test_7_restore_returns_to_the_previous_generation(godot_exe: Path, tmp_path: Path) -> None:
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    _generate(godot_exe, pack, target)
    before = _stable(target)
    _tweak_png(pack / "tilesets/ground.png")
    result = _regenerate(godot_exe, target)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert _diff(before, _stable(target)) != [], "the regeneration changed something"
    assert promote.list_backups(target), "a backup was made"
    promote.restore(target)
    assert _diff(before, _stable(target)) == []
