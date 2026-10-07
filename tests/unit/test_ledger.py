from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import ledger
from rpggen.core.ledger import FileState, Ledger, LedgerEntry
from rpggen.errors import RpgGenError


def _write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_text_files_hash_the_same_with_crlf_and_lf(tmp_path: Path) -> None:
    lf = _write(tmp_path, "a.gd", b"extends Node\nvar x = 1\n")
    crlf = _write(tmp_path, "b.gd", b"extends Node\r\nvar x = 1\r\n")
    assert ledger.file_hash(lf) == ledger.file_hash(crlf)
    assert ledger.file_hash(lf) == hashlib.sha256(b"extends Node\nvar x = 1\n").hexdigest()


def test_dotfiles_count_as_text_by_name(tmp_path: Path) -> None:
    a = _write(tmp_path, "x/.gitignore", b".godot/\n")
    b = _write(tmp_path, "y/.gitignore", b".godot/\r\n")
    assert ledger.file_hash(a) == ledger.file_hash(b)
    assert (
        ledger.file_hash(_write(tmp_path, ".gitattributes", b"* text\r\n"))
        == hashlib.sha256(b"* text\n").hexdigest()
    )


def test_binary_files_hash_raw_bytes(tmp_path: Path) -> None:
    raw = b"\x89PNG\r\n\x1a\n\x00\r\n"
    png = _write(tmp_path, "a.png", raw)
    assert ledger.file_hash(png) == hashlib.sha256(raw).hexdigest()


def test_ledger_round_trip_and_sorted_keys(tmp_path: Path) -> None:
    led = Ledger(
        {
            "generated/b.tres": LedgerEntry("b" * 64, "tileset_recipe", "generated"),
            "game/maps/m.tscn": LedgerEntry("a" * 64, "starter_map_recipe", "user_seed"),
        },
        ["generated/old.tscn", "generated/old.tscn"],
    )
    path = tmp_path / "rpggen" / "ownership_ledger.json"
    led.save(path)
    data = jsonio.read(path)
    assert list(data["files"]) == ["game/maps/m.tscn", "generated/b.tres"]
    assert data["deleted_by_user"] == ["generated/old.tscn"]
    loaded = Ledger.load(path)
    assert loaded.files == led.files
    assert loaded.deleted_by_user == ["generated/old.tscn"]


def test_loading_an_invalid_ledger_is_cat_002(tmp_path: Path) -> None:
    path = tmp_path / "l.json"
    jsonio.write(path, {"ledger_version": 1})
    with pytest.raises(RpgGenError) as exc:
        Ledger.load(path)
    assert exc.value.code == "CAT-002"


def test_classify_covers_all_five_states(tmp_path: Path) -> None:
    keep = _write(tmp_path, "generated/keep.tres", b"one\n")
    changed = _write(tmp_path, "generated/changed.tres", b"one\n")
    _write(tmp_path, "generated/user.tres", b"mine\n")
    led = Ledger(
        {
            "generated/keep.tres": LedgerEntry(ledger.file_hash(keep), "r", "generated"),
            "generated/changed.tres": LedgerEntry(ledger.file_hash(changed), "r", "generated"),
            "generated/gone.tres": LedgerEntry("c" * 64, "r", "generated"),
            "generated/gone_before.tres": LedgerEntry("d" * 64, "r", "generated"),
        },
        ["generated/gone_before.tres"],
    )
    changed.write_bytes(b"two\n")
    assert ledger.classify(tmp_path, "generated/keep.tres", led) is FileState.UNTOUCHED
    assert ledger.classify(tmp_path, "generated/changed.tres", led) is FileState.MODIFIED
    assert ledger.classify(tmp_path, "generated/gone.tres", led) is FileState.DELETED
    assert ledger.classify(tmp_path, "generated/user.tres", led) is FileState.UNKNOWN
    assert ledger.classify(tmp_path, "generated/never.tres", led) is FileState.ABSENT
    # already recorded as deleted by the user: no longer "deleted", just absent
    assert ledger.classify(tmp_path, "generated/gone_before.tres", led) is FileState.ABSENT


def test_covered_paths() -> None:
    for rel in (
        "generated/tilesets/a.tres",
        "addons/rpg_runtime/plugin.cfg",
        "addons/rpg_project_tools/x.gd",
        "rpggen/asset_catalog.json",
        "rpggen/build_state.json",
        "assets/packs/p/a.png",
        "project.godot",
        ".gitignore",
        ".gitattributes",
        "README.md",
        "game/maps/starter_map.tscn",
    ):
        assert ledger.is_covered(rel), rel
    for rel in (
        "rpggen/logs/godot_build.log",
        "rpggen/results/build_results.json",
        "rpggen/ownership_ledger.json",
        "GENERATION_REPORT.md",
        "notes.txt",
        "export/game.exe",
        ".godot/imported/x.ctex",
    ):
        assert not ledger.is_covered(rel), rel
    assert ledger.owner_of("game/a.gd") == "user_seed"
    assert ledger.owner_of("generated/a.gd") == "generated"


def test_scan_records_hashes_owners_and_recipes(tmp_path: Path) -> None:
    stg = tmp_path / "stg"
    _write(stg, "generated/tilesets/a.tres", b"ts\n")
    _write(stg, "game/maps/m.tscn", b"map\n")
    _write(stg, "rpggen/logs/x.log", b"log\n")
    _write(stg, ".godot/cache", b"c")
    _write(stg, "notes.txt", b"mine\n")
    jsonio.write(
        stg / "rpggen/results/build_results.json",
        {"items": [{"recipe": "tileset_recipe", "output": "generated/tilesets/a.tres"}]},
    )
    led = ledger.scan(stg)
    assert sorted(led.files) == ["game/maps/m.tscn", "generated/tilesets/a.tres"]
    assert led.files["generated/tilesets/a.tres"].written_by == "tileset_recipe"
    assert led.files["generated/tilesets/a.tres"].owner == "generated"
    assert led.files["game/maps/m.tscn"].owner == "user_seed"


def test_scan_keeps_seed_entries_and_skips_user_created_files(tmp_path: Path) -> None:
    target, stg = tmp_path / "t", tmp_path / "s"
    for root in (target, stg):
        _write(root, "game/maps/m.tscn", b"painted by the user\n")
        _write(root, "game/scripts/mine.gd", b"extends Node\n")
        _write(root, "generated/user_made.tres", b"x\n")
    _write(stg, "generated/new.tres", b"new\n")
    old = Ledger({"game/maps/m.tscn": LedgerEntry("e" * 64, "starter_map_recipe", "user_seed")}, [])
    led = ledger.scan(stg, target, old)
    assert led.files["game/maps/m.tscn"].sha256 == "e" * 64, "the seed's hash at creation is kept"
    assert "game/scripts/mine.gd" not in led.files, "user-created"
    assert "generated/user_made.tres" not in led.files, "user-created"
    assert "generated/new.tres" in led.files


def test_demo_removed_flag_round_trips_and_is_omitted_when_false(tmp_path: Path) -> None:
    plain = Ledger()
    assert "demo_removed" not in plain.to_json()
    flagged = Ledger(demo_removed=True)
    assert flagged.to_json()["demo_removed"] is True
    path = tmp_path / "ledger.json"
    flagged.save(path)
    assert Ledger.load(path).demo_removed is True
    assert Ledger.from_json(plain.to_json()).demo_removed is False


def test_scan_keeps_the_demo_removed_flag(tmp_path: Path) -> None:
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "a.txt").write_text("x", encoding="utf-8")
    assert ledger.scan(tmp_path, None, Ledger(demo_removed=True)).demo_removed is True
