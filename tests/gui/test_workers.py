from __future__ import annotations

import time
from pathlib import Path

from rpggen.errors import Issue
from rpggen.gui import workers
from rpggen.gui.state import WizardState

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def test_worker_emits_finished_and_progress(qtbot) -> None:
    def job(n, *, callbacks):
        for i in range(n):
            callbacks.on_phase("step", i + 1, n)
        callbacks.on_log("done")
        return n * 2

    worker = workers.Worker(job, 3)
    progress: list[tuple] = []
    logs: list[str] = []
    worker.signals.progress.connect(lambda *a: progress.append(a))
    worker.signals.log.connect(logs.append)
    with qtbot.waitSignal(worker.signals.finished, timeout=3000) as blocker:
        worker.start()
    assert blocker.args == [6]
    assert progress[-1] == ("step", 3, 3) and logs == ["done"]


def test_cancel_stops_a_looping_function_within_a_second(qtbot) -> None:
    def loop(*, callbacks):
        while not callbacks.is_cancelled():
            time.sleep(0.01)
        raise workers.Cancelled

    worker = workers.Worker(loop)
    with qtbot.waitSignal(worker.signals.failed, timeout=3000) as blocker:
        worker.start()
        qtbot.wait(50)
        started = time.monotonic()
        worker.cancel()
    assert time.monotonic() - started < 1.0
    assert isinstance(blocker.args[0], workers.Cancelled)


def test_exception_emits_failed(qtbot) -> None:
    def boom(*, callbacks):
        raise ValueError("boom")

    worker = workers.Worker(boom)
    with qtbot.waitSignal(worker.signals.failed, timeout=3000) as blocker:
        worker.start()
    assert isinstance(blocker.args[0], ValueError)


def test_rpggen_error_emits_its_issue(qtbot) -> None:
    from rpggen.errors import RpgGenError

    def boom(*, callbacks):
        raise RpgGenError("ENV-001", path="x")

    worker = workers.Worker(boom)
    with qtbot.waitSignal(worker.signals.failed, timeout=3000) as blocker:
        worker.start()
    assert isinstance(blocker.args[0], Issue) and blocker.args[0].code == "ENV-001"


def test_analyze_packs_fills_the_state(qtbot) -> None:
    state = WizardState(pack_sources=[SYNTH / "basic16"])
    worker = workers.Worker(workers.analyze_packs, state)
    phases: list[str] = []
    worker.signals.progress.connect(lambda name, i, n: phases.append(name))
    with qtbot.waitSignal(worker.signals.finished, timeout=60000) as blocker:
        worker.start()
    result = blocker.args[0]
    workers.apply_analysis(state, result)
    assert state.catalog is not None and state.catalog.assets
    assert len(state.opened_packs) == len(state.inventories) == 1
    assert phases[0].startswith("Reading") and phases[-1] == "Analyzing images"


def test_analyze_packs_can_be_cancelled(qtbot) -> None:
    state = WizardState(pack_sources=[SYNTH / "basic16", SYNTH / "mixed"])
    worker = workers.Worker(workers.analyze_packs, state)
    worker.cancel()
    with qtbot.waitSignal(worker.signals.failed, timeout=10000) as blocker:
        worker.start()
    assert isinstance(blocker.args[0], workers.Cancelled)
