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

from rpggen import __version__ as rpggen_version
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


# --------------------------------------------------------------------------- git (T12.12)


def _git(folder: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=folder, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.mark.skipif(not vcs.git_available(), reason="git is not installed")
def test_a_regeneration_in_a_dirty_repository_commits_only_what_rpggen_wrote(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Dana")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dana@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Dana")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "dana@example.com")
    pack = _make_pack(tmp_path)
    target = tmp_path / "game"
    _generate(godot_exe, pack, target, git_message="rpggen: generate project")
    assert vcs.is_clean(target)
    # the user's own work: an untracked file and an edit of a file of theirs
    (target / "my_notes.txt").write_text("remember the boss fight\n", encoding="utf-8")
    tsv = target / "game" / "i18n" / "strings.tsv"
    tsv.write_text(tsv.read_text(encoding="utf-8") + "MY_KEY\tMine\n", encoding="utf-8")
    # the pack gets a new picture, so that a regeneration really writes something
    shutil.copy(next(pack.rglob("*.png")), pack / "brand_new.png")
    result = orchestrator.run(
        target / paths.CONFIG,
        target,
        godot_exe,
        git_message="rpggen: regenerate project",
        force_while_open=True,
    )
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert "REGEN-008" in _codes(result)  # the user's changes were left out, and the user is told
    assert _git(target, "log", "-1", "--format=%s") == "rpggen: regenerate project"
    committed = _git(target, "show", "--name-only", "--format=", "HEAD").split("\n")
    assert any(name.endswith("brand_new.png") for name in committed)
    assert "my_notes.txt" not in committed and "game/i18n/strings.tsv" not in committed
    status = _git(target, "status", "--porcelain")
    assert "my_notes.txt" in status and "strings.tsv" in status  # still the user's to commit


@pytest.mark.skipif(not vcs.git_available(), reason="git is not installed")
def test_the_ignore_choice_keeps_the_pack_art_out_of_the_first_commit(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Dana")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dana@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Dana")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "dana@example.com")
    pack = _make_pack(tmp_path)
    opened = archive.open_pack(pack, set(), pack_id="sample_pack")
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for("Sample RPG", [config.pack_ref_from_source(pack, "sample_pack")])
    cfg.starter = mapping.default_starter(cat, "turn_based")
    cfg.git = {"pack_art": "ignore"}
    target = tmp_path / "game"
    result = orchestrator.run_in_memory(
        cfg, None, target, godot_exe, git_message="rpggen: generate project"
    )
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert "assets/packs/" in (target / ".gitignore").read_text(encoding="utf-8").splitlines()
    tracked = _git(target, "ls-files").splitlines()
    assert tracked and not [name for name in tracked if name.startswith("assets/packs/")]
    assert (target / "assets" / "packs" / "sample_pack").is_dir()  # the art is there, untracked
    assert vcs.is_clean(target)


# --------------------------------------------------------------------------- T14.01: 1.1 -> 1.2

OLD_REFS = ("v1.1.0", "m13", "origin/m13")
OLD_COMBAT = "addons/rpg_runtime/archetypes/arpg"
NEW_COMBAT = "addons/rpg_runtime/combat/realtime"
MOVED_SCRIPTS = (
    "damage_info",
    "hitbox",
    "hurtbox",
    "health",
    "projectile",
    "state_machine",
    "pickup",
    "screen_feedback",
)

OLD_PATH_SCRIPT = """extends SceneTree
# A user's script written against 1.1: it names the combat scripts by their old paths.
const OldHitbox := preload("res://addons/rpg_runtime/archetypes/arpg/hitbox.gd")
const OldHealth := preload("res://addons/rpg_runtime/archetypes/arpg/health.gd")
const OldInfo := preload("res://addons/rpg_runtime/archetypes/arpg/damage_info.gd")

func _initialize() -> void:
	var hitbox: Area2D = OldHitbox.new()
	var health: Node = OldHealth.new()
	var info: RefCounted = OldInfo.new()
	var good := hitbox is RpgHitbox and health is RpgHealth and info is RpgDamageInfo
	var enemies := DirAccess.get_files_at("res://generated/scenes/enemies")
	var loaded := 0
	for f in enemies:
		if f.ends_with(".tscn"):
			var scene := load("res://generated/scenes/enemies/" + f) as PackedScene
			var node := scene.instantiate() if scene != null else null
			if node != null and node.get_node_or_null("Hurtbox") is RpgHurtbox:
				loaded += 1
			if node != null:
				node.free()
	hitbox.free()
	health.free()
	print("old paths %s, enemy scenes %d" % [good, loaded])
	quit(0 if good and loaded > 0 else 1)
"""


