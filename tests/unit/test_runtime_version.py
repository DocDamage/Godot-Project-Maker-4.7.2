from __future__ import annotations

import re
from pathlib import Path

import pytest

from rpggen import jsonio, paths
from rpggen.core import catalog, config, ledger, orchestrator, report, runtime_version, staging
from rpggen.errors import CODES, RpgGenError

CHANGELOG = """# Changelog

## 2.0.0

* Breaking: new save format
  that wraps onto a second line.

## 1.1.0

- Added gamepad support

## 1.0.0

* First release

## not-a-version

* ignored
"""


def _templates(root: Path, version: str | None, changelog: str = CHANGELOG) -> Path:
    folder = root / "addons" / "rpg_runtime"
    folder.mkdir(parents=True, exist_ok=True)
    if version is not None:
        (folder / "VERSION").write_text(version + "\n", encoding="utf-8")
    (folder / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return root


def test_parse_and_compare() -> None:
    assert runtime_version.parse_version(" 1.2.3\n") == (1, 2, 3)
    for bad in ("1.2", "a.b.c", "1.2.3-beta", ""):
        with pytest.raises(ValueError):
            runtime_version.parse_version(bad)
    assert runtime_version.compare("1.10.0", "1.9.9") == 1
    assert runtime_version.compare("1.0.0", "1.0.0") == 0
    assert runtime_version.compare("0.9.0", "1.0.0") == -1
    assert runtime_version.major("3.1.4") == 3
    assert runtime_version.format_version((1, 2, 3)) == "1.2.3"


def test_read_version_missing_or_malformed(tmp_path: Path) -> None:
    assert runtime_version.read_version(tmp_path) is None
    _templates(tmp_path, "oops")
    assert runtime_version.read_version(tmp_path) is None
    _templates(tmp_path, "1.4.0")
    assert runtime_version.read_version(tmp_path) == "1.4.0"


def test_parse_changelog() -> None:
    entries = runtime_version.parse_changelog(CHANGELOG)
    assert list(entries) == ["2.0.0", "1.1.0", "1.0.0"]
    assert entries["2.0.0"] == ["Breaking: new save format that wraps onto a second line."]
    assert entries["1.1.0"] == ["Added gamepad support"]


def test_changelog_between() -> None:
    entries = runtime_version.parse_changelog(CHANGELOG)
    got = runtime_version.changelog_between("1.0.0", "2.0.0", entries)
    assert [v for v, _ in got] == ["2.0.0", "1.1.0"]
    assert [v for v, _ in runtime_version.changelog_between("1.0.0", "1.1.0", entries)] == ["1.1.0"]
    assert [v for v, _ in runtime_version.changelog_between(None, "1.1.0", entries)] == [
        "1.1.0",
        "1.0.0",
    ]
    assert runtime_version.changelog_between("2.0.0", "2.0.0", entries) == []
    assert "Version 2.0.0" in runtime_version.changelog_text(got)


def test_check_upgrade_cases(tmp_path: Path) -> None:
    tpl = _templates(tmp_path / "tpl", "2.0.0")
    # no target / target without a runtime: nothing to upgrade
    info = runtime_version.check_upgrade(tpl, None)
    assert info.old is None and info.new == "2.0.0" and not info.needs_confirmation
    info = runtime_version.check_upgrade(tpl, tmp_path / "missing")
    assert info.old is None and not info.needs_confirmation
    # major increase
    major_target = _templates(tmp_path / "t1", "1.0.0")
    info = runtime_version.check_upgrade(tpl, major_target)
    assert info.is_upgrade and info.major_increase and info.needs_confirmation
    assert [v for v, _ in info.changelog] == ["2.0.0", "1.1.0"]
    assert "new save format" in info.changelog_text
    # same major
    info = runtime_version.check_upgrade(_templates(tmp_path / "tpl2", "1.1.0"), major_target)
    assert info.is_upgrade and not info.major_increase and not info.needs_confirmation
    # same version and downgrade
    same = runtime_version.check_upgrade(tpl, _templates(tmp_path / "t2", "2.0.0"))
    assert not same.is_upgrade and not same.is_downgrade and same.changelog == []
    down = runtime_version.check_upgrade(major_target, tpl)
    assert down.is_downgrade and not down.needs_confirmation


def test_shipped_version_and_changelog_agree() -> None:
    root = paths.templates_root()
    version = runtime_version.read_version(root)
    assert version is not None
    assert version in runtime_version.read_changelog(root)


def test_regen_006_is_defined() -> None:
    assert CODES["REGEN-006"].severity == "error"
    err = RpgGenError("REGEN-006", old="1.0.0", new="2.0.0")
    assert "1.0.0" in err.issue.message and "2.0.0" in err.issue.message


# ------------------------------------------------------------------ orchestrator preflight


def _state(target: Path, accept: bool) -> orchestrator._State:
    state = orchestrator._State(None, target, Path(__file__), orchestrator.Callbacks())
    state.accept_runtime_upgrade = accept
    state.cfg = config.default_for("T", [])
    return state


def test_preflight_runtime_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tpl = _templates(tmp_path / "tpl", "2.0.0")
    project = _templates(tmp_path / "proj", "1.0.0")
    jsonio.write(project / paths.CONFIG, {})
    monkeypatch.setattr(paths, "templates_root", lambda: tpl)
    monkeypatch.setattr(orchestrator.promote, "editor_open", lambda p: False)
    monkeypatch.setattr(orchestrator.godot, "detect_version", lambda e: "4.7.2")
    monkeypatch.setattr(orchestrator.godot, "check_version", lambda v: [])
    monkeypatch.setattr(orchestrator.preflight, "check_target", lambda t, s: [])
    log: list[str] = []
    state = _state(project, False)
    state.cb = orchestrator.Callbacks(on_log=log.append)
    with pytest.raises(RpgGenError) as exc:
        orchestrator.phase_preflight(state)
    assert exc.value.issue.code == "REGEN-006"
    assert any("Version 2.0.0" in line for line in log)
    # accepted: passes and records the info
    state = _state(project, True)
    orchestrator.phase_preflight(state)
    assert state.runtime is not None and state.runtime.new == "2.0.0"
    # a first generation never needs confirmation
    state = _state(tmp_path / "fresh", False)
    orchestrator.phase_preflight(state)
    assert state.runtime is not None and state.runtime.old is None


def test_report_data_and_markdown_carry_the_runtime_version(tmp_path: Path) -> None:
    state = _state(tmp_path, False)
    state.runtime = runtime_version.UpgradeInfo("1.0.0", "1.1.0")
    assert orchestrator._report_data(state, True)["runtime_version"] == "1.1.0"
    md = report.build_markdown(
        config.default_for("T", []), catalog.Catalog(), [], True, runtime_version="1.1.0"
    )
    assert "Runtime 1.1.0" in md


# ------------------------------------------------------------------ README


def _cfg(name: str = "My Game") -> config.GeneratorConfig:
    return config.default_for(name, [config.PackRef("pack_a", "x", "0" * 64, "folder")])


def test_template_only_has_known_placeholders() -> None:
    template = paths.templates_root() / "project_files" / "README.template.md"
    text = template.read_text(encoding="utf-8")
    assert set(re.findall(r"\{(\w*)\}", text)) == {
        "project_name",
        "archetype",
        "runtime_version",
        "godot_version",
        "packs_list",
    }
    assert text.count("{") == text.count("}")
    for needle in ("addons/rpg_runtime", "generated/", ".rpggen-new", "MIT-0", "F5"):
        assert needle in text


def test_readme_is_rendered_into_the_project(tmp_path: Path) -> None:
    stg = staging.create_staging(tmp_path / "t")
    staging.write_project_files(stg, _cfg("Brace {x} Game"), catalog.Catalog())
    text = (stg.staging / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Brace {x} Game")
    assert "- pack_a" in text
    assert "generated-owned" in text
    assert not re.search(r"\{(project_name|packs_list|runtime_version)\}", text)
    version = runtime_version.read_version(paths.templates_root())
    assert f"RPG runtime version: {version}" in text
    assert "\r" not in text


def test_readme_is_generated_owned_in_the_ledger() -> None:
    assert ledger.is_covered("README.md")
    assert ledger.owner_of("README.md") == "generated"
    assert "README.md" not in ledger.MERGE_MANAGED


def test_regeneration_rewrites_an_edited_readme_in_staging(tmp_path: Path) -> None:
    target = tmp_path / "t"
    jsonio.write(target / paths.CONFIG, {})
    (target / "README.md").write_text("my notes\n", encoding="utf-8")
    stg = staging.create_staging(target)
    staging.write_project_files(stg, _cfg(), catalog.Catalog())
    assert (stg.staging / "README.md").read_text(encoding="utf-8").startswith("# My Game")
    # an up-to-date README is left alone (a no-op regeneration changes nothing)
    before = (stg.staging / "README.md").stat().st_mtime_ns
    staging.write_project_files(stg, _cfg(), catalog.Catalog())
    assert (stg.staging / "README.md").stat().st_mtime_ns == before
