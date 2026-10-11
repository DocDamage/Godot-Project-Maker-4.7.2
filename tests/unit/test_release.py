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
    for needle in ("fetch_godot", "godot-test", '-m "integration', "QT_QPA_PLATFORM"):
        assert needle in text
    # the integration suites are split per archetype (T14.11): the main jobs run the shared
    # ones, and a job per archetype and system runs the rest, so nothing is left out
    shared = 'pytest -q -m "integration and not arpg and not metroidvania and not shmup and not run_and_gun and not racing"'
    assert shared in ubuntu and text.count(shared) == 2
    job = text[text.index("archetype-integration:") :]
    assert "archetype: [arpg, metroidvania, shmup, run_and_gun, racing]" in job
    assert "os: [windows-latest, ubuntu-latest]" in job
    assert 'pytest -q -m "integration and ${{ matrix.archetype }}"' in job


def test_every_archetype_marker_of_ci_is_a_registered_marker_with_tests() -> None:
    """A marker the CI selects by must exist, or its job would run nothing and pass."""
    pyproject = _read("pyproject.toml")
    for marker, file in (
        ("arpg", "tests/integration/test_m9_sample.py"),
        ("metroidvania", "tests/integration/test_m14_side_sample.py"),
        ("shmup", "tests/integration/test_m16_shmup.py"),
        ("run_and_gun", "tests/integration/test_m16_run_and_gun.py"),
        ("racing", "tests/integration/test_m16_racing.py"),
    ):
        assert f'"{marker}: ' in pyproject, marker
        assert f"pytest.mark.{marker}" in _read(file), file


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
        if path.suffix.lower() not in {
            ".md",
            ".py",
            ".iss",
            ".yml",
            ".yaml",
            ".toml",
            ".json",
            ".txt",
        }:
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


# ------------------------------------------------------------------------ hygiene (T12.15)


def test_every_third_party_action_is_pinned_to_a_full_commit_sha() -> None:
    sha = re.compile(r"^[0-9a-f]{40}$")
    found = 0
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*(?:-\s*)?uses:\s*(\S+)", line)
            if not match or match.group(1).startswith("./"):
                continue  # a workflow of this repository is not third-party
            found += 1
            name, _, ref = match.group(1).partition("@")
            assert sha.match(ref), f"{path.name}: {name} is pinned to {ref!r}, not a commit SHA"
            assert "#" in line, f"{path.name}: {name} has no tag comment next to its SHA"
    assert found >= 10


def test_dependabot_keeps_the_actions_current_every_week() -> None:
    text = _read(".github/dependabot.yml")
    assert 'package-ecosystem: "github-actions"' in text and 'interval: "weekly"' in text


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_the_lock_file_names_every_dependency_of_pyproject() -> None:
    pyproject = _read("pyproject.toml")
    runtime = re.search(r"dependencies = \[(.*?)\]", pyproject, re.S).group(1)
    dev = re.search(r"^dev = \[(.*?)\]", pyproject, re.S | re.M).group(1)
    wanted = {_normalized(m) for m in re.findall(r'"([A-Za-z0-9_.-]+)', runtime + dev)}
    lock = _read("requirements/release.txt")
    pinned = {_normalized(m) for m in re.findall(r"^([A-Za-z0-9_.-]+)==", lock, re.M)}
    assert wanted <= pinned, sorted(wanted - pinned)
    assert "--hash=sha256:" in lock and "setuptools==" in lock  # hashed, and setuptools pinned too
    assert "--generate-hashes" in lock.splitlines()[4] and "--extra=dev" in lock.splitlines()[4]


def test_the_release_runs_the_whole_ci_first_and_installs_from_the_lock() -> None:
    release = _read(".github/workflows/release.yml")
    assert "uses: ./.github/workflows/ci.yml" in release and "needs: ci" in release
    assert "pip install --require-hashes -r requirements/release.txt" in release
    assert "pip install --no-build-isolation --no-deps -e ." in release
    assert "pip install -e .[dev]" not in release
    ci = _read(".github/workflows/ci.yml")
    assert "workflow_call:" in ci
    assert (
        "pip-compile --generate-hashes" in ci
        and "git diff --exit-code requirements/release.txt" in ci
    )


