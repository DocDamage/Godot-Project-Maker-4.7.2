"""Page 7: what the run produced, or why it failed. There is no way to deliver a failed run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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

from rpggen import procenv
from rpggen.core import conflicts, godot, orchestrator, promote, report
from rpggen.errors import Issue, RpgGenError, Severity
from rpggen.gui import fixes
from rpggen.gui.dialogs import diagnostic_export, error_lookup
from rpggen.gui.dialogs.conflict_dialog import ConflictDialog
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets.collapsible import CollapsibleSection

COUNT_LABELS = (
    ("assets", "Assets processed"),
    ("tilesets", "TileSets"),
    ("scenes", "Scenes"),
    ("animation_sets", "Animation sets"),
    ("warnings", "Warnings"),
    ("errors", "Errors"),
)
STARTER_MAP = "res://game/maps/starter_map.tscn"
ASSET_KEYS = ("asset", "file", "path", "source")  # detail keys that can name an asset
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
        env=procenv.child_env(),
        **kwargs,
    )


PHASE_FAILED_TEXT = {
    "preflight": "Something is wrong with your setup, so nothing was built.",
    "stage": "rpggen could not prepare a work folder next to your output folder.",
    "install": "rpggen could not copy your packs and the game code.",
    "catalog": "rpggen could not read what is in your packs.",
    "import": "Godot could not import your assets.",
    "build": "Godot could not build the game.",
    "validate": "The finished game did not pass its checks.",
    "smoke": "The game started, but the test that plays it failed.",
    "export": "The test export of the game failed.",
    "promote": "The finished project could not be put in place.",
    "report": "The report could not be written.",
}


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001, N802
        self.clicked.emit()
        super().mousePressEvent(event)


class ResultsPage(WizardPage):
    title = "Results"
    help_anchor = "4. In Godot"
    allow_next = False
    generateAnother = Signal()  # noqa: N815
    changeOptions = Signal()  # noqa: N815
    goToProject = Signal()  # noqa: N815
    generateAgain = Signal()  # noqa: N815 - a one-click fix: run the generation again
    showHelp = Signal(str)  # noqa: N815 - a help anchor
    showAssets = Signal(list)  # noqa: N815 - asset ids: switch to Audit, filtered to them

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state: WizardState | None = None
        self.result: orchestrator.RunResult | None = None
        self.shown_issues: list[Issue] = []
        self.shown_groups: list[list[Issue]] = []
        layout = QVBoxLayout(self)
        self.header = QLabel()
        self.header.setObjectName("resultsHeader")
        layout.addWidget(self.header)
        self.run_label = QLabel()
        self.run_label.setObjectName("runLabel")
        self.run_label.setProperty("muted", True)
        self.run_label.setToolTip(
            self.tr("The number of this run: the lines of the log and the report that belong to it")
        )
        layout.addWidget(self.run_label)
        self.phase_label = QLabel()
        self.phase_label.setObjectName("failedPhase")
        self.phase_label.setWordWrap(True)
        layout.addWidget(self.phase_label)
        # the numbers, as one compact strip
        counts_box = QWidget()
        self.counts_box = counts_box
        strip = QHBoxLayout(counts_box)
        strip.setContentsMargins(0, 0, 0, 0)
        self.count_labels: dict[str, QLabel] = {}
        for key, text in COUNT_LABELS:
            caption = QLabel(self.tr(text))
            caption.setProperty("muted", True)
            value = QLabel("0")
            value.setObjectName(f"count_{key}")
            value.setStyleSheet("font-weight: bold;")
            self.count_labels[key] = value
            strip.addWidget(value)
            strip.addWidget(caption)
            strip.addSpacing(14)
        strip.addStretch(1)
        layout.addWidget(counts_box)
        # the picture of the starter map, and what to do next
        self.success_box = QWidget()
        success = QHBoxLayout(self.success_box)
        success.setContentsMargins(0, 0, 0, 0)
        self.map_picture = ClickableLabel()
        self.map_picture.setObjectName("mapPicture")
        self.map_picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map_picture.setMinimumSize(320, 200)
        self.map_picture.setToolTip(
            self.tr("The starter map as it was built. Click to open it full size.")
        )
        self.map_picture.clicked.connect(self.open_picture)
        success.addWidget(self.map_picture, 3)
        right = QVBoxLayout()
        self.godot_button = QPushButton(self.tr("Open in Godot"))
        self.godot_button.setObjectName("openGodot")
        self.godot_button.setProperty("primary", True)
        self.godot_button.setMinimumHeight(40)
        self.godot_button.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.godot_button.setToolTip(self.tr("Open the new project in the Godot editor"))
        right.addWidget(self.godot_button)
        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.setObjectName("playGame")
        self.play_button.setToolTip(self.tr("Run the game, without opening the editor"))
        self.starter_button = QPushButton(self.tr("Open starter map"))
        self.starter_button.setObjectName("openStarterMap")
        self.starter_button.setToolTip(self.tr("Open the editor with the starter map shown"))
        play_row = QHBoxLayout()
        play_row.addWidget(self.play_button)
        play_row.addWidget(self.starter_button)
        right.addLayout(play_row)
        self.what_next_label = QLabel()
        self.what_next_label.setObjectName("whatNext")
        self.what_next_label.setWordWrap(True)
        self.what_next_label.setTextFormat(Qt.TextFormat.RichText)
        self.what_next_label.setOpenExternalLinks(False)
        self.what_next_label.linkActivated.connect(self._on_next_link)
        right.addWidget(self.what_next_label)
        right.addStretch(1)
        success.addLayout(right, 2)
        layout.addWidget(self.success_box)
        self.issue_title = QLabel()
        layout.addWidget(self.issue_title)
        self.issue_list = QListWidget()
        self.issue_list.setObjectName("issueList")
        self.issue_list.setToolTip(self.tr("Select a line to read how to fix it"))
        layout.addWidget(self.issue_list, 1)
        # a group of many issues of one code: its members, and what can be done with them
        self.group_detail = QListWidget()
        self.group_detail.setObjectName("groupDetail")
        self.group_detail.setToolTip(self.tr("Every issue of the selected code"))
        self.group_detail.setAccessibleName(self.tr("Issues of this code"))
        self.group_detail.setMaximumHeight(110)
        self.group_detail.setVisible(False)
        layout.addWidget(self.group_detail)
        group_row = QHBoxLayout()
        self.show_assets_button = QPushButton(self.tr("Show these assets"))
        self.show_assets_button.setObjectName("showAssets")
        self.show_assets_button.setToolTip(self.tr("Open the Audit page on the assets named here"))
        self.show_assets_button.setVisible(False)
        self.show_assets_button.clicked.connect(self.show_selected_assets)
        group_row.addWidget(self.show_assets_button)
        group_row.addStretch(1)
        layout.addLayout(group_row)
        self.fix_box = QWidget()  # the one-click fixes of the selected issue
        self.fix_box.setObjectName("fixButtons")
        self.fix_row = QHBoxLayout(self.fix_box)
        self.fix_row.setContentsMargins(0, 0, 0, 0)
        self.fix_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.fix_box.setVisible(False)
        self.fix_buttons: list[QPushButton] = []
        layout.addWidget(self.fix_box)
        self.fix_label = QLabel()
        self.fix_label.setObjectName("fixText")
        self.fix_label.setWordWrap(True)
        layout.addWidget(self.fix_label)
        self.issue_list.currentRowChanged.connect(self._on_issue_selected)
        self.issue_list.itemDoubleClicked.connect(self._on_issue_double_clicked)
        # notes (the INFO issues; the checks that did not run come first)
        self.notes = CollapsibleSection(self.tr("Notes"))
        self.notes.setObjectName("notesSection")
        notes_layout = QVBoxLayout(self.notes.body)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_list = QListWidget()
        self.notes_list.setObjectName("notesList")
        self.notes_list.setToolTip(self.tr("Things that were left out or only worth knowing"))
        self.notes_list.setMaximumHeight(130)
        notes_layout.addWidget(self.notes_list)
        self.notes_list.currentRowChanged.connect(self._on_note_selected)
        layout.addWidget(self.notes)

        buttons = QHBoxLayout()
        self.folder_button = self._button("Open folder", "openFolder", buttons)
        self.report_button = self._button("View report", "viewReport", buttons)
        self.restore_button = self._button("Restore previous", "restorePrevious", buttons)
        self.conflicts_button = self._button("Resolve conflicts…", "resolveConflicts", buttons)
        self.conflicts_button.setVisible(False)
        self.conflicts_button.setToolTip(
            self.tr("Choose between your changes and the new versions rpggen made (.rpggen-new)")
        )
        self.failed_button = self._button("Open failed folder", "openFailed", buttons)
        self.logs_button = self._button("View logs", "viewLogs", buttons)
        self.bundle_button = self._button("Export diagnostic bundle", "exportBundle", buttons)
        self.project_button = self._button("Back to the Project page", "backToProject", buttons)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        # what to do next, on a row of its own: one row does not fit the smallest window with the
        # wider fonts of Linux
        next_row = QHBoxLayout()
        next_row.addStretch(1)
        self.another_button = self._button("Generate another", "generateAnotherButton", next_row)
        self.options_button = self._button(
            "Change options and regenerate", "changeOptionsButton", next_row
        )
        layout.addLayout(next_row)
        self.another_button.setToolTip(self.tr("Start again from the welcome screen"))
        self.options_button.setToolTip(self.tr("Go back to the options of this project"))
        self.project_button.setToolTip(self.tr("Fix the Godot or folder choice on the first page"))
        self.another_button.clicked.connect(self.generateAnother)
        self.options_button.clicked.connect(self.changeOptions)
        self.project_button.clicked.connect(self.goToProject)
        self.restore_button.setEnabled(False)
        self.restore_button.setToolTip(self.tr(NO_BACKUP_TOOLTIP))
        self.restore_button.clicked.connect(self.restore_previous)
        self.conflicts_button.clicked.connect(lambda: self.resolve_conflicts())
        self.godot_button.clicked.connect(self.open_in_godot)
        self.play_button.clicked.connect(self.play)
        self.starter_button.clicked.connect(self.open_starter_map)
        self.folder_button.clicked.connect(lambda: self.open_path(self._target()))
        self.report_button.clicked.connect(self.view_report)
        self.failed_button.clicked.connect(self.open_failed_folder)
        self.logs_button.clicked.connect(self.view_logs)
        self.bundle_button.clicked.connect(self.export_bundle)

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

    def run_conflict_dialog(self, dialog: ConflictDialog) -> None:
        dialog.exec()

    def resolve_conflicts(self, select: str | None = None) -> None:
        """The resolver of T12.58 for this project, showing ``select`` first."""
        if self.result is None:
            return
        self.run_conflict_dialog(ConflictDialog(self.result.target, select, self))
        self._update_conflicts_button()

    def _update_conflicts_button(self) -> None:
        target = self.result.target if self.result is not None else None
        count = len(conflicts.list_conflicts(target)) if target and target.is_dir() else 0
        self.conflicts_button.setVisible(bool(count))
        self.conflicts_button.setText(self.tr("Resolve conflicts ({0})…").format(count))

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
            self.run_label.clear()
            return
        self.run_label.setText(self.tr("Run {0}").format(result.run_id) if result.run_id else "")
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

    def _fill_notes(self, result: orchestrator.RunResult) -> None:
        """The INFO issues in a folded section; a check that did not run is listed first."""
        skipped_codes = set(result.skipped.values())
        notes = [i for i in result.issues if i.severity is Severity.INFO]
        notes.sort(key=lambda i: i.code not in skipped_codes)  # stable: the rest keeps its order
        self.notes_list.clear()
        for issue in notes:
            mark = "–" if issue.code in skipped_codes else "ℹ"
            text = f"{mark} {issue.code}: {issue.message}"
            if issue.fix and issue.fix != "—":
                text += f"\n      {self.tr('Fix')}: {issue.fix}"
            self.notes_list.addItem(QListWidgetItem(text))
        self.notes.set_title(self.tr("Notes ({0})").format(len(notes)))
        self.notes.setVisible(bool(notes))

    def _fill_issues(self, issues: list[Issue]) -> None:
        """Errors first, then warnings, grouped by code: "ASSET-001 x 37" with the shared fix
        shown once; a group of several opens its members when selected."""
        groups: dict[str, list[Issue]] = {}
        for issue in issues:
            groups.setdefault(issue.code, []).append(issue)
        self.shown_groups = list(groups.values())
        self.shown_issues = [group[0] for group in self.shown_groups]  # one per row
        self.issue_list.clear()
        self.group_detail.clear()
        self.group_detail.setVisible(False)
        self.show_assets_button.setVisible(False)
        self.fix_label.clear()
        for group in self.shown_groups:
            issue = group[0]
            mark = "✖" if issue.severity is Severity.ERROR else "⚠"
            if len(group) > 1:
                text = f"{mark} {issue.code} × {len(group)}: {issue.message}"
            else:
                text = f"{mark} {issue.code}: {issue.message}"
            if issue.fix:
                text += f"\n      {self.tr('Fix')}: {issue.fix}"
            self.issue_list.addItem(QListWidgetItem(text))

    def issue_group_counts(self) -> dict[str, int]:
        """The rows as shown: code -> how many issues it stands for."""
        return {group[0].code: len(group) for group in self.shown_groups}

    def assets_named_by(self, issues: list[Issue]) -> list[str]:
        """Ids of the catalog's assets that these issues name (by id, or by file path)."""
        if self.state is None or self.state.catalog is None:
            return []
        catalog = self.state.catalog
        wanted: set[str] = set()
        for issue in issues:
            for text in (issue.file, *(issue.detail.get(k) for k in ASSET_KEYS)):
                if isinstance(text, str) and text:
                    wanted.add(text.replace("\\", "/"))
        found = []
        for asset in catalog.assets:
            if asset.id in wanted or any(
                asset.path == w or asset.path.endswith("/" + w) for w in wanted
            ):
                found.append(asset.id)
        return found

    def show_selected_assets(self) -> None:
        """ "Show these assets": the Audit page, filtered to what the selected group names."""
        row = self.issue_list.currentRow()
        if not 0 <= row < len(self.shown_groups):
            return
        ids = self.assets_named_by(self.shown_groups[row])
        if ids:
            self.showAssets.emit(ids)

    def lookup_code(self, code: str) -> None:
        """Double-click on a row: the error-code list, at this code."""
        dialog = error_lookup.ErrorLookupDialog(self, code)
        self.run_viewer(dialog)  # type: ignore[arg-type]

    def _on_issue_double_clicked(self, item: QListWidgetItem) -> None:
        row = self.issue_list.row(item)
        if 0 <= row < len(self.shown_issues):
            self.lookup_code(self.shown_issues[row].code)

    # ------------------------------------------------------------------ the picture, what next

    def picture_path(self) -> Path | None:
        if self.result is None:
            return None
        path = self.result.target / "rpggen" / "results" / "starter_map.png"
        return path if path.is_file() else None

    def _show_picture(self) -> None:
        path = self.picture_path()
        pixmap = QPixmap(str(path)) if path is not None else QPixmap()
        if pixmap.isNull():
            self.map_picture.clear()
            self.map_picture.setText(self.tr("No picture of the starter map was made."))
            return
        self.map_picture.setPixmap(
            pixmap.scaled(
                560,
                340,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

    def open_picture(self) -> None:
        path = self.picture_path()
        if path is not None:
            self.open_path(path)

    NEXT_ITEMS = (
        ("Press <b>F5</b> in Godot to play.", ""),
        ("Paint on <code>game/maps/starter_map.tscn</code>.", "game/maps/starter_map.tscn"),
        ("Drag objects from the <b>RPG Project Tools</b> dock into the map.", ""),
        ("Edit items in <code>game/data/items/</code>.", "game/data/items"),
        ("Read <code>README.md</code> in the project.", "README.md"),
    )

    def _fill_next_steps(self) -> None:
        rows = []
        for text, rel in self.NEXT_ITEMS:
            link = f' <a href="show:{rel}">{self.tr("Show")}</a>' if rel else ""
            rows.append(f"<li>{self.tr(text)}{link}</li>")
        self.what_next_label.setText(f"<b>{self.tr('What next')}</b><ul>{''.join(rows)}</ul>")

    def _on_next_link(self, link: str) -> None:
        if self.result is not None and link.startswith("show:"):
            self.open_path(self.result.target / link.removeprefix("show:"))

    def _show_success(self, result: orchestrator.RunResult) -> None:
        self.header.setText(self.tr("Your project was generated."))
        self._set_state(self.header, "ok")
        self.phase_label.clear()
        self.counts_box.setVisible(True)
        self.success_box.setVisible(True)
        self._show_picture()
        self._fill_next_steps()
        warnings = [i for i in result.issues if i.severity is Severity.WARNING]
        self.issue_title.setText(
            self.tr("Warnings ({0}): what to do about each is shown under it").format(len(warnings))
            if warnings
            else self.tr("No warnings.")
        )
        self.issue_title.setVisible(True)
        self._fill_issues(warnings)
        self.issue_list.setVisible(bool(warnings))
        self.fix_label.setVisible(False)
        self._fill_notes(result)
        for button in (self.godot_button, self.folder_button, self.report_button):
            button.setVisible(True)
        self.project_button.setVisible(False)
        self.another_button.setVisible(True)
        self.options_button.setVisible(True)
        self.restore_button.setVisible(True)
        has_backup = bool(promote.list_backups(result.target))
        self.restore_button.setEnabled(has_backup)
        self.restore_button.setToolTip(
            self.tr(RESTORE_TOOLTIP if has_backup else NO_BACKUP_TOOLTIP)
        )
        self.failed_button.setVisible(False)
        self.logs_button.setVisible(False)
        self._update_conflicts_button()

    def _show_failure(self, result: orchestrator.RunResult) -> None:
        self.header.setText(self.tr("Generation failed. Nothing was delivered."))
        self._set_state(self.header, "error")
        sentence = PHASE_FAILED_TEXT.get(result.failed_phase or "", "Something went wrong.")
        self.phase_label.setText(
            f"{self.tr(sentence)}  "
            f"({self.tr('phase')}: {result.failed_phase or self.tr('unknown')})"
        )
        self.counts_box.setVisible(False)
        self.success_box.setVisible(False)
        self.issue_title.setVisible(True)
        self.issue_list.setVisible(True)
        self.fix_label.setVisible(True)
        self.another_button.setVisible(False)
        self.options_button.setVisible(False)
        self.project_button.setVisible(any(i.code.startswith("ENV-") for i in result.issues))
        self.notes.setVisible(False)
        self.issue_title.setText(self.tr("Problems (select one to see how to fix it)"))
        ordered = sorted(
            (i for i in result.issues if i.severity is not Severity.INFO),
            key=lambda i: i.severity is not Severity.ERROR,
        )
        self._fill_issues(ordered)
        for button in (self.godot_button, self.folder_button, self.report_button):
            button.setVisible(False)
        self.restore_button.setVisible(False)
        self.conflicts_button.setVisible(False)
        has_folder = result.failed_staging is not None
        self.failed_button.setVisible(True)
        self.failed_button.setEnabled(has_folder)
        self.logs_button.setVisible(True)
        self.logs_button.setEnabled(has_folder)

    # ------------------------------------------------------------------ one-click fixes

    def show_fixes(self, issue: Issue | None) -> None:
        """The buttons of ``issue``'s code (none for a code that is not registered)."""
        for button in self.fix_buttons:
            self.fix_row.removeWidget(button)
            button.deleteLater()
        self.fix_buttons = []
        self.shown_fix_issue = issue
        if issue is not None:
            for fix in fixes.fixes_for(issue.code):
                button = QPushButton(self.tr(fix.label))
                button.setObjectName(f"fix_{fix.action}")
                button.clicked.connect(lambda _=False, f=fix, i=issue: self.apply_fix(f, i))
                self.fix_row.addWidget(button)
                self.fix_buttons.append(button)
        self.fix_box.setVisible(bool(self.fix_buttons))

    def apply_fix(self, fix: fixes.Fix, issue: Issue) -> bool:
        assert self.state is not None
        return fixes.apply(fix, issue, self.state, self._navigation())

    def _navigation(self) -> fixes.Navigation:
        page = self

        class Nav:
            def go_to_project(self) -> None:
                page.goToProject.emit()

            def generate_again(self) -> None:
                page.generateAgain.emit()

            def show_help(self, anchor: str) -> None:
                page.showHelp.emit(anchor)

            def open_folder(self) -> None:
                if page.result is not None:
                    page.open_path(page.result.target)

            def resolve_conflicts(self, file: str | None) -> None:
                page.resolve_conflicts(file)

        return Nav()

    shown_fix_issue: Issue | None = None

    def _on_note_selected(self, row: int) -> None:
        notes = [
            i for i in (self.result.issues if self.result else []) if i.severity is Severity.INFO
        ]
        skipped = set(self.result.skipped.values()) if self.result else set()
        notes.sort(key=lambda i: i.code not in skipped)
        self.show_fixes(notes[row] if 0 <= row < len(notes) else None)

    def _on_issue_selected(self, row: int) -> None:
        self.show_fixes(self.shown_issues[row] if 0 <= row < len(self.shown_issues) else None)
        self.group_detail.clear()
        self.group_detail.setVisible(False)
        self.show_assets_button.setVisible(False)
        if 0 <= row < len(self.shown_issues):
            self.fix_label.setText(self.shown_issues[row].fix or self.tr("No fix is needed."))
            group = self.shown_groups[row]
            if len(group) > 1:
                for issue in group:
                    self.group_detail.addItem(issue.message)
                self.group_detail.setVisible(True)
            self.show_assets_button.setVisible(bool(self.assets_named_by(group)))
        else:
            self.fix_label.clear()

    # ------------------------------------------------------------------ actions

    def open_in_godot(self) -> None:
        assert self.state is not None and self.result is not None
        exe = self.state.godot_exe
        if exe is None:
            return
        self.launch([str(godot.find_gui_exe(exe)), "--path", str(self.result.target), "--editor"])

    def play(self) -> None:
        """Run the generated game (no editor)."""
        assert self.state is not None and self.result is not None
        exe = self.state.godot_exe
        if exe is not None:
            self.launch([str(godot.find_gui_exe(exe)), "--path", str(self.result.target)])

    def open_starter_map(self) -> None:
        """The editor with the starter map open; just the editor when the scene is not there."""
        assert self.state is not None and self.result is not None
        exe = self.state.godot_exe
        if exe is None:
            return
        args = [str(godot.find_gui_exe(exe)), "--editor", "--path", str(self.result.target)]
        if (self.result.target / STARTER_MAP.removeprefix("res://")).is_file():
            args.append(STARTER_MAP)
        self.launch(args)

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
        self._update_conflicts_button()
        return True

    def view_report(self) -> None:
        assert self.result is not None
        path = self.result.target / report.REPORT_MD
        text = path.read_text(encoding="utf-8") if path.exists() else self.tr("No report found.")
        self.run_viewer(TextViewer(self.tr("Generation report"), text, True, self))

    def open_failed_folder(self) -> None:
        if self.result is not None and self.result.failed_staging is not None:
            self.open_path(self.result.failed_staging)

    def export_bundle(self) -> Path | None:
        """Save a diagnostic bundle of the failed run (or of the project after a success)."""
        if self.result is None:
            return None
        folder = self.result.failed_staging or self.result.target
        exe = self.state.godot_exe if self.state is not None else None
        return diagnostic_export.export_bundle(self, folder, exe)

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
