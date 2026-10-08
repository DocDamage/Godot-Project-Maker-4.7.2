from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from rpggen.core import config, export_check


def test_render_escapes_the_product_name_and_slugs_the_path() -> None:
    text = export_check.render_presets(r'My "Game" \ 2')
    assert 'export_path="export/windows/my_game_2.exe"' in text
    assert r'application/product_name="My \"Game\" \\ 2"' in text
    assert "binary_format/embed_pck=true" in text
    assert 'name="Windows Desktop"' in text


def test_write_presets_keeps_an_existing_file(tmp_path: Path) -> None:
    assert export_check.write_presets(tmp_path, "Game") is True
    dst = tmp_path / "export_presets.cfg"
    mine = dst.read_text(encoding="utf-8").replace("encrypt_pck=false", "encrypt_pck=true")
    dst.write_text(mine, encoding="utf-8")
    assert export_check.write_presets(tmp_path, "Game") is False
    assert dst.read_text(encoding="utf-8") == mine


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
    assert not export_check.templates_installed(version, "web")
    (folder / "web_nothreads_release.zip").write_bytes(b"x")
    assert export_check.templates_installed(version, "web")


def test_missing_templates_give_env_010_and_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_EXPORT_TEMPLATES_DIR", str(tmp_path))
    monkeypatch.setattr(export_check.godot, "detect_version", lambda exe: (4, 7, 2, "stable"))
    issues, ran = export_check.run_check(Path("godot"), tmp_path, "Game", tmp_path)
    assert not ran
    assert [i.code for i in issues] == ["ENV-010"]
    assert issues[0].severity.value == "info"
    assert issues[0].message.startswith("Windows Desktop export templates")


# ------------------------------------------------------------------ T12.52: more targets


def test_the_targets_follow_the_config_order() -> None:
    assert tuple(export_check.TARGETS) == config.EXPORT_TARGETS
    assert export_check.ordered_targets(["macos", "nope", "web"]) == ["web", "macos"]


def test_presets_render_deterministically_in_the_fixed_order() -> None:
    a = export_check.render_presets("My Game", ["macos", "linux", "web", "windows"])
    b = export_check.render_presets("My Game", ["windows", "web", "linux", "macos"])
    assert a == b
    assert re.findall(r"^\[preset\.(\d+)\]$", a, re.M) == ["0", "1", "2", "3"]
    assert re.findall(r'^name="(.*)"$', a, re.M) == ["Windows Desktop", "Web", "Linux", "macOS"]
    assert re.findall(r'^export_path="(.*)"$', a, re.M) == [
        "export/windows/my_game.exe",
        "export/web/index.html",
        "export/linux/my_game.x86_64",
        "export/macos/my_game.zip",
    ]
    assert "; target:" not in a and "{" not in a.replace("={}", "")
    assert "variant/thread_support=false" in a  # itch.io: no SharedArrayBuffer needed
    assert "notarization/notarization=0" in a
    assert 'application/bundle_identifier="com.example.my-game"' in a
    assert export_check.render_presets("My Game", []) == export_check.render_presets("My Game")


def test_a_single_target_is_preset_0() -> None:
    text = export_check.render_presets("Game", ["linux"])
    assert re.findall(r'^name="(.*)"$', text, re.M) == ["Linux"]
    assert "[preset.0]" in text and "[preset.0.options]" in text


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("My Game", "com.example.my-game"),
        ("3 Pigs", "com.example.n3-pigs"),
        ("", "com.example.game"),
    ],
)
def test_bundle_identifier_is_valid(name: str, expected: str) -> None:
    ident = export_check.bundle_identifier(name)
    assert re.fullmatch(r"[A-Za-z0-9.-]+", ident)
    assert not ident.rsplit(".", 1)[1][0].isdigit()
    if name != "":
        assert ident == expected


def test_write_presets_appends_new_targets_to_the_users_file(tmp_path: Path) -> None:
    assert export_check.write_presets(tmp_path, "Game")
    dst = tmp_path / "export_presets.cfg"
    mine = dst.read_text(encoding="utf-8").replace("seed=0", "seed=7")  # a user edit
    dst.write_text(mine, encoding="utf-8")
    assert export_check.write_presets(tmp_path, "Game", ["windows", "web", "macos"])
    text = dst.read_text(encoding="utf-8")
    assert text.startswith(mine.rstrip("\n"))  # every line of the user's file stays
    assert re.findall(r'^name="(.*)"$', text, re.M) == ["Windows Desktop", "Web", "macOS"]
    assert re.findall(r"^\[preset\.(\d+)\]$", text, re.M) == ["0", "1", "2"]
    assert not export_check.write_presets(tmp_path, "Game", ["web", "windows"])


def test_each_target_is_checked_or_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "4.7.2.stable"
    folder.mkdir()
    (folder / "linux_release.x86_64").write_bytes(b"x")
    monkeypatch.setenv("RPGGEN_EXPORT_TEMPLATES_DIR", str(tmp_path))
    monkeypatch.setattr(export_check.godot, "detect_version", lambda exe: (4, 7, 2, "stable"))
    calls: list[list[str]] = []

    def fake_run(exe, project, args, **kw):  # type: ignore[no-untyped-def]
        calls.append(list(args))
        Path(args[2]).write_bytes(b"binary")
        return SimpleNamespace(cancelled=False, timed_out=False, returncode=0)

    monkeypatch.setattr(export_check.godot, "run_godot", fake_run)
    issues, ran = export_check.run_check(
        Path("godot"), tmp_path, "Game", tmp_path, targets=["web", "linux"]
    )
    assert ran == ["linux"]
    assert [c[:2] for c in calls] == [["--export-release", "Linux"]]
    assert [(i.code, i.message.split(" export")[0]) for i in issues] == [("ENV-010", "Web")]
