from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from rpggen import godot_target
from rpggen.core import config, godot, godot_fetch, staging

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bump_godot", REPO / "tools" / "bump_godot.py")
assert spec and spec.loader
bump_godot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bump_godot)


def test_everything_reads_the_single_version() -> None:
    assert godot.SUPPORTED_VERSION == godot_target.SUPPORTED
    assert godot_fetch.DEFAULT_VERSION == godot_target.VERSION
    assert config.GODOT_VERSION == godot_target.VERSION
    assert f'("{godot_target.MAJOR_MINOR}")' in staging.minimal_project_godot("x")


def test_workflows_and_error_texts_agree_with_the_single_version() -> None:
    assert bump_godot.check() == []


def test_a_patch_bump_changes_only_the_full_version() -> None:
    text = "Godot {found} is not supported: builds projects for Godot 4.7. Use 4.7.2 or 4.7.x"
    assert bump_godot.rewrite_spec(text, "4.7.2", "4.7.3") == (
        "Godot {found} is not supported: builds projects for Godot 4.7. Use 4.7.3 or 4.7.x"
    )


def test_a_minor_bump_changes_the_series_too_but_not_other_numbers() -> None:
    text = "builds projects for Godot 4.7. Use 4.7.2 or 4.7.x; need 14.7 MB, 4.70 stays"
    got = bump_godot.rewrite_spec(text, "4.7.2", "4.8.1")
    assert got == "builds projects for Godot 4.8. Use 4.8.1 or 4.8.x; need 14.7 MB, 4.70 stays"


# ------------------------------------------------------------------------ the pinned hashes (T12.21)


def _bump_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bump_godot", Path(__file__).resolve().parents[2] / "tools" / "bump_godot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bump_reads_the_hashes_of_every_platform_from_the_release_list() -> None:
    bump = _bump_module()
    sums = "\n".join(
        f"{n:0128x}  {name}"
        for n, name in enumerate(
            (
                "Godot_v4.8.1-stable_win64.exe.zip",
                "Godot_v4.8.1-stable_linux.x86_64.zip",
                "Godot_v4.8.1-stable_macos.universal.zip",
                "godot-4.8.1-stable.tar.xz",
            ),
            start=10,
        )
    )
    seen: list[str] = []

    def get(url: str) -> bytes:
        seen.append(url)
        return sums.encode()

    hashes = bump.release_hashes("4.8.1", get)
    assert seen == [
        "https://github.com/godotengine/godot/releases/download/4.8.1-stable/SHA512-SUMS.txt"
    ]
    assert hashes == {"windows": f"{10:0128x}", "linux": f"{11:0128x}", "macos": f"{12:0128x}"}
    block = bump.sha_block("4.8.1", hashes)
    assert block.startswith("SHA512 = {\n") and block.endswith("}\n")
    assert bump._SHA_BLOCK.search("x = 1\n" + block + "y = 2\n").group(0) == block


def test_bump_refuses_a_release_without_a_checksum_and_changes_nothing() -> None:
    bump = _bump_module()
    before = bump.TARGET.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        bump.bump("4.9.9", lambda url: b"abc  something_else.zip")
    with pytest.raises(SystemExit):
        bump.bump("4.9.9", lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert bump.TARGET.read_text(encoding="utf-8") == before


def test_the_pin_block_is_found_in_the_real_target_file() -> None:
    bump = _bump_module()
    assert bump._SHA_BLOCK.search(bump.TARGET.read_text(encoding="utf-8")) is not None
    assert "release page" in bump.CHECKLIST
