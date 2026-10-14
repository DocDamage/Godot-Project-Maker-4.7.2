"""A Godot that crashes while importing is run once more (BUILD-006); any other failure is not."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rpggen.core import godot, orchestrator
from rpggen.errors import IssueList


def _run(code: int, *, timed_out: bool = False, cancelled: bool = False) -> godot.GodotRun:
    return godot.GodotRun(code, "", "", Path("import.log"), timed_out, cancelled)


@pytest.mark.parametrize(
    ("run", "crashed"),
    [
        (_run(0), False),
        (_run(1), False),  # Godot reported an error and exited
        (_run(-1, timed_out=True), False),
        (_run(-1, cancelled=True), False),
        (_run(-6), True),  # SIGABRT on Linux
        (_run(-11), True),  # SIGSEGV
        (_run(3221225477), True),  # 0xC0000005, an access violation on Windows
        (_run(0xC0000409), True),  # a stack buffer overrun on Windows
    ],
)
def test_a_crash_is_told_from_an_error(run: godot.GodotRun, crashed: bool) -> None:
    assert godot.crashed(run) is crashed


def _state(tmp_path: Path) -> SimpleNamespace:
    cb = SimpleNamespace(
        on_log=lambda _line: None,
        on_step=lambda *_a: None,
        is_cancelled=lambda: False,
    )
    return SimpleNamespace(
        staging=SimpleNamespace(staging=tmp_path),
        log_dir=tmp_path / "logs",
        godot_exe=tmp_path / "godot.exe",
        cb=cb,
        issues=IssueList(),
    )


def _runs(monkeypatch: pytest.MonkeyPatch, codes: list[int]) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(godot, "find_console_exe", lambda exe: exe)

    def run_godot(*_a, **_k) -> godot.GodotRun:
        calls.append(len(calls))
        return _run(codes[len(calls) - 1])

    monkeypatch.setattr(godot, "run_godot", run_godot)
    return calls


def test_an_import_that_crashes_once_is_run_again_and_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _runs(monkeypatch, [-6, 0])
    state = _state(tmp_path)
    orchestrator.phase_import(state)
    assert len(calls) == 2
    assert [(i.code, i.severity.name) for i in state.issues] == [("BUILD-006", "INFO")]


def test_an_import_that_crashes_twice_fails_with_its_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _runs(monkeypatch, [-6, -6, 0])
    state = _state(tmp_path)
    with pytest.raises(orchestrator._Stop):
        orchestrator.phase_import(state)
    assert len(calls) == orchestrator.IMPORT_ATTEMPTS
    assert [i.code for i in state.issues] == ["BUILD-006", "BUILD-001"]


def test_an_import_that_fails_without_crashing_is_not_run_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _runs(monkeypatch, [1, 0])
    state = _state(tmp_path)
    with pytest.raises(orchestrator._Stop):
        orchestrator.phase_import(state)
    assert len(calls) == 1
    assert [i.code for i in state.issues] == ["BUILD-001"]
