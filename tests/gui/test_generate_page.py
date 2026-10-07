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
