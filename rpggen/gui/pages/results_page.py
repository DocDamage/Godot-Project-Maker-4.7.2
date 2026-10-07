"""Page 7: what the run produced, or why it failed. There is no way to deliver a failed run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import orchestrator, promote, report
from rpggen.errors import Issue, RpgGenError, Severity
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState

COUNT_LABELS = (
    ("assets", "Assets processed"),
    ("tilesets", "TileSets"),
    ("scenes", "Scenes"),
    ("animation_sets", "Animation sets"),
    ("warnings", "Warnings"),
    ("errors", "Errors"),
)
RESTORE_TOOLTIP = "Put the project back the way it was before the last regeneration"
NO_BACKUP_TOOLTIP = "There is no earlier version to restore"


class TextViewer(QDialog):
    """A read-only viewer for the report (Markdown) or the logs (plain text)."""

    def __init__(self, title: str, text: str, markdown: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("textViewer")
        self.setWindowTitle(title)
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        if markdown:
            self.browser.setMarkdown(text)
        else:
            self.browser.setPlainText(text)
        layout.addWidget(self.browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def launch_detached(args: list[str]) -> None:
    """Start a program that outlives the wizard."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(  # noqa: S603 - the executable is the user's chosen Godot
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )


class ResultsPage(WizardPage):
    title = "Results"
    allow_next = False

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.result: orchestrator.RunResult | None = None
        self.shown_issues: list[Issue] = []
        layout = QVBoxLayout(self)
        self.header = QLabel()
        self.header.setObjectName("resultsHeader")
        layout.addWidget(self.header)
        self.phase_label = QLabel()
        self.phase_label.setObjectName("failedPhase")
        layout.addWidget(self.phase_label)
        counts_box = QWidget()
        self.counts_box = counts_box
        grid = QGridLayout(counts_box)
        self.count_labels: dict[str, QLabel] = {}
        for row, (key, text) in enumerate(COUNT_LABELS):
            grid.addWidget(QLabel(self.tr(text)), row, 0)
            value = QLabel("0")
            value.setObjectName(f"count_{key}")
            self.count_labels[key] = value
            grid.addWidget(value, row, 1)
        layout.addWidget(counts_box)
        self.issue_title = QLabel()
        layout.addWidget(self.issue_title)
        self.issue_list = QListWidget()
        self.issue_list.setObjectName("issueList")
        layout.addWidget(self.issue_list, 1)
        self.fix_label = QLabel()
        self.fix_label.setObjectName("fixText")
        self.fix_label.setWordWrap(True)
        layout.addWidget(self.fix_label)
        self.issue_list.currentRowChanged.connect(self._on_issue_selected)

        buttons = QHBoxLayout()
        self.godot_button = self._button("Open in Godot", "openGodot", buttons)
        self.folder_button = self._button("Open folder", "openFolder", buttons)
        self.report_button = self._button("View report", "viewReport", buttons)
        self.restore_button = self._button("Restore previous", "restorePrevious", buttons)
        self.failed_button = self._button("Open failed folder", "openFailed", buttons)
        self.logs_button = self._button("View logs", "viewLogs", buttons)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.restore_button.setEnabled(False)
        self.restore_button.setToolTip(self.tr(NO_BACKUP_TOOLTIP))
        self.restore_button.clicked.connect(self.restore_previous)
        self.godot_button.clicked.connect(self.open_in_godot)
        self.folder_button.clicked.connect(lambda: self.open_path(self._target()))
        self.report_button.clicked.connect(self.view_report)
        self.failed_button.clicked.connect(self.open_failed_folder)
        self.logs_button.clicked.connect(self.view_logs)

    def _button(self, text: str, name: str, row: QHBoxLayout) -> QPushButton:
        button = QPushButton(self.tr(text))
        button.setObjectName(name)
        row.addWidget(button)
        return button

    # ------------------------------------------------------------------ hooks for tests

    def launch(self, args: list[str]) -> None:
        launch_detached(args)

    def open_path(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def run_viewer(self, viewer: TextViewer) -> None:
        viewer.exec()

    def confirm_restore(self) -> bool:
        answer = QMessageBox.question(
            self,
            self.tr("Restore previous version"),
            self.tr(
                "Put the files of the last regeneration back the way they were? Your own files "
                "are not touched. What is replaced is saved first, so this can be undone."
            ),
        )
        return answer == QMessageBox.StandardButton.Yes

    def show_message(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)

    # ------------------------------------------------------------------ showing

    def _target(self) -> Path:
        assert self.result is not None
        return self.result.target

    def enter(self, state: WizardState) -> None:
        self.state = state
        result = state.run_result
        self.result = result
        if result is None:
            self.header.setText(self.tr("Nothing has been generated yet."))
            return
        counts = report.counts(result.catalog, result.issues, result.target if result.ok else None)
        for key, label in self.count_labels.items():
            label.setText(str(counts[key]))
        if result.ok:
            self._show_success(result)
        else:
            self._show_failure(result)

    def _set_state(self, label: QLabel, state: str) -> None:
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)

    def _fill_issues(self, issues: list[Issue]) -> None:
        self.shown_issues = issues
        self.issue_list.clear()
        self.fix_label.clear()
        for issue in issues:
            mark = "✖" if issue.severity is Severity.ERROR else "⚠"
            self.issue_list.addItem(QListWidgetItem(f"{mark} {issue.code}: {issue.message}"))

    def _show_success(self, result: orchestrator.RunResult) -> None:
        self.header.setText(self.tr("Your project was generated."))
        self._set_state(self.header, "ok")
        self.phase_label.clear()
        self.counts_box.setVisible(True)
        self.issue_title.setText(self.tr("Warnings (select one to see how to fix it)"))
        self._fill_issues([i for i in result.issues if i.severity is Severity.WARNING])
        for button in (self.godot_button, self.folder_button, self.report_button):
            button.setVisible(True)
        self.restore_button.setVisible(True)
        has_backup = bool(promote.list_backups(result.target))
        self.restore_button.setEnabled(has_backup)
        self.restore_button.setToolTip(
            self.tr(RESTORE_TOOLTIP if has_backup else NO_BACKUP_TOOLTIP)
        )
        self.failed_button.setVisible(False)
        self.logs_button.setVisible(False)

    def _show_failure(self, result: orchestrator.RunResult) -> None:
        self.header.setText(self.tr("Generation failed. Nothing was delivered."))
        self._set_state(self.header, "error")
        self.phase_label.setText(
            self.tr("Failed in phase: {0}").format(result.failed_phase or self.tr("unknown"))
        )
        self.counts_box.setVisible(False)
        self.issue_title.setText(self.tr("Problems (select one to see how to fix it)"))
        ordered = sorted(
            (i for i in result.issues if i.severity is not Severity.INFO),
            key=lambda i: i.severity is not Severity.ERROR,
        )
        self._fill_issues(ordered)
        for button in (self.godot_button, self.folder_button, self.report_button):
            button.setVisible(False)
        self.restore_button.setVisible(False)
        has_folder = result.failed_staging is not None
        self.failed_button.setVisible(True)
        self.failed_button.setEnabled(has_folder)
        self.logs_button.setVisible(True)
        self.logs_button.setEnabled(has_folder)

    def _on_issue_selected(self, row: int) -> None:
        if 0 <= row < len(self.shown_issues):
            self.fix_label.setText(self.shown_issues[row].fix or self.tr("No fix is needed."))
        else:
            self.fix_label.clear()

    # ------------------------------------------------------------------ actions

    def open_in_godot(self) -> None:
        assert self.state is not None and self.result is not None
        exe = self.state.godot_exe
        if exe is None:
            return
        self.launch([str(exe), "--path", str(self.result.target), "--editor"])

    def restore_previous(self) -> bool:
        """Restore the newest backup after asking; True when the project was restored."""
        assert self.result is not None
        if not self.confirm_restore():
            return False
        try:
            promote.restore(self.result.target)
        except RpgGenError as exc:
            self.show_message(self.tr("Restore failed"), exc.issue.message)
            return False
        self.show_message(
            self.tr("Restored"), self.tr("The previous version of the project was restored.")
        )
        self.restore_button.setEnabled(bool(promote.list_backups(self.result.target)))
        return True

    def view_report(self) -> None:
        assert self.result is not None
        path = self.result.target / report.REPORT_MD
        text = path.read_text(encoding="utf-8") if path.exists() else self.tr("No report found.")
        self.run_viewer(TextViewer(self.tr("Generation report"), text, True, self))

    def open_failed_folder(self) -> None:
        if self.result is not None and self.result.failed_staging is not None:
            self.open_path(self.result.failed_staging)

    def view_logs(self) -> None:
        if self.result is None or self.result.failed_staging is None:
            return
        log_dir = self.result.failed_staging / "rpggen" / "logs"
        parts = [
            f"=== {p.name} ===\n{p.read_text(encoding='utf-8', errors='replace')}"
            for p in sorted(log_dir.glob("*.log"))
        ]
        text = "\n\n".join(parts) or self.tr("No logs were written.")
        self.run_viewer(TextViewer(self.tr("Logs"), text, False, self))
