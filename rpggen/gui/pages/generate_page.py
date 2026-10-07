"""Page 6: run the pipeline in a worker and show its progress."""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import orchestrator, vcs
from rpggen.errors import Issue, IssueList
from rpggen.gui import workers
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.log_view import LogView

PHASES = orchestrator.PHASES_M1
ICON_PENDING = "○"
ICON_RUNNING = "⏳"
ICON_DONE = "✔"
ICON_FAILED = "✖"


class GeneratePage(WizardPage):
    title = "Generate"
    next_label = "Show results"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.worker: workers.Worker | None = None
        self.running = False
        self.cancelled = False
        self.allow_back = False
        self.allow_next = False
        layout = QVBoxLayout(self)
        self.status_label = QLabel()
        self.status_label.setObjectName("generateStatus")
        layout.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setObjectName("generateProgress")
        self.progress.setRange(0, len(PHASES))
        layout.addWidget(self.progress)
        self.phase_list = QListWidget()
        self.phase_list.setObjectName("phaseList")
        self.phase_list.setMaximumHeight(24 * (len(PHASES) + 1))
        for _ in PHASES:
            self.phase_list.addItem(QListWidgetItem())
        self._set_icons({})
        layout.addWidget(self.phase_list)
        self.log_view = LogView()
        layout.addWidget(self.log_view, 1)
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setObjectName("generateCancel")
        self.cancel_button.clicked.connect(self.cancel)
        layout.addWidget(self.cancel_button)

    # ------------------------------------------------------------------ phase list

    def _set_icons(self, icons: dict[str, str]) -> None:
        for i, name in enumerate(PHASES):
            item = self.phase_list.item(i)
            if item is not None:
                item.setText(f"{icons.get(name, ICON_PENDING)}  {name}")

    def _phase_icon(self, name: str) -> str:
        item = self.phase_list.item(PHASES.index(name))
        return item.text().split()[0] if item is not None else ""

    # ------------------------------------------------------------------ wizard hooks

    def enter(self, state: WizardState) -> None:
        self.state = state
        if self.running:
            return
        if state.run_result is not None and state.run_result.ok:
            self._show_finished(state.run_result)
            return
        self.start()

    def validate(self, state: WizardState) -> list[Issue]:
        return [] if not self.running else [form_error(self.tr("Generation is running."))]

    def leave(self, state: WizardState) -> bool | None:
        return False if self.running else None

    # ------------------------------------------------------------------ running

    def ask_editor_open(self) -> bool:
        """The Godot editor seems to have the project open: True to check again (Retry)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(self.tr("Godot editor is open"))
        box.setText(
            self.tr(
                "Close the Godot editor before regenerating; open scenes may be overwritten "
                "when the editor saves."
            )
        )
        retry = box.addButton(self.tr("Retry"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return box.clickedButton() is retry

    def git_message(self) -> str | None:
        """The commit message when the user wants a commit (default: on for a new project)."""
        state = self.state
        assert state is not None
        want = state.git_commit
        if want is None:
            want = vcs.git_available() and not state.regenerating
        if not want or not vcs.git_available():
            return None
        return "rpggen: regenerate project" if state.regenerating else "rpggen: generate project"

    def start(self) -> None:
        state = self.state
        assert state is not None
        self.cancelled = False
        self.log_view.clear()
        self._set_icons({})
        self.progress.setValue(0)
        if state.config is None or state.target is None or state.godot_exe is None:
            self._on_failed(
                IssueList().add("GUI-001", reason="the project, output folder or Godot is not set")
            )
            return
        self.running = True
        self.allow_back = False
        self.allow_next = False
        self.cancel_button.setEnabled(True)
        self.status_label.setText(self.tr("Generating…"))
        state.run_result = None
        worker = workers.Worker(
            workers.generate,
            copy.deepcopy(state.config),
            state.catalog,
            Path(state.target),
            Path(state.godot_exe),
            sorted(state.placeholders),
            self.git_message(),
            state.force_while_open,
        )
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self.log_view.append_line)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self.worker = worker
        self.changed.emit()
        worker.start()

    def cancel(self) -> None:
        if self.worker is not None and self.running:
            self.cancelled = True
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText(self.tr("Cancelling…"))

    def _on_progress(self, name: str, index: int, total: int) -> None:
        if name not in PHASES:
            return
        icons = {p: ICON_DONE for p in PHASES[: index - 1]}
        icons[name] = ICON_RUNNING
        self._set_icons(icons)
        self.progress.setMaximum(total)
        self.progress.setValue(index - 1)
        self.status_label.setText(self.tr("Phase {0} of {1}: {2}").format(index, total, name))

    def _stop_running(self) -> None:
        self.running = False
        self.cancel_button.setEnabled(False)
        self.worker = None

    def _on_finished(self, result: orchestrator.RunResult) -> None:
        self._stop_running()
        if self.cancelled:
            self._show_cancelled()
            return
        editor_open = not result.ok and any(i.code == "REGEN-005" for i in result.issues)
        if editor_open and self.ask_editor_open():
            self.start()
            return
        if self.state is not None:
            self.state.run_result = result
        self._show_finished(result)

    def _on_failed(self, error: object) -> None:
        self._stop_running()
        issue = (
            error
            if isinstance(error, Issue)
            else IssueList().add("GUI-001", reason=f"{type(error).__name__}: {error}")
        )
        target = self.state.target if self.state and self.state.target else Path(".")
        result = orchestrator.RunResult(False, Path(target), [issue], None, None)
        if self.state is not None:
            self.state.run_result = result
        self._show_finished(result)

    def _show_cancelled(self) -> None:
        self.status_label.setText(self.tr("Generation was cancelled; nothing was delivered."))
        self.status_label.setProperty("state", "warning")
        self.allow_back = True
        self.allow_next = False
        self.changed.emit()

    def _show_finished(self, result: orchestrator.RunResult) -> None:
        if result.ok:
            self._set_icons({p: ICON_DONE for p in PHASES})
            self.progress.setValue(len(PHASES))
            self.status_label.setText(self.tr("Generation finished."))
            self.status_label.setProperty("state", "ok")
            self.allow_back = False
        else:
            icons = (
                {p: ICON_DONE for p in PHASES[: PHASES.index(result.failed_phase)]}
                if (result.failed_phase in PHASES)
                else {}
            )
            if result.failed_phase in PHASES:
                icons[result.failed_phase] = ICON_FAILED
            self._set_icons(icons)
            self.status_label.setText(self.tr("Generation failed."))
            self.status_label.setProperty("state", "error")
            self.allow_back = True
        self.allow_next = True
        self.changed.emit()
