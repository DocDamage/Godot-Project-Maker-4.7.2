from __future__ import annotations

import zipfile
from pathlib import Path

from rpggen.core import preflight

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _codes(issues) -> list[str]:
    return [i.code for i in issues]


def test_zip_size_comes_from_the_central_directory(tmp_path: Path) -> None:
    z = tmp_path / "p.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.bin", b"\0" * 5000)
        zf.writestr("b.bin", b"\0" * 3000)
    assert preflight.pack_uncompressed_size(z) == 8000
    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "x").write_bytes(b"1" * 10)
    assert preflight.pack_uncompressed_size(folder) == 10


def test_target_inside_pack_is_env_008(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    assert "ENV-008" in _codes(preflight.check_target(pack / "out", [pack]))
    assert "ENV-008" not in _codes(preflight.check_target(tmp_path / "out", [pack]))


def test_non_empty_target_is_env_009_unless_it_is_a_project(tmp_path: Path) -> None:
    target = tmp_path / "t"
    target.mkdir()
    (target / "f.txt").write_text("x")
    assert "ENV-009" in _codes(preflight.check_target(target, []))
    (target / "rpggen").mkdir()
    (target / "rpggen" / "generator_config.json").write_text("{}")
    assert "ENV-009" not in _codes(preflight.check_target(target, []))


def test_cloud_and_long_paths_warn(tmp_path: Path) -> None:
    cloud = tmp_path / "OneDrive" / "game"
    assert "ENV-006" in _codes(preflight.check_target(cloud, []))
    long = tmp_path / ("d" * 120) / ("e" * 120)
    assert "ENV-007" in _codes(preflight.check_target(long, []))


def test_free_space_requirement(tmp_path: Path, monkeypatch) -> None:
    import shutil
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: usage(1, 1, 10 * 1024 * 1024))
    issues = preflight.check_target(tmp_path / "t", [])
    assert "ENV-005" in _codes(issues)


def test_check_pack(tmp_path: Path) -> None:
    assert preflight.check_pack(SYNTH / "basic16") == []
    assert preflight.check_pack(SYNTH / "zipped.zip") == []
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"nope")
    assert _codes(preflight.check_pack(bad)) == ["ARCH-001"]
    assert _codes(preflight.check_pack(tmp_path / "missing")) == ["ARCH-001"]
