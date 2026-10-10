"""Page 6: run the pipeline in a worker and show its progress."""

from __future__ import annotations

import copy
import time
from pathlib import Path

from PySide6.QtCore import QT_TRANSLATE_NOOP, QEventLoop, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QWidget,
)

from rpggen.core import app_settings, orchestrator, pack_sniff, vcs
from rpggen.errors import CODES, Issue, IssueList
from rpggen.gui import icons, taskbar, theme, workers
from rpggen.gui.dialogs.promotion_dialog import PromotionDialog
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import buttons, stepper
from rpggen.gui.widgets.card import INFO, Banner, Card
from rpggen.gui.widgets.log_view import LogView

PHASES = orchestrator.PHASES_M1
GODOT_PHASES = {"import", "build", "validate", "smoke", "export"}
PHASE_LABELS = {
    "preflight": "Checking your setup",
    "stage": "Preparing a work folder",
    "install": "Copying your packs and the game code",
    "catalog": "Reading what is in your packs",
    "import": "Importing assets into Godot",
    "build": "Building the game",
    "validate": "Checking the game for problems",
    "smoke": "Playing the game to test it",
    "export": "Test-exporting the game",
    "promote": "Delivering the project",
    "report": "Writing the report",
}
ICON_PENDING = "○"
ICON_RUNNING = "⏳"
ICON_DONE = "✔"
ICON_FAILED = "✖"
ICON_SKIPPED = "–"
WRITING_PHASES = ("promote", "report")  # from here on the project folder is being written
# what the step delegate paints for a row's glyph
STEP_STATES = {
    ICON_PENDING: stepper.PENDING,
    ICON_RUNNING: stepper.RUNNING,
    ICON_DONE: stepper.DONE,
    ICON_FAILED: stepper.ERROR,
    ICON_SKIPPED: stepper.SKIPPED,
}
# why a check did not run, in a few words (the issue's own text is in the tooltip)
SKIP_REASONS = {
    "ENV-010": "export templates are not installed",
    "VAL-021": "turned off in the config",
    "VAL-022": "turned off in the config",
    "REGEN-011": "nothing changed since the last run",
}


