"""Page 1: packs, output folder, Godot executable and project name."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import paths
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import godot, preflight, profiles
from rpggen.errors import Issue, RpgGenError, Severity
from rpggen.gui import state as state_mod
from rpggen.gui import workers
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import analysis_progress

log = logging.getLogger(__name__)

DEBOUNCE_MS = 300
SAMPLE_NAME = "Sample RPG"
SAMPLE_PROFILE = "sample.rpgprofile.json"
NAME_MAX = 64
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar")


@dataclass
class InputCheck:
    """Result of the slow checks (one Godot launch, disk statistics, zip directories)."""

    godot: list[Issue] = field(default_factory=list)
    godot_version: str = ""
    target: list[Issue] = field(default_factory=list)
    packs: list[Issue] = field(default_factory=list)


def check_inputs(
    godot_exe: Path | None,
    target: Path | None,
    packs: list[Path],
    *,
    callbacks: object = None,
) -> InputCheck:
    """Everything the page checks that touches the disk or starts a process."""
    out = InputCheck()
    if godot_exe is not None:
        try:
            version = godot.detect_version(godot_exe)
            out.godot_version = ".".join(str(p) for p in version[:3]) + f".{version[3]}"
            out.godot.extend(godot.check_version(version))
        except Exception as exc:  # noqa: BLE001 - shown as a field message
            out.godot.append(getattr(exc, "issue", None) or form_error(str(exc)))
    if target is not None:
        out.target = preflight.check_target(target, packs)
    for pack in packs:
        out.packs.extend(preflight.check_pack(pack))
    return out


class PackList(QListWidget):
    """The pack list; files and folders can be dropped onto it."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("packList")
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.on_paths_dropped = lambda paths: None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        dropped = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if dropped:
            self.on_paths_dropped(dropped)
            event.acceptProposedAction()


def _status_label(name: str) -> QLabel:
    label = QLabel()
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def set_status(label: QLabel, issues: list[Issue], ok_text: str = "") -> None:
    """Show the worst issue of ``issues`` (red, amber) or ``ok_text`` (green)."""
    worst = None
    for issue in issues:
        if issue.severity is Severity.ERROR:
            worst = issue
            break
        if issue.severity is Severity.WARNING and worst is None:
            worst = issue
    if worst is not None:
        state = "error" if worst.severity is Severity.ERROR else "warning"
        text = worst.message + (f" {worst.fix}" if worst.fix else "")
    else:
        state = "ok" if ok_text else ""
        text = ok_text
    label.setText(text)
    label.setProperty("state", state)
    label.style().unpolish(label)
    label.style().polish(label)


