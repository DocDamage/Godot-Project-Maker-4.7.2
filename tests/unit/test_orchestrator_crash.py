"""T12.23: an unexpected exception is a report with a crash log, not a traceback."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import config, diagnostics, orchestrator

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "_rpggen"))


def _config(tmp_path: Path) -> config.GeneratorConfig:
    return orchestrator.default_config_for_pack(SYNTH / "basic16", "Crash Test")


def _fake_godot_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    from rpggen.core import godot

    monkeypatch.setattr(godot, "detect_version", lambda exe: (4, 7, 2, "stable"))


def test_a_phase_that_raises_gives_a_failed_result_with_build_005(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_godot_checks(monkeypatch)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")

    def boom(state) -> None:
        raise ZeroDivisionError("the divisor was zero")

    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "catalog", boom)
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(_config(tmp_path), None, target, exe)
    assert not result.ok and result.failed_phase == "catalog" and not result.cancelled
    issue = next(i for i in result.issues if i.code == "BUILD-005")
    assert issue.severity.value == "error"
    assert (
        "phase catalog" in issue.message
        and "ZeroDivisionError: the divisor was zero" in issue.message
    )
    assert issue.fix == "Export a diagnostic bundle and report it."
    failed = result.failed_staging
    assert failed is not None and failed.is_dir() and not (target / ".rpggen_staging").exists()
    crash = (failed / "rpggen" / "logs" / "crash.log").read_text(encoding="utf-8")
    assert "Traceback" in crash and "ZeroDivisionError" in crash and "boom" in crash
    assert result.report_path is not None and result.report_path.is_file()
    assert "BUILD-005" in (failed / "GENERATION_REPORT.md").read_text(encoding="utf-8")


def test_the_diagnostic_bundle_of_the_failed_folder_carries_the_crash_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import zipfile

    _fake_godot_checks(monkeypatch)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "install", lambda state: 1 / 0)
    result = orchestrator.run_in_memory(_config(tmp_path), None, tmp_path / "out", exe)
    bundle = tmp_path / "bundle.zip"
    diagnostics.make_bundle(result.failed_staging, bundle, None)
    with zipfile.ZipFile(bundle) as zf:
        assert "logs/crash.log" in zf.namelist()
        assert "ZeroDivisionError" in zf.read("logs/crash.log").decode("utf-8")


def test_a_crash_before_the_work_folder_exists_is_still_a_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_godot_checks(monkeypatch)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")
    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "preflight", lambda state: {}["nothing"])
    result = orchestrator.run_in_memory(_config(tmp_path), None, tmp_path / "out", exe)
    assert not result.ok and result.failed_staging is None and result.failed_phase == "preflight"
    assert [i.code for i in result.issues] == ["BUILD-005"]
    assert "KeyError" in result.issues[0].message


@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
def test_ctrl_c_and_exit_keep_their_old_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signal: type[BaseException]
) -> None:
    _fake_godot_checks(monkeypatch)
    exe = tmp_path / "godot.exe"
    exe.write_text("x")

    def stop(state) -> None:
        raise signal()

    monkeypatch.setitem(orchestrator.PHASE_FUNCS, "catalog", stop)
    target = tmp_path / "out"
    with pytest.raises(signal):
        orchestrator.run_in_memory(_config(tmp_path), None, target, exe)
    assert not (target / ".rpggen_staging").exists()  # the work folder was moved away