def _templates_of_1_1(tmp_path: Path) -> Path | None:
    """The template project of release 1.1 from this repository's history, or None."""
    import io
    import subprocess
    import tarfile

    repo = SAMPLE.parent
    for ref in OLD_REFS:
        found = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
            capture_output=True,
            check=False,
        )
        if found.returncode != 0:
            continue
        packed = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", ref, "godot_templates"],
            capture_output=True,
            check=True,
        )
        with tarfile.open(fileobj=io.BytesIO(packed.stdout)) as tar:
            tar.extractall(tmp_path / "release_1_1", filter="data")
        return tmp_path / "release_1_1" / "godot_templates"
    return None


def test_an_action_rpg_made_by_1_1_regenerates_and_old_combat_paths_still_load(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T14.01: the real-time combat scripts moved to combat/realtime/. A project whose runtime
    came from the 1.1 templates regenerates cleanly, nothing of the user's is touched, and a
    script that preloads an old path gets the same classes."""
    old_templates = _templates_of_1_1(tmp_path)
    if old_templates is None:
        pytest.skip("this checkout has no v1.1.0 tag and no m13 branch")
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    opened = archive.open_pack(pack, set(), pack_id="sample_pack")
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for(
        "Sample RPG", [config.pack_ref_from_source(pack, "sample_pack")], archetype="arpg"
    )
    cfg.starter = mapping.default_starter(cat, "arpg")
    with monkeypatch.context() as patch:
        patch.setattr(paths, "templates_root", lambda: old_templates)
        first = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert first.ok, [f"{i.code}: {i.message}" for i in first.issues]
    assert not (target / NEW_COMBAT).exists(), "the fixture must be a 1.1 project"
    assert "class_name RpgHitbox" in (target / OLD_COMBAT / "hitbox.gd").read_text("utf-8")
    game_before = {k: v for k, v in _stable(target).items() if k.startswith("game/")}

    result = _regenerate(godot_exe, target)

    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert [c for c in _codes(result) if c.startswith("REGEN-")] == []
    after = _stable(target)
    assert {k: v for k, v in after.items() if k.startswith("game/")} == game_before
    for stem in MOVED_SCRIPTS:
        assert f"{NEW_COMBAT}/{stem}.gd" in after
        shim = (target / OLD_COMBAT / f"{stem}.gd").read_text(encoding="utf-8")
        assert f'extends "res://{NEW_COMBAT}/{stem}.gd"' in shim
        assert "class_name" not in shim
    probe = target / "game" / "old_path_probe.gd"
    probe.write_text(OLD_PATH_SCRIPT, encoding="utf-8", newline="\n")
    run = _godot(godot_exe, target, ["--script", "res://game/old_path_probe.gd"], "old_paths")
    assert "old paths true" in run.stdout, run.stdout


@pytest.mark.parametrize("archetype", ["turn_based", "arpg"])
def test_a_project_made_by_1_1_regenerates_with_its_maps_and_tilesets_untouched(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archetype: str
) -> None:
    """The gate of 1.2 (T14.13): the third archetype changed shared recipes (the TileSet's
    side-view layers, the archetype HUD, the room checks of the validator). A top-down project
    whose runtime came from the 1.1 templates regenerates without a prompt, everything under
    `game/` is byte for byte what it was, and its TileSets are what 1.1 built."""
    old_templates = _templates_of_1_1(tmp_path)
    if old_templates is None:
        pytest.skip("this checkout has no v1.1.0 tag and no m13 branch")
    pack, target = _make_pack(tmp_path), tmp_path / "out"
    opened = archive.open_pack(pack, set(), pack_id="sample_pack")
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for(
        "Sample RPG", [config.pack_ref_from_source(pack, "sample_pack")], archetype=archetype
    )
    cfg.starter = mapping.default_starter(cat, archetype)
    with monkeypatch.context() as patch:
        patch.setattr(paths, "templates_root", lambda: old_templates)
        first = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert first.ok, [f"{i.code}: {i.message}" for i in first.issues]
    assert not (target / "addons/rpg_runtime/archetypes/metroidvania").exists()

    def kept(snapshot: dict[str, str]) -> dict[str, str]:
        return {
            k: v
            for k, v in snapshot.items()
            if k.startswith(("game/", "generated/tilesets/", "generated/sprite_frames/"))
        }

    before = kept(_stable(target))
    assert any(k.startswith("generated/tilesets/") for k in before)
    assert any(k.startswith("game/maps/") for k in before)

    result = _regenerate(godot_exe, target)

    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert [c for c in _codes(result) if c.startswith("REGEN-")] == [], "no prompt, no conflict"
    assert _diff(before, kept(_stable(target))) == []
    # the project is still of its own kind only, with this build's runtime
    archetypes = target / "addons/rpg_runtime/archetypes"
    assert sorted(p.name for p in archetypes.iterdir()) == [archetype]
    version = (target / "addons/rpg_runtime/VERSION").read_text(encoding="utf-8").strip()
    assert version == rpggen_version
    # the real-time combat set is shared code now: every project has it
    assert (target / "addons/rpg_runtime/combat/realtime/hitbox.gd").is_file()