class ProjectPage(WizardPage):
    title = "Project"
    sampleReady = Signal()  # "Try with sample pack" filled in valid inputs

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._check: InputCheck | None = None  # latest completed slow check
        self._check_key: tuple | None = None
        self._generation = 0  # ignores results of superseded checks
        self._worker: workers.Worker | None = None
        self._name_touched = False
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # packs
        self.pack_list = PackList()
        self.pack_list.on_paths_dropped = self.add_sources
        self.add_zip_button = QPushButton(self.tr("Add Zip/7z…"))
        self.add_zip_button.setObjectName("addZipButton")
        self.add_folder_button = QPushButton(self.tr("Add Folder…"))
        self.add_folder_button.setObjectName("addFolderButton")
        self.remove_button = QPushButton(self.tr("Remove"))
        self.remove_button.setObjectName("removePackButton")
        buttons = QHBoxLayout()
        for b in (self.add_zip_button, self.add_folder_button, self.remove_button):
            buttons.addWidget(b)
        buttons.addStretch(1)
        pack_box = QVBoxLayout()
        pack_box.addWidget(self.pack_list)
        pack_box.addLayout(buttons)
        self.packs_status = _status_label("packsStatus")
        pack_box.addWidget(self.packs_status)
        form.addRow(self.tr("Asset packs"), pack_box)

        # output folder
        self.target_edit = QLineEdit()
        self.target_edit.setObjectName("targetEdit")
        self.browse_target_button = QPushButton(self.tr("Browse…"))
        self.browse_target_button.setObjectName("browseTargetButton")
        row = QHBoxLayout()
        row.addWidget(self.target_edit, 1)
        row.addWidget(self.browse_target_button)
        box = QVBoxLayout()
        box.addLayout(row)
        self.target_status = _status_label("targetStatus")
        box.addWidget(self.target_status)
        form.addRow(self.tr("Output folder"), box)

        # godot
        self.godot_combo = QComboBox()
        self.godot_combo.setObjectName("godotCombo")
        self.godot_combo.setEditable(True)
        self.browse_godot_button = QPushButton(self.tr("Browse…"))
        self.browse_godot_button.setObjectName("browseGodotButton")
        row = QHBoxLayout()
        row.addWidget(self.godot_combo, 1)
        row.addWidget(self.browse_godot_button)
        box = QVBoxLayout()
        box.addLayout(row)
        self.godot_status = _status_label("godotStatus")
        box.addWidget(self.godot_status)
        form.addRow(self.tr("Godot 4.7.2"), box)

        # name
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setMaxLength(NAME_MAX * 2)  # longer text is reported, not silently cut
        box = QVBoxLayout()
        box.addWidget(self.name_edit)
        self.name_status = _status_label("nameStatus")
        box.addWidget(self.name_status)
        form.addRow(self.tr("Project name"), box)

        layout.addStretch(1)
        self.sample_row = QHBoxLayout()
        self.sample_button = QPushButton(self.tr("Try with sample pack"))
        self.sample_button.setObjectName("trySampleButton")
        self.sample_button.setToolTip(
            self.tr("Fill in the bundled sample pack and go straight to the options.")
        )
        self.sample_row.addWidget(self.sample_button)
        self.sample_row.addStretch(1)
        layout.addLayout(self.sample_row)
        self.sample_button.clicked.connect(self.try_sample)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._start_check)

        self.add_zip_button.clicked.connect(self._browse_archives)
        self.add_folder_button.clicked.connect(self._browse_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.browse_target_button.clicked.connect(self._browse_target)
        self.browse_godot_button.clicked.connect(self._browse_godot)
        self.target_edit.textChanged.connect(self._on_target_changed)
        self.godot_combo.currentTextChanged.connect(self._on_inputs_changed)
        self.name_edit.textEdited.connect(self._on_name_edited)
        self.name_edit.textChanged.connect(self._refresh_name_status)

    # ------------------------------------------------------------------ sample pack

    def documents_dir(self) -> Path:  # overridden by tests
        found = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return Path(found) if found else Path.home() / "Documents"

    def sample_target(self) -> Path:
        base = self.documents_dir()
        n = 1
        while (base / f"rpggen-sample-{n}").exists():
            n += 1
        return base / f"rpggen-sample-{n}"

    def try_sample(self) -> bool:
        """Fill the page with the bundled sample pack; emits ``sampleReady`` when every input
        is valid so the window can continue to the Options page."""
        sample = paths.sample_pack_root()
        if not sample.is_dir():
            QMessageBox.warning(
                self,
                self.tr("Sample pack"),
                self.tr("The sample pack was not found: {0}").format(sample),
            )
            return False
        profile = sample / SAMPLE_PROFILE
        if profile.is_file():
            try:
                profiles.install_profile(profile)  # the audit of the sample is all CONFIRMED
            except (RpgGenError, OSError, ValueError):
                log.warning("could not install the sample profile", exc_info=True)
        self._loading = True
        try:
            self.pack_list.clear()
            self.pack_list.addItem(str(sample))
            self.target_edit.setText(str(self.sample_target()))
            self.name_edit.setText(SAMPLE_NAME)
            self._name_touched = True
        finally:
            self._loading = False
        self._debounce.stop()
        key = self._key()
        self._generation += 1
        self._check = check_inputs(self.godot_path(), self.target(), self.sources())
        self._check_key = key
        self._refresh_cheap()
        self.changed.emit()
        ok = not [i for i in self.validate(WizardState()) if i.severity is Severity.ERROR]
        if ok:
            self.sampleReady.emit()
        return ok

    # ------------------------------------------------------------------ editing

    def sources(self) -> list[Path]:
        return [Path(self.pack_list.item(i).text()) for i in range(self.pack_list.count())]

    def add_sources(self, paths_: list[Path]) -> None:
        known = {str(p).casefold() for p in self.sources()}
        for path in paths_:
            path = Path(path)
            if path.is_file() and path.suffix.lower() not in ARCHIVE_SUFFIXES:
                continue
            if str(path).casefold() not in known:
                self.pack_list.addItem(str(path))
                known.add(str(path).casefold())
        self._on_inputs_changed()

    def remove_selected(self) -> None:
        for item in self.pack_list.selectedItems():
            self.pack_list.takeItem(self.pack_list.row(item))
        self._on_inputs_changed()

    def target(self) -> Path | None:
        text = self.target_edit.text().strip()
        return Path(text) if text else None

    def godot_path(self) -> Path | None:
        text = self.godot_combo.currentText().strip()
        return Path(text) if text else None

    def _browse_archives(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Add asset packs"), "", self.tr("Archives (*.zip *.7z *.rar)")
        )
        self.add_sources([Path(f) for f in files])

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.tr("Add asset pack folder"))
        if folder:
            self.add_sources([Path(folder)])

    def _browse_target(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.tr("Output folder"))
        if folder:
            self.target_edit.setText(folder)

    def _browse_godot(self) -> None:
        exe, _ = QFileDialog.getOpenFileName(
            self, self.tr("Godot 4.7.2 executable"), "", self.tr("Executables (*.exe);;All (*)")
        )
        if exe:
            self.godot_combo.setCurrentText(exe)

    def _on_target_changed(self) -> None:
        if not self._name_touched and not self._loading:
            target = self.target()
            self.name_edit.setText(target.name if target else "")
        self._on_inputs_changed()

    def _on_name_edited(self) -> None:
        self._name_touched = True
        self.changed.emit()

    def _on_inputs_changed(self) -> None:
        if self._loading:
            return
        self._debounce.start()
        self._refresh_cheap()
        self.changed.emit()

    # ------------------------------------------------------------------ live validation

    def _key(self) -> tuple:
        return (
            str(self.godot_path() or ""),
            str(self.target() or ""),
            tuple(str(p) for p in self.sources()),
        )

    def _start_check(self) -> None:
        key = self._key()
        self._generation += 1
        generation = self._generation
        worker = workers.Worker(check_inputs, self.godot_path(), self.target(), self.sources())

        def done(result: InputCheck) -> None:
            if generation != self._generation:
                return
            self._check, self._check_key = result, key
            self._refresh_cheap()
            self.changed.emit()

        def failed(exc: object) -> None:
            log.warning("input check failed: %s", exc)

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._worker = worker  # keep it alive until its signals are delivered
        worker.start()

    def _current_check(self) -> InputCheck | None:
        return self._check if self._check_key == self._key() else None

    def _name_issues(self) -> list[Issue]:
        name = self.name_edit.text().strip()
        if not 1 <= len(name) <= NAME_MAX:
            return [form_error(self.tr("The name needs 1 to 64 characters."))]
        return []

    def _refresh_name_status(self) -> None:
        set_status(self.name_status, self._name_issues(), self.tr("Name is fine."))

    def _refresh_cheap(self) -> None:
        """Update the field lines from the latest completed slow check."""
        check = self._current_check()
        pack_issues: list[Issue] = (
            [] if self.sources() else [form_error(self.tr("Add at least one asset pack."))]
        )
        if check:
            pack_issues += check.packs
        set_status(
            self.packs_status,
            pack_issues,
            self.tr("{0} pack(s) ready.").format(len(self.sources())),
        )
        if self.godot_path() is None:
            set_status(
                self.godot_status, [form_error(self.tr("Select the Godot 4.7.2 executable."))]
            )
        elif check:
            set_status(
                self.godot_status,
                check.godot,
                self.tr("Godot {0}").format(check.godot_version),
            )
        else:
            self._set_pending(self.godot_status)
        if self.target() is None:
            set_status(self.target_status, [form_error(self.tr("Choose an output folder."))])
        elif check:
            set_status(self.target_status, check.target, self.tr("Output folder is fine."))
        else:
            self._set_pending(self.target_status)
        self._refresh_name_status()

    def _set_pending(self, label: QLabel) -> None:
        label.setText(self.tr("Checking…"))
        label.setProperty("state", "")
        label.style().unpolish(label)
        label.style().polish(label)

    def validate(self, state: WizardState) -> list[Issue]:
        issues: list[Issue] = []
        if not self.sources():
            issues.append(form_error(self.tr("Add at least one asset pack.")))
        if self.target() is None:
            issues.append(form_error(self.tr("Choose an output folder.")))
        if self.godot_path() is None:
            issues.append(form_error(self.tr("Select the Godot 4.7.2 executable.")))
        issues += self._name_issues()
        check = self._current_check()
        if check is None:
            if not issues:
                issues.append(form_error(self.tr("Checking your choices…")))
            return issues
        for found in (*check.godot, *check.target, *check.packs):
            if found.severity is Severity.ERROR:
                issues.append(found)
        return issues

    # ------------------------------------------------------------------ state <-> widgets

    def enter(self, state: WizardState) -> None:
        self._loading = True
        try:
            self.pack_list.clear()
            for source in state.pack_sources:
                self.pack_list.addItem(str(source))
            self.target_edit.setText(str(state.target) if state.target else "")
            self._name_touched = bool(state.project_name)
            self.name_edit.setText(state.project_name)
            self.godot_combo.clear()
            candidates = [str(p) for p in godot.auto_find_godot()]
            if state.godot_exe and str(state.godot_exe) not in candidates:
                candidates.insert(0, str(state.godot_exe))
            self.godot_combo.addItems(candidates)
            if state.godot_exe:
                self.godot_combo.setCurrentText(str(state.godot_exe))
            elif not candidates:
                self.godot_combo.setCurrentText("")
        finally:
            self._loading = False
        self._start_check()
        self._refresh_cheap()

    def ask_resume(self) -> bool:
        """Ask whether to continue the saved session of this output folder."""
        answer = QMessageBox.question(
            self,
            self.tr("Resume previous session?"),
            self.tr("There is saved work for this output folder. Resume it?"),
        )
        return answer == QMessageBox.StandardButton.Yes

    def leave(self, state: WizardState) -> bool | None:
        sources = self.sources()
        target = self.target()
        state.pack_sources = sources
        state.target = target
        state.godot_exe = self.godot_path()
        state.project_name = self.name_edit.text().strip()
        if target is None or not sources:
            return None
        previous = self._load_previous(state, target)
        key = tuple(str(p) for p in sources)
        if state.catalog is not None and state.analyzed_key == key and previous is None:
            return True
        if previous is not None:
            state.catalog = previous
        if not self._run_analysis(state):
            return False
        state.analyzed_key = key
        if state.config is None or [p.source for p in state.config.packs] != [
            str(s) for s in sources
        ]:
            state.config = self._default_config(state)
        return True

    def _default_config(self, state: WizardState) -> config_mod.GeneratorConfig:
        refs = []
        used: set[str] = set()
        for opened, source in zip(state.opened_packs, state.pack_sources, strict=True):
            ref = config_mod.pack_ref_from_source(source, opened.pack_id)
            refs.append(ref)
            used.add(opened.pack_id)
        return config_mod.default_for(state.project_name, refs, archetype=state.archetype)

    def _load_previous(self, state: WizardState, target: Path) -> catalog_mod.Catalog | None:
        """The catalog to build on: an existing project's, or a saved draft (when resumed)."""
        if preflight.is_rpggen_project(target):
            state.regenerating = True
            state.config = config_mod.load(target / paths.CONFIG)
            state.archetype = state.config.archetype
            return catalog_mod.load(target / paths.CATALOG)
        state.regenerating = False
        draft = state_mod.load_draft(target)
        if draft is not None and self.ask_resume():
            return state_mod.apply_draft(state, draft)
        return None

    def _run_analysis(self, state: WizardState) -> bool:
        """Analyze in a worker behind a modal progress dialog; False when cancelled or failed."""
        return analysis_progress.run_analysis(self, state)
