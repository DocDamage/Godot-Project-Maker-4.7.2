"""Page 7: what the run produced, or why it failed. There is no way to deliver a failed run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QT_TRANSLATE_NOOP, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rpggen import procenv
from rpggen.core import (
    conflicts,
    godot,
    godot_log,
    orchestrator,
    promote,
    report,
    world_repair,
)
from rpggen.errors import Issue, RpgGenError, Severity
from rpggen.gui import fixes, icons, theme
from rpggen.gui.dialogs import diagnostic_export, error_lookup
from rpggen.gui.dialogs.conflict_dialog import ConflictDialog
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import buttons as button_kinds
from rpggen.gui.widgets.card import DANGER, INFO, SUCCESS, Banner, Card
from rpggen.gui.widgets.collapsible import CollapsibleSection
from rpggen.gui.widgets.log_view import LogView

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
    purpose = str(
        QT_TRANSLATE_NOOP("WizardPage", "What was made, what to look at, and what to do next.")
    )
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
        outer = self.page_layout()
        # the body scrolls in a small window (as Mapping and Options do); the buttons under it
        # stay in view
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("resultsScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("resultsBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, theme.px("space_8"), 0)
        layout.setSpacing(theme.px("space_12"))
        self.scroll_area.setWidget(body)
        outer.addWidget(self.scroll_area, 1)
        # how the run went (T15.17): a banner with the run id at its right and, after a
        # failure, the phase in its second line. ``header`` and ``phase_label`` are its labels.
        self.banner = Banner(INFO)
        self.banner.setObjectName("resultsBanner")
        self.header = self.banner.text_label
        self.header.setObjectName("resultsHeader")
        self.header.setProperty("role", "section")
        self.phase_label = self.banner.detail_label
        self.phase_label.setObjectName("failedPhase")
        self.phase_label.setProperty("role", None)
        self.run_label = QLabel()
        self.run_label.setObjectName("runLabel")
        self.run_label.setProperty("role", "caption")
        self.run_label.setToolTip(
            self.tr("The number of this run: the lines of the log and the report that belong to it")
        )
        self.banner.add_action(self.run_label)
        layout.addWidget(self.banner)
        # after a failure, right under the banner: where the run's files and logs are
        self.failure_row = QWidget()
        self.failure_row.setObjectName("failureActions")
        self.failure_layout = QHBoxLayout(self.failure_row)
        self.failure_layout.setContentsMargins(0, 0, 0, 0)
        self.failure_row.setVisible(False)
        layout.addWidget(self.failure_row)
        # the picture of the starter map, and what to do next
        self.success_box = QWidget()
        success = QHBoxLayout(self.success_box)
        success.setContentsMargins(0, 0, 0, 0)
        success.setSpacing(theme.px("space_16"))
        self.picture_card = Card(margin=theme.px("space_8"))
        self.picture_card.setObjectName("pictureCard")
        self.map_picture = ClickableLabel()
        self.map_picture.setObjectName("mapPicture")
        self.map_picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.map_picture.setMinimumSize(300, 180)
        self.map_picture.setToolTip(
            self.tr("The starter map as it was built. Click to open it full size.")
        )
        self.map_picture.clicked.connect(self.open_picture)
        self.picture_card.box.addWidget(self.map_picture)
        success.addWidget(self.picture_card, 3)
        right = QVBoxLayout()
        right.setSpacing(theme.px("space_8"))
        self.godot_button = QPushButton(self.tr("Open in Godot"))
        self.godot_button.setObjectName("openGodot")
        button_kinds.set_kind(self.godot_button, button_kinds.PRIMARY)
        self.godot_button.setProperty("tall", True)
        self.godot_button.setToolTip(self.tr("Open the new project in the Godot editor"))
        icons.set_icon(self.godot_button, "external-link", "on_accent")
        right.addWidget(self.godot_button)
        self.play_button = QPushButton(self.tr("Play"))
        self.play_button.setObjectName("playGame")
        self.play_button.setToolTip(self.tr("Run the game, without opening the editor"))
        icons.set_icon(self.play_button, "play")
        self.starter_button = QPushButton(self.tr("Open starter map"))
        self.starter_button.setObjectName("openStarterMap")
        self.starter_button.setToolTip(self.tr("Open the editor with the starter map shown"))
        icons.set_icon(self.starter_button, "map")
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
        # the numbers, as a row of small tiles: the number, and under it what it counts
        counts_box = QWidget()
        self.counts_box = counts_box
        strip = QHBoxLayout(counts_box)
        strip.setContentsMargins(0, 0, 0, 0)
        strip.setSpacing(theme.px("space_8"))
        self.count_labels: dict[str, QLabel] = {}
        self.count_tiles: dict[str, Card] = {}
        for key, text in COUNT_LABELS:
            tile = Card(margin=theme.px("space_8"))
            tile.setObjectName(f"tile_{key}")
            tile.box.setSpacing(0)
            value = QLabel("0")
            value.setObjectName(f"count_{key}")
            value.setProperty("stat", True)
            caption = QLabel(self.tr(text))
            caption.setProperty("role", "caption")
            tile.box.addWidget(value)
            tile.box.addWidget(caption)
            self.count_labels[key] = value
            self.count_tiles[key] = tile
            strip.addWidget(tile, 1)
        layout.addWidget(counts_box)
        self.issue_title = QLabel()
        layout.addWidget(self.issue_title)
        self.issue_list = QListWidget()
        self.issue_list.setObjectName("issueList")
        self.issue_list.setToolTip(self.tr("Select a line to read how to fix it"))
        self.issue_list.setMinimumHeight(96)
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
        # the last lines of the failed phase's log (T15.17): what Godot said, without a click
        self.log_card = Card(margin=theme.px("space_8"))
        self.log_card.setObjectName("logTailCard")
        self.log_more_button = QPushButton(self.tr("Show more"))
        self.log_more_button.setObjectName("logShowMore")
        self.log_more_button.setToolTip(self.tr("Open the whole log file"))
        button_kinds.set_kind(self.log_more_button, button_kinds.QUIET)
        self.log_more_button.clicked.connect(self.show_whole_log)
        self.log_title = self.log_card.add_heading(
            self.tr("Last lines of the log"), self.log_more_button
        )
        self.log_tail = LogView(max_lines=godot_log.TAIL_LINES * 2)
        self.log_tail.setObjectName("logTail")
        self.log_tail.setMinimumHeight(90)
        self.log_tail.setMaximumHeight(170)
        self.log_card.box.addWidget(self.log_tail)
        self.log_card.setVisible(False)
        self.shown_log: Path | None = None
        layout.addWidget(self.log_card)
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
        self.failed_button = self._button("Open failed folder", "openFailed", self.failure_layout)
        self.logs_button = self._button("View logs", "viewLogs", self.failure_layout)
        self.bundle_button = self._button("Export diagnostic bundle", "exportBundle", buttons)
        self._bottom_buttons = buttons
        self.failure_layout.addStretch(1)
        for button, icon_name in (
            (self.folder_button, "folder-open"),
            (self.report_button, "book-open"),
            (self.restore_button, "undo"),
            (self.failed_button, "folder-open"),
            (self.logs_button, "list"),
            (self.bundle_button, "download"),
        ):
            icons.set_icon(button, icon_name)
        self.project_button = self._button("Back to the Project page", "backToProject", buttons)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        # what to do next, on a row of its own: one row does not fit the smallest window with the
        # wider fonts of Linux
        next_row = QHBoxLayout()
        next_row.addStretch(1)
        self.another_button = self._button("Generate another", "generateAnotherButton", next_row)
        self.options_button = self._button(
            "Change options and regenerate", "changeOptionsButton", next_row
        )
        outer.addLayout(next_row)
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

    # ------------------------------------------------------------------ world repair (T13.24)

    def run_world_repair(self, dry_run: bool) -> world_repair.RepairResult:  # tests replace it
        """Run the project's repair tool in Godot (a few seconds; the cursor shows it)."""
        assert self.result is not None and self.state is not None
        exe = self.state.godot_exe
        if exe is None:
            raise RpgGenError("ENV-001")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return world_repair.run(self.result.target, exe, dry_run=dry_run)
        finally:
            QApplication.restoreOverrideCursor()

    def confirm_world_repair(self, preview: world_repair.RepairResult) -> bool:
        lines = "\n".join(f"• {line['map']}: {line['what']}" for line in preview.repairs)
        answer = QMessageBox.question(
            self,
            self.tr("Repair the world"),
            self.tr(
                "This will be done to your maps (they are saved to the backups first, so "
                "Restore previous undoes it):\n\n{0}"
            ).format(lines),
        )
        return answer == QMessageBox.StandardButton.Yes

    def repair_world(self) -> bool:
        """The one-click fix of VAL-027 and VAL-028: show what the repair would do, and do it
        after a yes. Every map may be written here, edited ones too: the user asked."""
        if self.result is None:
            return False
        try:
            preview = self.run_world_repair(True)
            if not preview.repairs:
                why = "\n".join(f"• {line['what']}" for line in preview.unfixable)
                self.show_message(
                    self.tr("Repair the world"),
                    self.tr("Nothing can be mended automatically.")
                    + (("\n\n" + why) if why else ""),
                )
                return False
            if not self.confirm_world_repair(preview):
                return False
            done = self.run_world_repair(False)
        except RpgGenError as exc:
            self.show_message(self.tr("Repair failed"), exc.issue.message)
            return False
        text = self.tr("{0} repair(s) made. Open the maps in Godot to see them.").format(
            len(done.repairs)
        )
        if done.unfixable:
            text += "\n\n" + self.tr("Not mended:") + "\n"
            text += "\n".join(f"• {line['what']}" for line in done.unfixable)
        self.show_message(self.tr("World repaired"), text)
        self.restore_button.setEnabled(bool(promote.list_backups(self.result.target)))
        self.last_world_repair = done
        return True

    last_world_repair: world_repair.RepairResult | None = None

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
            self.banner.set_kind(INFO)
            self.header.setText(self.tr("Nothing has been generated yet."))
            self.phase_label.setVisible(False)
            self.run_label.clear()
            self.failure_row.setVisible(False)
            self.log_card.setVisible(False)
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
            cause = issue.detail.get("cause")
            if isinstance(cause, str) and cause:  # T15.21: what Godot said, under the message
                text += f"\n      {self.tr('Godot said')}: {cause}"
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

    def asset_of_file(self, file: object) -> str | None:
        """The catalog asset a file named by Godot belongs to (T15.21): the pack's own file
        (``res://assets/packs/...``), or a generated file with the name of exactly one asset
        or object (``res://generated/objects/house.tscn`` → the object *house*)."""
        if not isinstance(file, str) or not file:
            return None
        if self.state is None or self.state.catalog is None:
            return None
        catalog = self.state.catalog
        path = file.replace("\\", "/").removeprefix("res://")
        for asset in catalog.assets:
            if path == asset.path or path.endswith("/" + asset.path) or asset.path.endswith(path):
                return asset.id
        stem = Path(path).stem.lower()
        for obj in catalog.objects:  # an object scene is named after the object
            if stem in (obj.id.lower(), obj.name.lower()):
                return obj.sheet or None
        named = [a.id for a in catalog.assets if Path(a.path).stem.lower() == stem]
        return named[0] if len(named) == 1 else None

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
            self.map_picture.setText(
                self.tr("No picture of the world was made.")
                if self.has_rooms()
                else self.tr("No picture of the starter map was made.")
            )
            return
        # 300 high: in the default window the counts under the picture show without scrolling
        self.map_picture.setPixmap(
            pixmap.scaled(
                560,
                300,
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
    # a metroidvania has rooms instead of a starter map (T14.10)
    NEXT_ITEMS_ROOMS = (
        ("Press <b>F5</b> in Godot to play.", ""),
        ("Paint on the rooms in <code>game/maps/rooms/</code>.", "game/maps/rooms"),
        ("Drag objects from the <b>RPG Project Tools</b> dock into a room.", ""),
        ("Edit enemies in <code>game/data/enemies/</code>.", "game/data/enemies"),
        ("Read <code>README.md</code> in the project.", "README.md"),
    )

    def has_rooms(self) -> bool:
        """True for the result of a metroidvania: a world of rooms."""
        cfg = self.result.cfg if self.result is not None else None
        return cfg is not None and cfg.archetype == "metroidvania"

    def first_map(self) -> str:
        """The scene the *Open starter map* button shows: the starter map, or the first room
        of a metroidvania ("" when the project has neither)."""
        if self.result is None:
            return ""
        root = self.result.target
        if (root / STARTER_MAP.removeprefix("res://")).is_file():
            return STARTER_MAP
        from rpggen.core import world_plan

        try:
            plan = world_plan.load(root) or {}
        except Exception:  # noqa: BLE001 - a damaged plan only means: open the editor
            plan = {}
        rooms = plan.get("rooms") or {}
        start = next((r for r in rooms.get("list", []) if r["id"] == rooms.get("start")), None)
        if start is not None and (root / start["map"]).is_file():
            return "res://" + start["map"]
        return ""

    def _fill_next_steps(self) -> None:
        rooms = self.has_rooms()
        self.starter_button.setText(
            self.tr("Open first room") if rooms else self.tr("Open starter map")
        )
        self.starter_button.setToolTip(
            self.tr("Open the editor with the first room shown")
            if rooms
            else self.tr("Open the editor with the starter map shown")
        )
        rows = []
        for text, rel in self.NEXT_ITEMS_ROOMS if rooms else self.NEXT_ITEMS:
            link = f' <a href="show:{rel}">{self.tr("Show")}</a>' if rel else ""
            rows.append(f"<li>{self.tr(text)}{link}</li>")
        self.what_next_label.setText(f"<b>{self.tr('What next')}</b><ul>{''.join(rows)}</ul>")

    def _on_next_link(self, link: str) -> None:
        if self.result is not None and link.startswith("show:"):
            self.open_path(self.result.target / link.removeprefix("show:"))

    def _show_success(self, result: orchestrator.RunResult) -> None:
        self.banner.set_kind(SUCCESS)
        self.header.setText(self.tr("Your project was generated."))
        self._set_state(self.header, "ok")
        self.phase_label.clear()
        self.phase_label.setVisible(False)
        self.failure_row.setVisible(False)
        self.log_card.setVisible(False)
        self._place_bundle_button(failed=False)
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
        cancelled = bool(getattr(result, "cancelled", False))
        self.banner.set_kind(INFO if cancelled else DANGER)
        self.header.setText(
            self.tr("Generation was cancelled. Nothing was delivered.")
            if cancelled
            else self.tr("Generation failed. Nothing was delivered.")
        )
        self._set_state(self.header, "" if cancelled else "error")
        self.phase_label.setVisible(True)
        self.failure_row.setVisible(True)
        self._place_bundle_button(failed=True)
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
        self._show_log_tail(result)
        if self.issue_list.count():  # the first problem's fix and buttons show at once
            self.issue_list.setCurrentRow(0)

    def _place_bundle_button(self, failed: bool) -> None:
        """*Export diagnostic bundle* is in the action row under the banner after a failure
        and with the other buttons at the bottom after a success."""
        for layout in (self.failure_layout, self._bottom_buttons):
            layout.removeWidget(self.bundle_button)
        if failed:
            self.failure_layout.insertWidget(2, self.bundle_button)
        else:
            self._bottom_buttons.insertWidget(
                max(self._bottom_buttons.count() - 1, 0), self.bundle_button
            )

    # ------------------------------------------------------------------ the log tail (T15.17)

    def failed_log(self, result: orchestrator.RunResult) -> Path | None:
        """The log of the failed phase: the one an issue names (T15.21), else the newest."""
        if result.failed_staging is None:
            return None
        log_dir = result.failed_staging / "rpggen" / "logs"
        for issue in result.issues:
            name = issue.detail.get("log")
            if isinstance(name, str) and name and (log_dir / name).is_file():
                return log_dir / name
        logs = sorted(log_dir.glob("godot_*.log"), key=lambda p: p.stat().st_mtime)
        return logs[-1] if logs else None

    def _show_log_tail(self, result: orchestrator.RunResult) -> None:
        self.shown_log = self.failed_log(result)
        self.log_tail.clear()
        if self.shown_log is None:
            self.log_card.setVisible(False)
            return
        try:
            text = self.shown_log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            self.log_card.setVisible(False)
            return
        self.log_tail.append_line(godot_log.tail(text))
        self.log_title.setText(self.tr("Last lines of the log ({0})").format(self.shown_log.name))
        self.log_card.setVisible(True)

    def show_whole_log(self, name: str | None = None) -> None:
        """The whole file in the viewer (*Show more*, and the *Open the log* fix)."""
        path = self.shown_log
        if name and self.result is not None and self.result.failed_staging is not None:
            named = self.result.failed_staging / "rpggen" / "logs" / name
            path = named if named.is_file() else path
        if path is None:
            self.view_logs()
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = self.tr("No logs were written.")
        self.run_viewer(TextViewer(path.name, godot_log.strip_ansi(text), False, self))

    # ------------------------------------------------------------------ one-click fixes

    def show_fixes(self, issue: Issue | None) -> None:
        """The buttons of ``issue``'s code (none for a code that is not registered)."""
        for button in self.fix_buttons:
            self.fix_row.removeWidget(button)
            button.deleteLater()
        self.fix_buttons = []
        self.shown_fix_issue = issue
        if issue is not None:
            offered = fixes.fixes_for_issue(
                issue,
                names_asset=bool(self.asset_of_file(issue.detail.get("file"))),
                has_failed_folder=self.result is not None
                and self.result.failed_staging is not None,
            )
            for fix in offered:
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

            def repair_world(self) -> None:
                page.repair_world()

            def open_log(self, name: str) -> None:
                page.show_whole_log(name)

            def show_asset(self, file: str) -> bool:
                asset_id = page.asset_of_file(file)
                if asset_id:
                    page.showAssets.emit([asset_id])
                return bool(asset_id)

            def open_failed_folder(self) -> None:
                page.open_failed_folder()

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
        if scene := self.first_map():
            args.append(scene)
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