class GeneratePage(WizardPage):
    title = "Generate"
    purpose = str(
        QT_TRANSLATE_NOOP(
            "WizardPage", "rpggen builds, checks and plays the project before it hands it over."
        )
    )
    help_anchor = "2. First run with the sample pack"
    next_label = "Show results"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.worker: workers.Worker | None = None
        self.running = False
        self.cancelled = False
        self.current_phase = ""
        self.allow_back = False
        self.allow_next = False
        layout = self.page_layout()
        # a sample run from the welcome view (T15.22): what it does, and that Back is open
        self.sample_banner = Banner(
            INFO,
            self.tr("Using the default options. Back changes them; nothing was written yet."),
        )
        self.sample_banner.setObjectName("sampleBanner")
        self.sample_banner.setVisible(False)
        layout.addWidget(self.sample_banner)
        self.status_label = QLabel()
        self.status_label.setObjectName("generateStatus")
        self.status_label.setProperty("role", "section")
        layout.addWidget(self.status_label)
        # what the running Godot phase is doing: "Building tile sets (7 of 31)", or the last line
        # Godot printed while it imports
        self.step_label = QLabel()
        self.step_label.setObjectName("generateStep")
        self.step_label.setProperty("muted", True)
        layout.addWidget(self.step_label)
        self.elapsed_label = QLabel()
        self.elapsed_label.setObjectName("elapsedLabel")
        self.elapsed_label.setProperty("role", "caption")
        self.header.add_widget(self.elapsed_label)  # the time, in the header's slot (T15.15)
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._tick)
        self._run_started = 0.0
        self._phase_started = 0.0
        self._durations: dict[str, float] = {}
        self._skipped: dict[str, str] = {}  # phase -> code: a check that did not run
        # this computer's phase times (T13.07), read once per run; the estimates of the running
        # phase and of everything still to do are worked out when a phase starts
        self._history: dict[str, list[list[float]]] = {}
        self._assets = 0
        self._phase_estimate: float | None = None
        self._rest_estimate: float | None = None
        self.progress = QProgressBar()
        self.progress.setObjectName("generateProgress")
        self.progress.setRange(0, len(PHASES))
        self.progress.setTextVisible(False)
        # the bar says no number itself: the percentage is beside it
        self.percent_label = QLabel("0 %")
        self.percent_label.setObjectName("generatePercent")
        self.percent_label.setProperty("role", "caption")
        self.percent_label.setMinimumWidth(40)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.percent_label)
        layout.addLayout(progress_row)
        self.progress.valueChanged.connect(lambda _v: self._show_percent())
        # the phases as a checklist (T15.15): the step delegate paints a circle per phase;
        # the rows keep their text (glyph, name, note) for the tests and the screen reader
        self.phase_list = QListWidget()
        self.phase_list.setObjectName("phaseList")
        self.phase_list.setToolTip(self.tr("The steps of the generation and how long each took"))
        self.phase_delegate = stepper.StepDelegate(self.phase_list, compact=True)
        self.phase_list.setItemDelegate(self.phase_delegate)
        self.phase_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.phase_list.setFixedHeight(self.phase_delegate.row_height * len(PHASES) + 6)
        for _ in PHASES:
            self.phase_list.addItem(QListWidgetItem())
        self._spinner = QTimer(self)  # turns the ring of the running phase
        self._spinner.setInterval(80)
        self._spinner.timeout.connect(self._spin)
        self._set_icons({})
        layout.addWidget(self.phase_list)
        self.details_button = QPushButton(self.tr("Show details"))
        self.details_button.setObjectName("generateDetails")
        self.details_button.setCheckable(True)
        self.details_button.setToolTip(self.tr("Show the log of the run"))
        buttons.set_kind(self.details_button, buttons.QUIET)
        icons.set_icon(self.details_button, "chevron-right")
        layout.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.log_card = Card(margin=theme.px("space_8"))
        self.log_card.setObjectName("logCard")
        self.log_card.setVisible(False)
        self.log_view = LogView()
        self.log_view.setVisible(False)
        self.log_card.box.addWidget(self.log_view, 1)
        layout.addWidget(self.log_card, 1)
        self.log_note = QLabel(
            self.tr(
                "Older lines are not shown here; the whole log is in the project's rpggen/logs."
            )
        )
        self.log_note.setObjectName("logNote")
        self.log_note.setProperty("muted", True)
        self.log_note.setProperty("role", "caption")
        self.log_note.setVisible(False)
        self.log_card.box.addWidget(self.log_note)  # the card's footer
        self.log_view.truncated.connect(lambda: self.log_note.setVisible(self.log_card.isVisible()))
        layout.addStretch(0)
        self.details_button.toggled.connect(self._show_details)
        # Cancel is the page's button, but while a run is on the window shows it in its button
        # bar where Next is (T15.03, T15.15): ``bar_button`` is what the window looks for
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setObjectName("generateCancel")
        self.cancel_button.setToolTip(self.tr("Stop the generation: nothing is delivered"))
        buttons.set_kind(self.cancel_button, buttons.SECONDARY)
        self.cancel_button.setMinimumWidth(buttons.BAR_BUTTON_WIDTH)
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.setVisible(False)
        self.bar_button = self.cancel_button
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------ phase list

    def _set_icons(self, icons: dict[str, str]) -> None:
        for i, name in enumerate(PHASES):
            item = self.phase_list.item(i)
            if item is None:
                continue
            label = self.tr(PHASE_LABELS.get(name, name))
            code = self._skipped.get(name)
            if code and icons.get(name) in (ICON_RUNNING, ICON_DONE):
                # a check that did not run is never shown as passed
                reason = self.tr(
                    SKIP_REASONS.get(code, CODES[code].message if code in CODES else code)
                )
                item.setText(f"{ICON_SKIPPED}  {label}  ·  {self.tr('skipped')}: {reason}")
                fix = CODES[code].fix if code in CODES else ""
                item.setToolTip(f"{code}: {fix}" if fix else code)
                item.setData(stepper.StateRole, stepper.SKIPPED)
                item.setData(stepper.LabelRole, f"{label}  ·  {self.tr('skipped')}: {reason}")
                item.setData(stepper.NoteRole, "")
                continue
            text = f"{icons.get(name, ICON_PENDING)}  {label}"
            note = ""
            if name in self._durations and icons.get(name) in (ICON_DONE, ICON_FAILED):
                note = f"{self._durations[name]:.0f} s"
            elif icons.get(name) == ICON_RUNNING and name == self.current_phase:
                note = self.phase_note(time.monotonic() - self._phase_started)
            if note:
                text += f"  ·  {note}"
            item.setText(text)
            item.setToolTip(name)
            item.setData(stepper.StateRole, STEP_STATES.get(icons.get(name, ICON_PENDING)))
            item.setData(stepper.LabelRole, label)
            item.setData(stepper.NoteRole, note)
        running = ICON_RUNNING in icons.values() and not theme.reduce_motion()
        if running and not self._spinner.isActive():
            self._spinner.start()
        elif not running and self._spinner.isActive():
            self._spinner.stop()

    def _spin(self) -> None:
        """One step of the running phase's ring (a still ring with reduce motion)."""
        self.phase_delegate.spin_frame = (self.phase_delegate.spin_frame + 1) % stepper.SPIN_FRAMES
        viewport = self.phase_list.viewport()
        if viewport is not None:
            viewport.update()

    def _show_percent(self) -> None:
        top = max(self.progress.maximum(), 1)
        self.percent_label.setText(f"{round(100 * self.progress.value() / top)} %")

    def _show_details(self, shown: bool) -> None:
        self.log_card.setVisible(shown)
        self.log_view.setVisible(shown)
        self.log_note.setVisible(shown and self.log_view.dropped)
        self.details_button.setText(self.tr("Hide details") if shown else self.tr("Show details"))
        themed = self.details_button._themed_icon  # type: ignore[attr-defined]
        themed.name = "chevron-down" if shown else "chevron-right"
        themed.apply()

    # ------------------------------------------------------------------ the clock

    @staticmethod
    def format_seconds(seconds: float) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds // 60}:{seconds % 60:02d}"

    @staticmethod
    def round_seconds(seconds: float) -> int:
        """An estimate is said in steps of five seconds, and never as less than five."""
        return max(5, round(seconds / 5) * 5)

    def estimates_for(self, phase: str) -> tuple[float | None, float | None]:
        """``(the phase, the phase and every phase after it)`` in seconds, from this computer's
        history; None without one (a first run shows no estimate)."""
        if phase not in PHASES:
            return None, None
        rest = PHASES[PHASES.index(phase) :]
        return (
            app_settings.estimate(self._history, phase, self._assets),
            app_settings.estimate_rest(self._history, rest, self._assets),
        )

    def phase_note(self, in_phase: float) -> str:
        """Beside the running phase: "about 40 s left", or that it is taking longer than usual
        once the estimate is used up. The number is set when the phase starts and does not
        count down."""
        if self._phase_estimate is None:
            return ""
        if in_phase > self._phase_estimate:
            return self.tr("taking longer than usual")
        return self.tr("about {0} s left").format(self.round_seconds(self._phase_estimate))

    def total_note(self, in_phase: float) -> str:
        """At the top: what is left of the whole run, as of the start of the running phase."""
        if self._rest_estimate is None or self._phase_estimate is None:
            return ""
        if in_phase > self._phase_estimate:
            return self.tr("taking longer than usual")
        return self.tr("about {0} s left").format(self.round_seconds(self._rest_estimate))

    def _tick(self) -> None:
        if not self.running:
            return
        now = time.monotonic()
        text = self.tr("Elapsed {0}").format(self.format_seconds(now - self._run_started))
        note = self.total_note(now - self._phase_started)
        if note:
            text += "  ·  " + note
        self.elapsed_label.setText(text)
        self._show_running_row()

    def _show_running_row(self) -> None:
        """The running phase's row again: its note changes once the estimate is used up."""
        if self.current_phase in PHASES:
            position = PHASES.index(self.current_phase)
            icons = {p: ICON_DONE for p in PHASES[:position]}
            icons[self.current_phase] = ICON_RUNNING
            self._set_icons(icons)

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

    def ask_stop_and_close(self) -> bool:  # overridden by tests
        answer = QMessageBox.question(
            self,
            self.tr("Generation is running"),
            self.tr("Generation is running. Stop it and close?"),
        )
        return answer == QMessageBox.StandardButton.Yes

    def request_close(self, timeout_ms: int = 15000) -> bool:
        """True when the window may close: nothing runs, or the user chose to stop it (the run
        is cancelled and awaited so that no Godot process is left behind)."""
        if not self.running or self.worker is None:
            return True
        if self._promotion_dialog is not None:  # closing the window answers the question: no
            self._promotion_dialog.reject()
            self.worker.answer(False)
            self.cancel()
        elif not self.ask_stop_and_close():
            return False
        worker = self.worker
        self.cancel()
        loop = QEventLoop()
        worker.signals.finished.connect(loop.quit)
        worker.signals.failed.connect(loop.quit)
        QTimer.singleShot(timeout_ms, loop.quit)
        if self.running:
            loop.exec()
        return True

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
        self.log_note.setVisible(False)
        self.step_label.clear()
        self._history = {  # once per run, not every second
            phase: [list(pair) for pair in pairs]
            for phase, pairs in app_settings.get().phase_history.items()
        }
        self._assets = len(state.catalog.assets) if state.catalog is not None else 0
        self._phase_estimate = self._rest_estimate = None
        self._durations = {}
        self._skipped = {}
        self._run_started = self._phase_started = time.monotonic()
        self.elapsed_label.setText(self.tr("Elapsed {0}").format("0:00"))
        self._clock.start()
        self._set_icons({})
        self.progress.setValue(0)
        if state.config is None or state.target is None or state.godot_exe is None:
            self._on_failed(
                IssueList().add("GUI-001", reason="the project, output folder or Godot is not set")
            )
            return
        self.current_phase = ""
        self.running = True
        self.allow_back = self.back_allowed_while_running()  # a sample run: Back stays open
        self.allow_next = False
        self.sample_banner.setVisible(state.sample_run)
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
            state.accept_runtime_upgrade,
        )
        worker.signals.progress.connect(self._on_progress)
        worker.signals.log.connect(self.log_view.append_line)  # a batch may hold many lines
        worker.signals.step.connect(self._on_step)
        worker.signals.skipped.connect(self._on_skipped)
        worker.confirm_promotions = app_settings.get().confirm_regeneration
        worker.signals.confirmation.connect(self._on_confirmation)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self.worker = worker
        self.changed.emit()
        worker.start()

    def ask_promotion(self, summary) -> bool:  # noqa: ANN001 - overridden by tests
        """Show what the regeneration will change; True to go on."""
        dialog = PromotionDialog(summary, self)
        self._promotion_dialog = dialog
        try:
            return bool(dialog.exec())
        finally:
            self._promotion_dialog = None

    def _on_confirmation(self, summary) -> None:  # noqa: ANN001
        worker = self.worker
        if worker is None:
            return
        self.status_label.setText(self.tr("Waiting for you to look at the changes…"))
        answer = self.ask_promotion(summary)
        worker.answer(answer)
        if not answer:
            self.cancel()
        else:
            self.status_label.setText(self.tr("Generating…"))

    _promotion_dialog: PromotionDialog | None = None

    # ------------------------------------------------------------------ a sample run (T15.22)

    def back_allowed_while_running(self) -> bool:
        """Back is open during a sample run until the run starts to write the project (the
        ``promote`` phase): before that a cancel leaves nothing behind."""
        if not self.running or self.state is None or not self.state.sample_run:
            return False
        return self.current_phase not in WRITING_PHASES and not self.cancelled

    def _sync_sample(self) -> None:
        sample = bool(self.state is not None and self.state.sample_run)
        self.sample_banner.setVisible(sample and self.running)
        if self.running:
            allowed = self.back_allowed_while_running()
            if allowed != self.allow_back:
                self.allow_back = allowed
                self.changed.emit()

    def stop_for_back(self, timeout_ms: int = 15000) -> bool:
        """Back was pressed while a sample run is on: stop the run (nothing was written) and
        say True, or False when the run can no longer be left."""
        if not self.back_allowed_while_running() or self.worker is None:
            return False
        worker = self.worker
        self.cancel()
        loop = QEventLoop()
        worker.signals.finished.connect(loop.quit)
        worker.signals.failed.connect(loop.quit)
        QTimer.singleShot(timeout_ms, loop.quit)
        if self.running:
            loop.exec()
        return not self.running

    def cancel(self) -> None:
        if self.worker is not None and self.running:
            self.cancelled = True
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText(
                self.tr("Stopping Godot…")
                if self.current_phase in GODOT_PHASES
                else self.tr("Cancelling…")
            )

    @property
    def run_percent(self) -> int | None:
        """How far the run is, for the window's title; None while nothing runs."""
        if not self.running or self.progress.maximum() <= 0:
            return None
        return round(100 * self.progress.value() / self.progress.maximum())

    def _retitle(self) -> None:
        update = getattr(self.window(), "_update_title", None)
        if callable(update):
            update()

    def _on_progress(self, name: str, index: int, total: int) -> None:
        if name not in PHASES:
            return
        now = time.monotonic()
        if self.current_phase and self.current_phase != name:
            self._durations[self.current_phase] = now - self._phase_started
        if self.current_phase != name:
            self._phase_started = now
        if self.current_phase != name:
            self.step_label.clear()
            self._phase_estimate, self._rest_estimate = self.estimates_for(name)
        self.current_phase = name
        icons = {p: ICON_DONE for p in PHASES[: index - 1]}
        icons[name] = ICON_RUNNING
        self._set_icons(icons)
        self.progress.setMaximum(total)
        self.progress.setValue(index - 1)
        taskbar.set_progress(self.window(), index - 1, total)  # the taskbar button, the dock
        self._retitle()
        self._sync_sample()  # Back closes when the run starts to write
        self.status_label.setText(
            self.tr("Phase {0} of {1}: {2}").format(
                index, total, self.tr(PHASE_LABELS.get(name, name))
            )
        )

    STEP_VERBS = {
        "build": "Building {label} ({i} of {n})",
        "validate": "Checking {label} ({i} of {n})",
    }

    def step_text(self, phase: str, i: int, n: int, label: str) -> str:
        """The sub-line under the running phase."""
        if n > 0 and phase in self.STEP_VERBS:
            return self.tr(self.STEP_VERBS[phase]).format(label=label, i=i, n=n)
        return label  # no protocol (the import): the last line Godot printed

    def _on_step(self, phase: str, i: int, n: int, label: str) -> None:
        if phase != self.current_phase:
            return  # a late line of the phase before
        text = self.step_text(phase, i, n, label)
        width = max(self.step_label.width(), 200)
        self.step_label.setText(
            self.step_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, width)
        )
        self.step_label.setToolTip(text)

    def _on_skipped(self, phase: str, code: str) -> None:
        """A check did not run (no export templates, a test turned off): say so in its row."""
        if phase in PHASES:
            self._skipped[phase] = code
            self._set_icons(self._current_icons())

    def _current_icons(self) -> dict[str, str]:
        """The icons the list shows now, read back from the rows (a skipped row counts as done)."""
        icons = {}
        for i, name in enumerate(PHASES):
            item = self.phase_list.item(i)
            first = item.text().split()[0] if item is not None and item.text() else ""
            if first in (ICON_DONE, ICON_RUNNING, ICON_FAILED, ICON_SKIPPED):
                icons[name] = ICON_DONE if first == ICON_SKIPPED else first
        return icons

    def _stop_running(self) -> None:
        self._clock.stop()
        self.step_label.clear()
        self.running = False
        self.cancel_button.setEnabled(False)
        self.worker = None

    def _on_finished(self, result: orchestrator.RunResult) -> None:
        if self.state is not None:
            self.state.accept_runtime_upgrade = False  # one run only
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

    def notify(self, title: str, text: str) -> None:
        """A system notification when the run ends while this window is not the active one."""
        if QApplication.activeWindow() is not None:
            return
        self.show_notification(title, text)

    def show_notification(self, title: str, text: str) -> None:  # overridden by tests
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.show()
        tray.showMessage(title, text)
        QTimer.singleShot(6000, tray.hide)

    def _show_cancelled(self) -> None:
        self.status_label.setText(self.tr("Generation was cancelled; nothing was delivered."))
        self.status_label.setProperty("state", "warning")
        self.allow_back = True
        self.allow_next = False
        self.changed.emit()

    def _remember_project(self, result: orchestrator.RunResult) -> None:
        """A finished generation goes into the recent projects (and remembers the folders)."""
        state = self.state
        if state is None or state.config is None or state.target is None:
            return
        target, name, archetype = state.target, state.config.project_name, state.config.archetype
        godot_exe = state.godot_exe
        # the packs as they are now: the welcome view compares them with this later (T13.08)
        packs = [
            {"path": str(source), "stamp": pack_sniff.stamp(source) or ""}
            for source in state.pack_sources
        ]

        def remember(settings: app_settings.AppSettings) -> None:
            app_settings.add_recent(settings, target, name, archetype, packs)
            settings.last_target_dir = str(Path(target).parent)
            if godot_exe is not None:
                settings.godot_exe = str(godot_exe)

        app_settings.store().update(remember)

    def _show_finished(self, result: orchestrator.RunResult) -> None:
        self.sample_banner.setVisible(False)
        taskbar.clear(self.window(), failed=not result.ok and not result.cancelled)
        if result.timings:
            self._durations.update(result.timings)
        self._skipped.update(result.skipped)
        if result.ok:
            self._remember_project(result)
            if result.timings:
                assets = len(result.catalog.assets) if result.catalog is not None else 0
                app_settings.update(phase_timings=dict(result.timings), timing_assets=assets)
            self._set_icons({p: ICON_DONE for p in PHASES})
            self.elapsed_label.setText(
                self.tr("Finished in {0}").format(self.format_seconds(sum(result.timings.values())))
            )
            self.notify(self.tr("rpggen"), self.tr("Your project was generated."))
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
            self.details_button.setChecked(True)  # a failure opens the log by itself
            self.notify(self.tr("rpggen"), self.tr("Generation failed."))
            self.status_label.setText(self.tr("Generation failed."))
            self.status_label.setProperty("state", "error")
            self.allow_back = True
        self.allow_next = True
        self.changed.emit()
