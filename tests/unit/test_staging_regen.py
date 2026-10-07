from __future__ import annotations

import os
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import ledger, staging
from rpggen.core.ledger import Ledger, LedgerEntry
from rpggen.errors import RpgGenError


def _write(root: Path, rel: str, data: bytes | str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def _project(root: Path) -> Path:
    """A minimal generated project."""
    _write(root, paths.CONFIG, "{}")
    _write(root, "project.godot", "config_version=5\n")
    _write(root, "game/maps/m.tscn", "map\n")
    _write(root, "assets/packs/p/a.png", b"\x89PNG-a")
    _write(root, "assets/packs/p/a.png.import", "[remap]\n")
    _write(root, ".godot/imported/a.ctex", b"cache")
    _write(root, ".godot/editor/state.cfg", "editor\n")
    return root


def test_new_mode_for_a_missing_or_empty_target(tmp_path: Path) -> None:
    stg = staging.create_staging(tmp_path / "fresh")
    assert stg.mode == "new" and not stg.regenerate
    assert list(stg.staging.iterdir()) == []
    (tmp_path / "empty").mkdir()
    assert staging.create_staging(tmp_path / "empty").mode == "new"


def test_leftover_working_folders_do_not_count_as_content(tmp_path: Path) -> None:
    (tmp_path / "t" / staging.FAILED_NAME / "x").mkdir(parents=True)
    assert staging.create_staging(tmp_path / "t").mode == "new"


def test_a_folder_that_is_not_a_project_is_env_009(tmp_path: Path) -> None:
    _write(tmp_path / "t", "notes.txt", "hello")
    with pytest.raises(RpgGenError) as exc:
        staging.create_staging(tmp_path / "t")
    assert exc.value.code == "ENV-009"


def test_regenerate_mode_copies_the_project_and_skips_working_folders(tmp_path: Path) -> None:
    target = _project(tmp_path / "t")
    _write(target, ".rpggen_backups/x/a", "b")
    _write(target, ".rpggen_failed/x/a", "f")
    _write(target, ".git/HEAD", "ref")
    _write(target, "export/game.exe", "x")
    _write(target, "rpggen/logs/old.log", "log")
    _write(target, "rpggen/results/old.json", "{}")
    stg = staging.create_staging(target)
    assert stg.mode == "regenerate"
    copied = sorted(
        p.relative_to(stg.staging).as_posix() for p in stg.staging.rglob("*") if p.is_file()
    )
    assert copied == [
        ".godot/editor/state.cfg",
        ".godot/imported/a.ctex",
        "assets/packs/p/a.png",
        "assets/packs/p/a.png.import",
        "game/maps/m.tscn",
        "project.godot",
        paths.CONFIG,
    ]


def test_binary_pack_files_are_hard_linked_and_text_files_are_copied(tmp_path: Path) -> None:
    target = _project(tmp_path / "t")
    stg = staging.create_staging(target)
    png = stg.staging / "assets/packs/p/a.png"
    sidecar = stg.staging / "assets/packs/p/a.png.import"
    try:
        linked = os.path.samefile(png, target / "assets/packs/p/a.png")
    except OSError:
        linked = False
    assert linked or png.read_bytes() == b"\x89PNG-a"  # a volume without hard links copies
    assert not os.path.samefile(sidecar, target / "assets/packs/p/a.png.import")


def test_templates_are_only_written_when_their_content_differs(tmp_path: Path) -> None:
    templates = tmp_path / "tpl"
    _write(templates, "addons/rpg_runtime/a.gd", "one\n")
    _write(templates, "addons/rpg_runtime/b.gd", "two\n")
    target = _project(tmp_path / "t")
    _write(target, "addons/rpg_runtime/a.gd", "one\r\n")  # same text, other line ending
    _write(target, "addons/rpg_runtime/b.gd", "old\n")
    stg = staging.create_staging(target)
    a = stg.staging / "addons/rpg_runtime/a.gd"
    os.utime(a, (1_000_000, 1_000_000))
    staging.install_templates(stg, templates)
    assert a.stat().st_mtime == 1_000_000, "unchanged template keeps its mtime"
    assert (stg.staging / "addons/rpg_runtime/b.gd").read_text() == "two\n"
    assert (target / "addons/rpg_runtime/b.gd").read_text() == "old\n", "target is not touched"


def test_changed_pack_file_is_replaced_not_edited_through_a_hard_link(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    _write(pack, "a.png", b"\x89PNG-new")
    target = _project(tmp_path / "t")
    stg = staging.create_staging(target)
    staging.install_pack(stg, pack, "p")
    assert (stg.staging / "assets/packs/p/a.png").read_bytes() == b"\x89PNG-new"
    assert (target / "assets/packs/p/a.png").read_bytes() == b"\x89PNG-a"


def _old_ledger(target: Path, rels: list[str]) -> Ledger:
    return Ledger(
        {r: LedgerEntry(ledger.file_hash(target / r), "pack_install", "generated") for r in rels}
    )


def test_prune_removes_untouched_files_that_left_the_pack(tmp_path: Path) -> None:
    target = _project(tmp_path / "t")
    old = _old_ledger(target, ["assets/packs/p/a.png", "assets/packs/p/a.png.import"])
    stg = staging.create_staging(target)
    issues = staging.prune_packs(stg, old, keep=set())
    assert issues == []
    assert not (stg.staging / "assets/packs/p/a.png").exists()
    assert not (stg.staging / "assets/packs/p/a.png.import").exists(), "sidecar goes with its file"
    assert (target / "assets/packs/p/a.png").is_file(), "the target is untouched"


def test_prune_keeps_modified_files_with_regen_003_and_user_files_silently(tmp_path: Path) -> None:
    target = _project(tmp_path / "t")
    old = _old_ledger(target, ["assets/packs/p/a.png"])
    (target / "assets/packs/p/a.png").write_bytes(b"\x89PNG-edited")
    _write(target, "assets/packs/p/mine.png", b"user")
    stg = staging.create_staging(target)
    issues = staging.prune_packs(stg, old, keep=set())
    assert [i.code for i in issues] == ["REGEN-003"]
    assert issues[0].file == "assets/packs/p/a.png"
    assert (stg.staging / "assets/packs/p/a.png").is_file()
    assert (stg.staging / "assets/packs/p/mine.png").is_file()


def test_prune_does_nothing_for_a_first_generation(tmp_path: Path) -> None:
    stg = staging.create_staging(tmp_path / "t")
    assert staging.prune_packs(stg, Ledger(), keep=set()) == []


def test_write_project_files_keeps_the_users_project_godot(tmp_path: Path) -> None:
    from rpggen.core import catalog, config

    target = _project(tmp_path / "t")
    (target / "project.godot").write_text("config_version=5\n[user]\nx=1\n", encoding="utf-8")
    jsonio.write(target / paths.CONFIG, {})
    stg = staging.create_staging(target)
    cfg = config.default_for("T", [config.PackRef("p", str(tmp_path), "0" * 64, "folder")])
    staging.write_project_files(stg, cfg, catalog.Catalog())
    assert "x=1" in (stg.staging / "project.godot").read_text(encoding="utf-8")
    assert (stg.staging / ".gitignore").is_file()


def test_only_the_chosen_archetype_is_installed(tmp_path: Path) -> None:
    templates = tmp_path / "tpl"
    for rel in (
        "addons/rpg_runtime/core/events.gd",
        "addons/rpg_runtime/archetypes/turn_based/battle_controller.gd",
        "addons/rpg_runtime/archetypes/turn_based/ui/battle_ui.gd",
        "addons/rpg_runtime/archetypes/arpg/player.gd",
        "builder/build.gd",
        "builder/recipes/turn_based/enemy_recipes.gd",
        "builder/recipes/arpg/enemy_recipes.gd",
        "builder/smoke/smoke_steps_m6.gd",
        "builder/smoke/smoke_steps_turn_based.gd",
        "builder/smoke/smoke_steps_turn_based.gd.uid",
        "builder/smoke/smoke_steps_arpg.gd",
    ):
        _write(templates, rel, "x\n")
    for archetype, gone, kept in (
        ("turn_based", "arpg", "turn_based"),
        ("arpg", "turn_based", "arpg"),
    ):
        stg = staging.create_staging(tmp_path / f"t_{archetype}")
        written = staging.install_templates(stg, templates, archetype)
        joined = "\n".join(written)
        assert f"archetypes/{kept}/" in joined and f"recipes/{kept}/" in joined
        assert f"smoke_steps_{kept}.gd" in joined
        assert f"archetypes/{gone}/" not in joined and f"recipes/{gone}/" not in joined
        assert f"smoke_steps_{gone}.gd" not in joined
        assert "addons/rpg_runtime/core/events.gd" in written
        assert "generated/builder/smoke/smoke_steps_m6.gd" in written
    # without an archetype everything is copied (the template project's own tests)
    stg = staging.create_staging(tmp_path / "all")
    assert any("archetypes/arpg/" in w for w in staging.install_templates(stg, templates))


def test_smoke_steps_follow_the_archetype() -> None:
    from rpggen.core import orchestrator

    turn_based = orchestrator.smoke_steps_for("turn_based").split(",")
    assert turn_based[0].endswith("smoke_steps_m6.gd")
    assert turn_based[1].endswith("smoke_steps_turn_based.gd")
    arpg = orchestrator.smoke_steps_for("arpg").split(",")
    assert arpg[0].endswith("smoke_steps_m6.gd") and arpg[1].endswith("smoke_steps_arpg.gd")
    assert len(arpg) == 2


def test_the_readme_gets_the_archetype_section(tmp_path: Path) -> None:
    from rpggen.core import catalog, config

    pack = config.PackRef("pack_a", "x", "0" * 64, "folder")
    stg = staging.create_staging(tmp_path / "tb")
    staging.write_project_files(stg, config.default_for("Game {x}", [pack]), catalog.Catalog())
    text = (stg.staging / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Game {x}")
    assert "## 11. Battles and enemies (turn-based)" in text
    other = config.default_for("Game", [pack], archetype="arpg")
    stg = staging.create_staging(tmp_path / "arpg")
    staging.write_project_files(stg, other, catalog.Catalog())
    assert "Battles and enemies" not in (stg.staging / "README.md").read_text(encoding="utf-8")
