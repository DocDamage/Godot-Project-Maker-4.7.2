from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import export_check


def test_render_escapes_the_product_name_and_slugs_the_path() -> None:
    text = export_check.render_presets(r'My "Game" \ 2')
    assert 'export_path="export/windows/my_game_2.exe"' in text
    assert r'application/product_name="My \"Game\" \\ 2"' in text
    assert "binary_format/embed_pck=true" in text
    assert 'name="Windows Desktop"' in text


def test_write_presets_keeps_an_existing_file(tmp_path: Path) -> None:
    assert export_check.write_presets(tmp_path, "Game") is True
    (tmp_path / "export_presets.cfg").write_text("mine", encoding="utf-8")
    assert export_check.write_presets(tmp_path, "Game") is False
    assert (tmp_path / "export_presets.cfg").read_text(encoding="utf-8") == "mine"


def test_templates_installed_looks_for_the_version_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_EXPORT_TEMPLATES_DIR", str(tmp_path))
    version = (4, 7, 2, "stable")
    assert export_check.version_folder(version) == "4.7.2.stable"
    assert not export_check.templates_installed(version)
    folder = tmp_path / "4.7.2.stable"
    folder.mkdir()
    assert not export_check.templates_installed(version)  # empty folder
    (folder / "windows_release_x86_64.exe").write_bytes(b"x")
    assert export_check.templates_installed(version)


def test_missing_templates_give_env_010_and_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_EXPORT_TEMPLATES_DIR", str(tmp_path))
    monkeypatch.setattr(export_check.godot, "detect_version", lambda exe: (4, 7, 2, "stable"))
    issues, ran = export_check.run_check(Path("godot"), tmp_path, "Game", tmp_path)
    assert not ran
    assert [i.code for i in issues] == ["ENV-010"]
    assert issues[0].severity.value == "info"