def test_a_tag_build_stops_while_the_coverage_tables_are_pending() -> None:
    release = _read(".github/workflows/release.yml")
    gate = release[release.index("The 1.0 gate") :]
    assert "github.ref_type == 'tag'" in gate.split("run:")[0]
    assert "docs/coverage.md" in gate and "(pending)" in gate and "exit 1" in gate


def test_contributing_does_not_tell_anyone_to_copy_a_file_onto_itself() -> None:
    text = _read("CONTRIBUTING.md")
    assert "and copy it to" not in text
    assert "1. Add the row to `docs/spec/03_ERROR_CODES.md`." in text


def test_pyside6_has_an_upper_bound_and_ci_tests_the_oldest_and_the_newest() -> None:
    assert '"PySide6>=6.7,<7"' in _read("pyproject.toml")
    ci = _read(".github/workflows/ci.yml")
    assert 'pyside: ["6.7.*", "latest"]' in ci and "fail-fast: false" in ci
    assert 'pip install "PySide6==${{ matrix.pyside }}"' in ci
    assert "tests/gui" in ci


# ------------------------------------------------------------------------ T12.63: three platforms


def _pins(rel: str) -> dict[str, str]:
    text = _read(rel)
    return {_normalized(n): v for n, v in re.findall(r"^([A-Za-z0-9_.-]+)==(\S+)", text, re.M)}


def test_the_release_builds_and_smoke_tests_every_platform_then_publishes_one_sum_file() -> None:
    release = _read(".github/workflows/release.yml")
    for job, runner, lock in (
        ("windows", "windows-latest", "requirements/release.txt"),
        ("linux", "ubuntu-22.04", "requirements/release-linux.txt"),
        ("macos", "macos-14", "requirements/release-macos.txt"),
    ):
        body = release[release.index(f"\n  {job}:") :]
        body = body[: body.find("\n  ", 3 + len(job)) if False else len(body)]
        assert f"runs-on: {runner}" in body.split("steps:")[0], job
        section = body.split("\n  publish:")[0]
        assert f"pip install --require-hashes -r {lock}" in section, job
        assert "tools/package.py --smoke" in section and "fetch_godot.py" in section, job
    publish = release[release.index("\n  publish:") :]
    assert "needs: [windows, linux, macos]" in publish
    assert "sha256sum rpggen-* > SHA256SUMS.txt" in publish
    for kind in ("setup.exe", "portable.zip", "AppImage", "linux-x86_64.tar.gz", "macos-"):
        assert kind in publish, kind


def test_the_platform_locks_pin_the_same_versions_as_the_windows_lock() -> None:
    windows = _pins("requirements/release.txt")
    for rel in ("requirements/release-linux.txt", "requirements/release-macos.txt"):
        other = _pins(rel)
        shared = set(windows) & set(other)
        assert {n for n in shared if windows[n] != other[n]} == set(), rel
        assert {"pyside6", "pyinstaller", "pillow", "numpy"} <= shared, rel
        assert "--hash=sha256:" in _read(rel)
    assert "macholib" in _pins("requirements/release-macos.txt")  # PyInstaller needs it there
    assert "pywin32-ctypes" not in _pins("requirements/release-linux.txt")


def test_the_linux_package_files_exist() -> None:
    desktop = _read("packaging/linux/rpggen.desktop")
    assert "Exec=rpggen" in desktop and "Icon=rpggen" in desktop and "Type=Application" in desktop
    apprun = _read("packaging/linux/AppRun")
    assert apprun.startswith("#!/bin/sh") and "usr/lib/rpggen/rpggen-cli" in apprun
    assert (REPO / "packaging/linux/rpggen.png").is_file()
    spec = _read("packaging/rpggen.spec")
    assert "BUNDLE(" in spec and "rpggen.app" in spec and "IS_MAC" in spec
