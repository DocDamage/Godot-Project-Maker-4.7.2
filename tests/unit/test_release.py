"""Release consistency (T10.10): one version everywhere, and the packaging files agree."""

from __future__ import annotations

import re
from pathlib import Path

import rpggen
from rpggen.core import runtime_version

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_versions_are_consistent() -> None:
    version = rpggen.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert re.search(r'^version = "([^"]+)"', _read("pyproject.toml"), re.M).group(1) == version
    assert runtime_version.read_version(REPO / "godot_templates") == version
    assert (
        re.search(
            r'^version="([^"]+)"',
            _read("godot_templates/addons/rpg_project_tools/plugin.cfg"),
            re.M,
        ).group(1)
        == version
    )
    info = _read("packaging/version_info.txt")
    tuple_text = ", ".join(version.split(".")) + ", 0"
    assert f"filevers=({tuple_text})" in info and f"prodvers=({tuple_text})" in info
    assert f"StringStruct('FileVersion', '{version}')" in info
    assert f"StringStruct('ProductVersion', '{version}')" in info
    assert f'#define AppVersion "{version}"' in _read("packaging/installer.iss")


def test_runtime_changelog_has_the_current_version() -> None:
    text = _read("godot_templates/addons/rpg_runtime/CHANGELOG.md")
    assert f"## {rpggen.__version__}" in text


def test_packaging_files_exist_and_reference_each_other() -> None:
    spec = _read("packaging/rpggen.spec")
    for needle in ("rpggen-cli", "godot_templates", "sample_pack", "style.qss", ".json", "tests"):
        assert needle in spec
    assert "console=False" in spec and "console=True" in spec
    assert "QtWebEngineCore" in spec and "Qt3DCore" in spec  # unused Qt modules are excluded
    for rel in ("packaging/rpggen.ico", "packaging/entry_gui.py", "packaging/entry_cli.py"):
        assert (REPO / rel).is_file(), rel
    iss = _read("packaging/installer.iss")
    assert "PrivilegesRequired=lowest" in iss and "LICENSE_AND_NOTICES.txt" in iss
    assert "{autoprograms}" in iss and "[UninstallDelete]" in iss


def test_third_party_notices_name_every_runtime_dependency() -> None:
    notices = _read("THIRD_PARTY_NOTICES.md")
    for name in ("PySide6", "Pillow", "NumPy", "py7zr", "jsonschema", "LGPL"):
        assert name in notices
    deps = re.search(r"dependencies = \[(.*?)\]", _read("pyproject.toml"), re.S).group(1)
    for dep in re.findall(r'"([A-Za-z0-9_.-]+)', deps):
        assert dep.lower() in notices.lower(), dep


def test_release_workflow_builds_signs_and_checks_sums() -> None:
    text = _read(".github/workflows/release.yml")
    assert "tags:" in text and "v*" in text
    assert "tools/package.py --smoke" in text
    assert "SHA256SUMS.txt" in text and "signpath" in text.lower()


def test_main_ci_runs_the_full_ubuntu_job() -> None:
    text = _read(".github/workflows/ci.yml")
    ubuntu = text[text.index("ubuntu:") :]
    assert "Becomes a full job" not in ubuntu
    for needle in ("fetch_godot", "godot-test", "-m integration", "QT_QPA_PLATFORM"):
        assert needle in text
    assert "pytest -q -m integration" in ubuntu


def test_architecture_doc_is_the_current_spec() -> None:
    assert _read("docs/architecture.md") == _read("docs/spec/ARCHITECTURE.md")


def test_documentation_set_exists_and_links_resolve() -> None:
    for rel in (
        "README.md", "CONTRIBUTING.md", "docs/user_guide.md", "docs/regeneration.md",
        "docs/adapters.md", "docs/profiles.md", "docs/release.md", "docs/coverage.md",
        "docs/errors.md", "docs/architecture.md", "THIRD_PARTY_NOTICES.md",
    ):  # fmt: skip
        assert (REPO / rel).is_file(), rel
    link = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+)")
    for rel in ("README.md", "CONTRIBUTING.md", "docs/user_guide.md", "docs/profiles.md",
                "docs/adapters.md", "docs/release.md", "docs/coverage.md"):  # fmt: skip
        base = (REPO / rel).parent
        for target in link.findall(_read(rel)):
            assert (base / target).exists(), f"{rel}: broken link {target}"


def test_repository_urls_are_consistent() -> None:
    import subprocess

    assert rpggen.REPO_URL.endswith("/Godot-Project-Maker-4.7.2")
    assert f"AppPublisherURL={rpggen.REPO_URL}\n" in _read("packaging/installer.iss")
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for rel in tracked:
        if rel.startswith("docs/spec/"):
            continue
        path = REPO / rel
        if path.suffix.lower() not in {".md", ".py", ".iss", ".yml", ".yaml", ".toml", ".json", ".txt"}:
            continue
        if rel == "tests/unit/test_release.py" or not path.is_file():
            continue
        assert "github.com/rpggen/" not in path.read_text(encoding="utf-8", errors="ignore"), rel


def test_notices_carry_no_gpl_dependency_outside_the_bootloader() -> None:
    notices = _read("THIRD_PARTY_NOTICES.md")
    assert "mutagen" not in notices.lower()
    for line in notices.splitlines():
        if "GPL-2.0-or-later" in line:
            assert "LGPL" in line, line  # py7zr is LGPL-2.1-or-later; no plain GPL row remains


def test_the_spec_exists_once_and_dev_docs_are_not_bundled() -> None:
    assert not (REPO / "Implementation Plan and Specs").exists()
    assert (REPO / "docs/dev/implementation_notes.md").is_file()
    assert not (REPO / "IMPLEMENTATION_NOTES.md").exists()
    spec = _read("packaging/rpggen.spec")
    assert '"spec"' in spec and '"dev"' in spec
    ignore = _read(".gitignore")
    assert ".mypy_cache/" in ignore and "validation_runs/" in ignore


def test_the_screenshots_match_the_files_the_guide_uses() -> None:
    """Every picture the guide shows exists, and no picture in docs/images is left unused."""
    shown = set(re.findall(r"\]\(images/([\w.-]+\.png)\)", _read("docs/user_guide.md")))
    on_disk = {p.name for p in (REPO / "docs/images").glob("*.png")}
    readme_uses = set(re.findall(r"docs/images/([\w.-]+\.png)", _read("README.md")))
    assert shown <= on_disk, sorted(shown - on_disk)
    assert on_disk <= shown | readme_uses, sorted(on_disk - shown - readme_uses)
    # the tool that renders them knows every one the guide shows
    tool = _read("tools/make_doc_screenshots.py")
    for name in shown:
        stem = name.removesuffix(".png")
        assert stem in tool or stem.removeprefix("wizard_") in tool, name


def test_the_application_changelog_has_the_current_version() -> None:
    assert f"## {rpggen.__version__}" in _read("CHANGELOG.md")
