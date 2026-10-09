import re


def test_closing_while_running_asks_and_cancels(qtbot) -> None:
    from rpggen.gui.pages.generate_page import GeneratePage

    page = GeneratePage()
    qtbot.addWidget(page)
    assert page.request_close()  # nothing runs
    cancelled: list[bool] = []

    class FakeWorker:
        class signals:  # noqa: N801
            class _S:
                def connect(self, fn):
                    fn()  # delivered at once so the wait ends

            finished = _S()
            failed = _S()

        def cancel(self) -> None:
            cancelled.append(True)

    page.worker = FakeWorker()  # type: ignore[assignment]
    page.running = True
    page.ask_stop_and_close = lambda: False  # type: ignore[method-assign]
    assert not page.request_close() and not cancelled
    page.ask_stop_and_close = lambda: True  # type: ignore[method-assign]
    page.current_phase = "import"
    assert page.request_close(timeout_ms=100)
    assert cancelled and page.cancelled
    assert "Stopping Godot" in page.status_label.text()


# ------------------------------------------------------------------------ skipped checks (T12.07)


def _skipping_run(tmp_path, monkeypatch, code="ENV-010", phase="export"):
    from rpggen.core import orchestrator
    from rpggen.errors import CODES, Issue
    from rpggen.gui import workers
    from rpggen.gui.pages.generate_page import PHASES, GeneratePage
    from tests.gui.test_generate_results import _ok_result, _state

    state = _state(tmp_path)
    info = CODES[code]

    def fake(
        cfg,
        cat,
        target,
        godot,
        placeholders,
        git_message=None,
        force=False,
        accept=False,
        *,
        callbacks,
    ):
        for i, name in enumerate(PHASES, start=1):
            callbacks.on_phase(name, i, len(PHASES))
            if name == phase:
                callbacks.on_skip(phase, code)
        result = _ok_result(tmp_path, [Issue(code, info.severity, info.message, info.fix)])
        result.skipped = {phase: code}
        result.timings = dict.fromkeys(PHASES, 1.0)
        assert isinstance(result, orchestrator.RunResult)
        return result

    monkeypatch.setattr(workers, "generate", fake)
    page = GeneratePage()
    page.show_notification = lambda title, text: None  # type: ignore[method-assign]
    return page, state, PHASES.index(phase)


def test_a_skipped_check_never_shows_a_tick_or_a_duration(qtbot, tmp_path, monkeypatch) -> None:
    page, state, row = _skipping_run(tmp_path, monkeypatch)
    qtbot.addWidget(page)
    page.enter(state)
    qtbot.waitUntil(lambda: not page.running, timeout=20000)
    item = page.phase_list.item(row)
    assert (
        item.text().startswith("–") and "skipped: export templates are not installed" in item.text()
    )
    assert "✔" not in item.text() and not re.search(r"\d+ s", item.text())  # no duration
    assert "ENV-010" in item.toolTip() and "Install export templates" in item.toolTip()
    assert page.phase_list.item(row - 1).text().startswith("✔")  # the others are as before


def test_the_smoke_test_turned_off_is_shown_as_skipped_too(qtbot, tmp_path, monkeypatch) -> None:
    page, state, row = _skipping_run(tmp_path, monkeypatch, "VAL-021", "smoke")
    qtbot.addWidget(page)
    page.enter(state)
    qtbot.waitUntil(lambda: not page.running, timeout=20000)
    assert "skipped: turned off in the config" in page.phase_list.item(row).text()


# ------------------------------------------------------------------------ remaining time (T13.07)


def test_the_estimate_is_set_per_phase_and_never_counts_down(qtbot) -> None:
    import time

    from rpggen.core import app_settings
    from rpggen.gui.pages.generate_page import ICON_RUNNING, PHASES, GeneratePage

    page = GeneratePage()
    qtbot.addWidget(page)
    # a first run: no history, no estimate anywhere
    page.running = True
    page._run_started = page._phase_started = time.monotonic()
    page._on_progress("build", PHASES.index("build") + 1, len(PHASES))
    page._tick()
    assert "left" not in page.elapsed_label.text() and "usual" not in page.elapsed_label.text()
    row = page.phase_list.item(PHASES.index("build")).text()
    assert row.startswith(ICON_RUNNING) and "left" not in row
    assert page.estimates_for("build") == (None, None)
    # with history: 0.4 s an asset for the build, 10 s for every later phase
    history = {name: [[100, 10.0]] for name in PHASES}
    history["build"] = [[100, 30.0], [100, 40.0], [100, 50.0]]
    page._history, page._assets = history, 100
    page.current_phase = ""
    page._on_progress("build", PHASES.index("build") + 1, len(PHASES))
    after = len(PHASES) - PHASES.index("build") - 1
    assert page.estimates_for("build") == (40.0, 40.0 + 10.0 * after)
    assert "about 40 s left" in page.phase_list.item(PHASES.index("build")).text()
    page._tick()
    total = page.round_seconds(40.0 + 10.0 * after)
    assert f"about {total} s left" in page.elapsed_label.text()
    # ten seconds into the phase the numbers are the same: it does not count down by the clock
    page._phase_started -= 10
    page._tick()
    assert "about 40 s left" in page.phase_list.item(PHASES.index("build")).text()
    assert f"about {total} s left" in page.elapsed_label.text()
    # past the estimate it says so, in the row and at the top
    page._phase_started -= 60
    page._tick()
    assert "taking longer than usual" in page.phase_list.item(PHASES.index("build")).text()
    assert "taking longer than usual" in page.elapsed_label.text()
    # twice the assets: the scaling phases take twice as long, the fixed ones do not
    page._assets = 200
    assert page.estimates_for("build")[0] == 80.0
    assert page.estimates_for("report") == (10.0, 10.0)
    assert page.round_seconds(2.0) == 5 and page.round_seconds(42.4) == 40
    assert app_settings.estimate(history, "promote", 200) == 10.0
    page.running = False
