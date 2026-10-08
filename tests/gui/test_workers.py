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
    assert phases[0].startswith("Reading") and phases[-1].startswith("Analyzing images")


def test_analyze_packs_can_be_cancelled(qtbot) -> None:
    state = WizardState(pack_sources=[SYNTH / "basic16", SYNTH / "mixed"])
    worker = workers.Worker(workers.analyze_packs, state)
    worker.cancel()
    with qtbot.waitSignal(worker.signals.failed, timeout=10000) as blocker:
        worker.start()
    assert isinstance(blocker.args[0], workers.Cancelled)


# ------------------------------------------------------------------------ analysis (T12.06)


def _many_images(root: Path, count: int = 200) -> Path:
    from PIL import Image

    pack = root / "many"
    (pack / "tiles").mkdir(parents=True)
    for i in range(count):
        Image.new("RGBA", (16, 16), (i % 256, (i * 7) % 256, (i * 13) % 256, 255)).save(
            pack / "tiles" / f"t{i:03d}.png"
        )
    return pack


def _run(qtbot, fn, *args):
    worker = workers.Worker(fn, *args)
    outcome: dict = {}
    worker.signals.finished.connect(lambda r: outcome.setdefault("result", r))
    worker.signals.failed.connect(lambda e: outcome.setdefault("error", e))
    progress: list[tuple] = []
    worker.signals.progress.connect(lambda *a: progress.append(a))
    return worker, outcome, progress


def test_progress_is_throttled_and_every_stage_ends_on_its_total() -> None:
    from rpggen.core.orchestrator import Callbacks

    seen: list[tuple] = []
    sink = workers.ProgressSink(Callbacks(on_phase=lambda *a: seen.append(a)), interval=3600)
    for i in range(1, 51):  # an hour of throttle: only the first call and the end go through
        sink.count("Reading files", i, 50)
    for i in range(1, 11):
        sink.count("Analyzing images", i, 10)
    assert seen == [
        ("Reading files — 1 of 50", 1, 50),
        ("Reading files — 50 of 50", 50, 50),
        ("Analyzing images — 1 of 10", 1, 10),
        ("Analyzing images — 10 of 10", 10, 10),
    ]
    sink.bytes("Extracting a.zip", 3 << 30, 4 << 30)
    assert seen[-1][0] == "Extracting a.zip — 3.0 GB of 4.0 GB" and seen[-1][2] == 4 << 20


def test_a_zipped_pack_reports_extraction_and_every_stage_in_order(qtbot, tmp_path) -> None:
    import zipfile

    from PIL import Image

    pack = _many_images(tmp_path, 40)
    archive_file = tmp_path / "many.zip"
    with zipfile.ZipFile(archive_file, "w") as zf:
        for png in pack.rglob("*.png"):
            zf.write(png, png.relative_to(pack).as_posix())
    assert Image.open(pack / "tiles" / "t000.png").size == (16, 16)
    state = WizardState(pack_sources=[archive_file])
    worker, outcome, progress = _run(qtbot, workers.analyze_packs, state)
    with qtbot.waitSignal(worker.signals.finished, timeout=60000):
        worker.start()
    labels = [p[0].split(" — ")[0] for p in progress]
    for stage in ("Reading many.zip", "Extracting many.zip", "Reading files", "Analyzing images"):
        assert stage in labels, labels
    assert labels.index("Extracting many.zip") < labels.index("Reading files")
    assert labels.index("Reading files") < labels.index("Analyzing images")
    by_stage: dict[str, list[int]] = {}
    for label, i, n in progress:
        stage = label.split(" — ")[0]
        if n:
            assert 0 <= i <= n
            by_stage.setdefault(stage, []).append(i)
    for stage, values in by_stage.items():
        assert values == sorted(values), stage  # monotonic
        assert values[-1] > 0


def test_cancel_during_analysis_returns_fast_and_leaves_no_partial_folder(
    qtbot, tmp_path, cache_dir
) -> None:
    import zipfile

    pack = _many_images(tmp_path, 200)
    archive_file = tmp_path / "many.zip"
    with zipfile.ZipFile(archive_file, "w") as zf:
        for png in pack.rglob("*.png"):
            zf.write(png, png.relative_to(pack).as_posix())
    for source in (pack, archive_file):
        state = WizardState(pack_sources=[source])
        worker, outcome, progress = _run(qtbot, workers.analyze_packs, state)
        stopped = {}

        def on_progress(label: str, i: int, n: int, worker=worker, stopped=stopped) -> None:
            if label.startswith("Analyzing images") and i >= 10 and "at" not in stopped:
                stopped["at"] = time.monotonic()
                worker.cancel()

        worker.signals.progress.connect(on_progress)
        with qtbot.waitSignal(worker.signals.failed, timeout=10000) as blocker:
            worker.start()
        assert isinstance(blocker.args[0], workers.Cancelled)
        assert time.monotonic() - stopped["at"] < 2.0
    extracted = cache_dir / "extracted"
    assert not extracted.exists() or not [
        p for p in extracted.iterdir() if p.name.endswith(".partial")
    ]


def test_cancel_says_stopping_disables_the_button_and_waits_for_the_worker(
    qtbot, monkeypatch
) -> None:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QProgressDialog, QPushButton, QWidget

    from rpggen.gui.widgets import analysis_progress

    def slow(state, *, callbacks):
        callbacks.on_phase("Reading files — 1 of 9", 1, 9)
        while not callbacks.is_cancelled():
            time.sleep(0.01)
        time.sleep(0.2)  # the worker needs a moment to stop
        raise workers.Cancelled

    monkeypatch.setattr(workers, "analyze_packs", slow)
    parent = QWidget()
    qtbot.addWidget(parent)
    seen: dict = {}

    def click_cancel() -> None:
        dialog = parent.findChild(QProgressDialog, "analysisProgress")
        assert dialog is not None and dialog.labelText() == "Reading files — 1 of 9"
        button = dialog.findChild(QPushButton)
        button.click()
        seen["label"] = dialog.labelText()
        seen["enabled"] = button.isEnabled()
        seen["visible"] = dialog.isVisible()

    QTimer.singleShot(150, click_cancel)
    assert analysis_progress.run_analysis(parent, WizardState()) is False
    assert seen == {"label": "Stopping…", "enabled": False, "visible": True}
