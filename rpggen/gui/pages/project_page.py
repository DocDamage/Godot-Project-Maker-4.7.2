"""Page 1: packs, output folder, Godot executable and project name. The decisions are in
``rpggen.gui.models.project_model``; this module has the widgets and the wiring."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QT_TRANSLATE_NOOP, QPoint, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QInputDialog,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QWidget,
)

from rpggen import paths
from rpggen.core import app_settings, godot_fetch, pack_diff, pack_sniff, preflight, profiles
from rpggen.core import config as config_mod
from rpggen.errors import Issue, RpgGenError, Severity
from rpggen.gui import workers
from rpggen.gui.dialogs.bundle_dialog import BundleDialog
from rpggen.gui.models import project_model as model_mod
from rpggen.gui.models.project_model import (  # noqa: F401 - names the tests import from here
    ARCHIVE_SUFFIXES,
    NAME_MAX,
    SAMPLE_NAME,
    SAMPLE_PROFILE,
    InputCheck,
    Inputs,
    ProjectModel,
    check_inputs,
    format_size,
    prefill_name,
)
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import analysis_progress, godot_download
from rpggen.gui.widgets.pack_list import (  # noqa: F401
    CARD_ROLE,
    GROUP_ROLE,
    PackCardDelegate,
    PackList,
)
from rpggen.gui.widgets.project_form import ProjectForm, show_status

log = logging.getLogger(__name__)

DEBOUNCE_MS = 300


class ProjectPage(WizardPage):
    title = "Project"
    purpose = str(
        QT_TRANSLATE_NOOP(
            "WizardPage", "Your asset packs, where the project goes, and which Godot builds it."
        )
    )
    help_anchor = "3. Using a pack you bought"
    shows_inline_errors = True  # the fields print their own messages
    sampleReady = Signal()  # "Try with sample pack" filled in valid inputs

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = ProjectModel(self.tr)
        self._worker: workers.Worker | None = None
        self._loading = False

        layout = self.page_layout()
        self.form = form = ProjectForm()
        # the form scrolls when a long message wraps on a small window (as Mapping and Options do)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("projectScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(form)
        layout.addWidget(self.scroll_area)
        self.pack_list, self.packs_status = form.pack_list, form.packs_status
        self.add_zip_button, self.add_folder_button = form.add_zip_button, form.add_folder_button
        self.remove_button, self.update_pack_button = form.remove_button, form.update_pack_button
        self.target_edit, self.target_status = form.target_edit, form.target_status
        self.browse_target_button = form.browse_target_button
        self.godot_combo, self.godot_status = form.godot_combo, form.godot_status
        self.browse_godot_button = form.browse_godot_button
        self.download_godot_button = form.download_godot_button
        self.name_edit, self.name_status = form.name_edit, form.name_status
        self.sample_button, self.sample_row = form.sample_button, form.sample_row
        self.pack_list.on_paths_dropped = self.add_sources
        form.drop_zone.on_paths_dropped = self.add_sources
        self.pack_list.card_delegate.removeRequested.connect(self.remove_row)
        self.pack_list.card_delegate.chooseRequested.connect(self.choose_packs_at)
        self.pack_list.itemActivated.connect(self._on_item_activated)
        self.choose_packs_button = form.choose_packs_button
        self.choose_packs_button.clicked.connect(lambda: self.choose_packs_at())
        self.sample_button.clicked.connect(self._on_sample_button)
        self.sample_archetype = ""  # the kind of the sample that was chosen by name
        self.sample_key = ""  # ... and which one it was: its view goes with its kind (T17.17)
        self.sample_actions: dict[str, QAction] = {}
        self._add_sample_menu()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._start_check)

        self.add_zip_button.clicked.connect(self._browse_archives)
        self.add_folder_button.clicked.connect(self._browse_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.update_pack_button.clicked.connect(self.update_pack)
        self.browse_target_button.clicked.connect(self._browse_target)
        self.browse_godot_button.clicked.connect(self._browse_godot)
        self.download_godot_button.clicked.connect(self.download_godot)
        self.target_edit.textChanged.connect(self._on_target_changed)
        self.target_edit.textEdited.connect(lambda _t: self.model.target_typed())
        self.godot_combo.activated.connect(lambda _i: self._touch("godot"))
        if (godot_line := self.godot_combo.lineEdit()) is not None:
            godot_line.textEdited.connect(lambda _t: self._touch("godot"))
        self.godot_combo.currentTextChanged.connect(self._on_inputs_changed)
        self.name_edit.textEdited.connect(self._on_name_edited)
        self.name_edit.textChanged.connect(self._refresh_name_status)

    # ------------------------------------------------------------------ sample pack

    def _add_sample_menu(self) -> None:
        """The sample button lists the samples the welcome view offers (T16.17): with more
        than one on offer a click opens the list, and an entry fills the page with its pack
        and sets its kind of game. With one it stays the plain button."""
        offered = model_mod.offered_samples()
        if len(offered) < 2:
            return
        menu = QMenu(self.sample_button)
        menu.setObjectName("projectSampleMenu")
        menu.setToolTipsVisible(True)
        for entry in offered:
            action = menu.addAction(self.tr(entry.label))
            action.setObjectName(f"projectSample_{entry.key}")
            action.setToolTip(self.tr(entry.tooltip))
            action.triggered.connect(lambda _on=False, k=entry.key: self.try_sample(key=k))
            self.sample_actions[entry.key] = action
        self.sample_menu = menu
        self.sample_button.setToolTip(
            self.tr("Fill in a bundled sample pack and go straight to the options.")
        )

    def _on_sample_button(self) -> None:
        """The list of samples under the button, or the one sample there is."""
        if self.sample_menu is None:
            self.try_sample()
            return
        below = self.sample_button.mapToGlobal(QPoint(0, self.sample_button.height()))
        self.sample_menu.popup(below)  # not exec: the page goes on when an entry is chosen

    sample_menu: QMenu | None = None

    def documents_dir(self) -> Path:  # overridden by tests
        found = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return Path(found) if found else Path.home() / "Documents"

    def sample_target(self) -> Path:
        return model_mod.sample_target(self.documents_dir())

    def try_sample(self, side: bool = False, key: str = "") -> bool:
        """Fill the page with a bundled sample pack; emits ``sampleReady`` when every input
        is valid so the window can continue to the Options page. ``key`` names the sample
        (``project_model.SAMPLES``); without one it is the top-down village, or with ``side``
        the side-view pack (T14.09). A sample chosen by its key also sets the kind of game."""
        chosen = model_mod.sample(key or ("side" if side else "top"))
        # the plain button is today's path: the kind of game stays what it was
        self.sample_archetype = chosen.archetype if key else ""
        self.sample_key = key
        sample = paths.sample_pack_dir(chosen.folder)
        if not sample.is_dir():
            QMessageBox.warning(
                self,
                self.tr("Sample pack"),
                self.tr("The sample pack was not found: {0}").format(sample),
            )
            return False
        profile = sample / chosen.profile
        if profile.is_file():
            try:
                profiles.install_profile(profile)  # the audit of the sample is all CONFIRMED
            except (RpgGenError, OSError, ValueError):
                log.warning("could not install the sample profile", exc_info=True)
        self._loading = True
        try:
            self.pack_list.clear()
            self.pack_list.add_path(sample)
            self.target_edit.setText(str(self.sample_target()))
            self.name_edit.setText(chosen.name)
            self.model.name_touched = True
            self.model.touch_all()
        finally:
            self._loading = False
        self._debounce.stop()
        inputs = self.inputs()
        generation = self.model.begin_check()
        result = check_inputs(inputs.godot, inputs.target, inputs.sources)
        self.model.finish_check(generation, inputs.key(), result)
        self._refresh_cheap()
        self.changed.emit()
        ok = not [i for i in self.validate(WizardState()) if i.severity is Severity.ERROR]
        if ok:
            self.sampleReady.emit()
        return ok

    # ------------------------------------------------------------------ editing

    def sources(self) -> list[Path]:
        return self.pack_list.paths()

    def target(self) -> Path | None:
        text = self.target_edit.text().strip()
        return Path(text) if text else None

    def godot_path(self) -> Path | None:
        text = self.godot_combo.currentText().strip()
        return Path(text) if text else None

    def inputs(self) -> Inputs:
        return Inputs(
            self.sources(), self.target(), self.godot_path(), self.name_edit.text().strip()
        )

    def add_sources(self, paths_: list[Path]) -> None:
        """Add folders and archives. One that is a bundle of packs is not added: its
        checklist opens, and what is ticked there is (T16.22)."""
        for path in self.model.new_sources(self.sources(), paths_):
            sniffed = self.bundle_of(path)
            if sniffed is None:
                self.pack_list.add_path(path)
            else:
                self.choose_packs(path, sniffed)  # Cancel adds nothing
        self._suggest_from_first_pack()
        self._on_inputs_changed()

    def remove_row(self, row: int) -> None:
        """The cross on a pack card. On the row of a bundle it takes all the bundle's packs,
        after the confirmation."""
        if not 0 <= row < self.pack_list.count():
            return
        bundle = self.pack_list.item(row).data(GROUP_ROLE)
        if bundle:
            taken = [self.pack_list.item(r) for r in self.pack_list.group_rows(bundle)[1:]]
            names = [Path(item.data(Qt.ItemDataRole.UserRole)).name for item in taken]
            if not self.confirm_remove_packs(names):
                return
        self.pack_list.remove_rows([row])
        self.model.touched["packs"] = True
        self._on_inputs_changed()

    def remove_selected(self) -> None:
        rows = [self.pack_list.row(item) for item in self.pack_list.selectedItems()]
        self.pack_list.remove_rows(rows)
        self.model.touched["packs"] = True
        self._on_inputs_changed()

    # ------------------------------------------------------------------ a bundle of packs

    def bundle_of(self, path: Path) -> pack_sniff.PackSniff | None:
        """What the listing of ``path`` says, when it is a bundle of packs; else None.
        Nothing is unpacked, and the listing is read for a second at most."""
        sniffed = pack_sniff.sniff(path)
        return sniffed if sniffed.bundle else None

    def run_bundle_dialog(self, dialog: BundleDialog) -> bool:  # overridden by tests
        return dialog.exec() == BundleDialog.DialogCode.Accepted

    def confirm_remove_packs(self, names: list[str]) -> bool:  # overridden by tests
        """The confirmation before packs of a bundle leave the project."""
        answer = QMessageBox.question(
            self,
            self.tr("Remove packs"),
            self.tr(
                "Remove {0} pack(s) from the project?\n\n{1}\n\nWhat you set for their assets "
                "in the audit is not used any more."
            ).format(len(names), "\n".join(names[:12]) + ("\n…" if len(names) > 12 else "")),
        )
        return answer == QMessageBox.StandardButton.Yes

    def choose_packs(self, bundle: Path, sniffed: pack_sniff.PackSniff | None = None) -> bool:
        """Open *Choose packs* for a bundle, with the packs the list has from it ticked.
        Ticking adds a pack; clearing one removes it after the confirmation. False when the
        dialog was cancelled, the removal declined, or ``bundle`` is not one."""
        sniffed = sniffed or self.bundle_of(bundle)
        if sniffed is None:
            return False
        present = self.model.bundle_choice(self.sources(), bundle, sniffed.bundle)
        dialog = BundleDialog(bundle.name, sniffed.bundle, set(present) or None, self)
        if not self.run_bundle_dialog(dialog):
            return False
        chosen = dialog.chosen()
        removed = [name for name in present if name not in chosen]
        if removed and not self.confirm_remove_packs(removed):
            return False
        by_name = {pack.name: model_mod.member_source(bundle, pack) for pack in sniffed.bundle}
        doomed = {str(by_name[name]).casefold() for name in removed}
        rows = [
            self.pack_list.row(item)
            for item in self.pack_list.pack_items()
            if str(item.data(Qt.ItemDataRole.UserRole)).casefold() in doomed
        ]
        self.pack_list.remove_rows(rows)
        for name in chosen:
            if name not in present:
                self.pack_list.add_path(by_name[name])
        self.model.touched["packs"] = True
        return True

    def choose_packs_at(self, row: int | None = None) -> bool:
        """*Choose packs…* on the row of a bundle, or the button under the list: the bundle
        of the current row, else the first one in the list."""
        if row is None:
            row = self.pack_list.currentRow()
        bundle = self.pack_list.bundle_at(row) if row >= 0 else None
        if bundle is None:
            bundles = self.pack_list.bundles()
            if not bundles:
                return False
            bundle = bundles[0]
        done = self.choose_packs(bundle)
        if done:
            self._suggest_from_first_pack()
            self._on_inputs_changed()
        return done

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        """Enter or a double click on the row of a bundle opens its checklist."""
        row = self.pack_list.row(item)
        if row >= 0 and item.data(GROUP_ROLE):
            self.choose_packs_at(row)

    def _browse_archives(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr("Add asset packs"),
            app_settings.get().last_pack_dir,
            self.tr("Archives (*.zip *.7z *.rar)"),
        )
        if files:
            app_settings.update(last_pack_dir=str(Path(files[0]).parent))
        self.add_sources([Path(f) for f in files])

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Add asset pack folder"), app_settings.get().last_pack_dir
        )
        if folder:
            app_settings.update(last_pack_dir=str(Path(folder).parent))
            self.add_sources([Path(folder)])

    def _browse_target(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Output folder"), app_settings.get().last_target_dir
        )
        if folder:
            app_settings.update(last_target_dir=str(Path(folder).parent))
            self.target_edit.setText(folder)

    def _browse_godot(self) -> None:
        saved = app_settings.get().godot_exe
        exe, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Godot executable"),
            str(Path(saved).parent) if saved else "",
            self.tr("Executables (*.exe);;All (*)"),
        )
        if exe:
            self.godot_combo.setCurrentText(exe)

    # ------------------------------------------------------------------ download godot

    def confirm_godot_download(self, destination: Path) -> bool:  # overridden by tests
        return godot_download.confirm(self, destination)

    def download_godot(self) -> Path | None:
        """Download the supported Godot after a confirmation; selects it. None when declined,
        cancelled or failed."""
        destination = godot_fetch.managed_dir()
        if not self.confirm_godot_download(destination):
            return None
        exe = godot_download.download(self, destination)
        if exe is None:
            return None
        if self.godot_combo.findText(str(exe)) < 0:
            self.godot_combo.insertItem(0, str(exe))
        self.godot_combo.setCurrentText(str(exe))
        return exe

    def _touch(self, which: str) -> None:
        self.model.touched[which] = True
        self._refresh_cheap()

    def _suggest_from_first_pack(self) -> None:
        name, folder = self.model.suggestions(
            self.sources(), self.name_edit.text(), self.target_edit.text(), self.documents_dir()
        )
        if name is not None:
            self.name_edit.setText(name)
        if folder is not None:
            self.target_edit.setText(folder)

    def _on_target_changed(self) -> None:
        target = self.target()
        if not self.model.name_touched and not self._loading:
            self.name_edit.setText(target.name if target else "")
        self.form.show_update_button(target is not None and preflight.is_rpggen_project(target))
        self._on_inputs_changed()

    def _on_name_edited(self) -> None:
        self.model.name_typed()
        self.changed.emit()

    def _on_inputs_changed(self) -> None:
        if self._loading:
            return
        self._debounce.start()
        self._refresh_cheap()
        self.changed.emit()

    # ------------------------------------------------------------------ pack update

    def choose_update_source(self, pack_id: str) -> Path | None:  # overridden by tests
        file, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("New version of {0}").format(pack_id),
            "",
            self.tr("Archives (*.zip *.7z *.rar)"),
        )
        return Path(file) if file else None

    def choose_pack_id(self, pack_ids: list[str]) -> str | None:  # overridden by tests
        if len(pack_ids) == 1:
            return pack_ids[0]
        pack_id, ok = QInputDialog.getItem(
            self, self.tr("Update pack"), self.tr("Which pack?"), pack_ids, 0, False
        )
        return pack_id if ok else None

    def confirm_update(self, summary: str) -> bool:  # overridden by tests
        answer = QMessageBox.question(self, self.tr("Update pack"), summary)
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def update_summary(pack_id: str, d: pack_diff.PackDiff) -> str:
        return model_mod.update_summary(pack_id, d)

    def update_pack(self, pack_id: str | None = None, new_source: Path | None = None) -> bool:
        """Swap a pack of the existing project for a newer release (T5.05).

        Shows what changed; on confirmation the pack list points at the new source and the audit
        opens on the "Changed in update" filter. Returns True when the update was accepted.
        """
        target = self.target()
        pack_ids = self.model.project_pack_ids(target)
        if target is None or not pack_ids:
            return False
        pack_id = pack_id or self.choose_pack_id(pack_ids)
        if pack_id is None or pack_id not in pack_ids:
            return False
        new_source = new_source or self.choose_update_source(pack_id)
        if new_source is None:
            return False
        try:
            d = self.model.diff_update(target, pack_id, new_source)
        except (RpgGenError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Update pack"), str(exc))
            return False
        if not self.confirm_update(self.update_summary(pack_id, d)):
            return False
        old_source = self.model.old_source(target, pack_id)
        listed = [str(p).casefold() for p in self.sources()]
        if str(Path(old_source)).casefold() in listed:
            item = self.pack_list.pack_items()[listed.index(str(Path(old_source)).casefold())]
            item.setText(str(new_source))
            item.setData(Qt.ItemDataRole.UserRole, str(new_source))
        else:
            self.pack_list.add_path(new_source)
        self.model.record_update(new_source, pack_id, d)
        self._on_inputs_changed()
        return True

    # ------------------------------------------------------------------ live validation

    def _start_check(self) -> None:
        inputs = self.inputs()
        key = inputs.key()
        generation = self.model.begin_check()
        worker = workers.Worker(check_inputs, inputs.godot, inputs.target, inputs.sources)

        def done(result: InputCheck) -> None:
            try:
                self.godot_combo.objectName()
            except RuntimeError:
                return  # the page was closed while the check ran
            if self.model.finish_check(generation, key, result):
                self._refresh_cheap()
                self.changed.emit()

        def failed(exc: object) -> None:
            log.warning("input check failed: %s", exc)

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self._worker = worker  # keep it alive until its signals are delivered
        worker.start()

    def _current_check(self) -> InputCheck | None:
        return self.model.current_check(self.inputs())

    def _refresh_name_status(self) -> None:
        show_status(self.name_status, self.model.name_status(self.name_edit.text().strip()))

    def _refresh_pack_rows(self, check: InputCheck | None) -> None:
        for row in range(self.pack_list.count()):
            item = self.pack_list.item(row)
            bundle = item.data(GROUP_ROLE)
            if bundle:  # the row over the packs taken from a bundle
                taken = len(self.pack_list.group_rows(bundle)) - 1
                card = self.model.group_card(str(bundle), check, taken)
                item.setToolTip(card["error"] or str(bundle))
                item.setData(CARD_ROLE, card)
                continue
            path = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
            text, tooltip = self.model.row_text(path, check)
            item.setText(text)
            item.setToolTip(tooltip)
            item.setData(CARD_ROLE, self.model.card_for(path, check))

    def _refresh_cheap(self) -> None:
        """Update the field lines from the latest completed slow check."""
        inputs = self.inputs()
        show_status(self.packs_status, self.model.packs_status(inputs))
        self._refresh_pack_rows(self.model.current_check(inputs))
        godot_status = self.model.godot_status(inputs)
        show_status(self.godot_status, godot_status)
        self.form.show_godot_chip(godot_status)  # fine: the version, as a chip by the label
        self.download_godot_button.setVisible(self.model.offers_download(inputs))
        show_status(self.target_status, self.model.target_status(inputs))
        show_status(self.name_status, self.model.name_status(inputs.name))

    def status(self, state: WizardState) -> tuple[str, int]:
        if state.catalog is None:
            return ("none", 0)
        return ("ok", len(state.pack_sources))

    def validate(self, state: WizardState) -> list[Issue]:
        return self.model.validate(self.inputs())

    def reveal_missing(self, state: WizardState) -> None:
        """Next was pressed with fields still empty: mark them all and focus the first one."""
        self.model.touch_all()
        self._refresh_cheap()
        order = (
            (not self.sources(), self.form.packs_focus()),
            (self.target() is None, self.target_edit),
            (self.godot_path() is None, self.godot_combo),
            (not self.name_edit.text().strip(), self.name_edit),
        )
        for missing, widget in order:
            if missing:
                widget.setFocus()
                break

    # ------------------------------------------------------------------ state <-> widgets

    def enter(self, state: WizardState) -> None:
        self._loading = True
        try:
            self.pack_list.clear()
            for source in state.pack_sources:
                self.pack_list.add_path(source)
            self.target_edit.setText(str(state.target) if state.target else "")
            self.model.load(state)
            self.name_edit.setText(state.project_name)
            self.godot_combo.clear()
            candidates, current = model_mod.godot_choices(
                state.godot_exe, app_settings.get().godot_exe
            )
            self.godot_combo.addItems(candidates)
            if current is not None:
                self.godot_combo.setCurrentText(current)
        finally:
            self._loading = False
        self._start_check()
        self._refresh_cheap()
        self._take_focus_request(state)

    def _take_focus_request(self, state: WizardState) -> None:
        """A one-click fix on Results points at a button of this page: focus it."""
        name, state.project_focus = state.project_focus, ""
        widget = self.findChild(QPushButton, name) if name else None
        if widget is not None and widget.isEnabled():
            widget.setFocus()

    def ask_resume(self) -> bool:
        """Ask whether to continue the saved session of this output folder."""
        answer = QMessageBox.question(
            self,
            self.tr("Resume previous session?"),
            self.tr("There is saved work for this output folder. Resume it?"),
        )
        return answer == QMessageBox.StandardButton.Yes

    def leave(self, state: WizardState) -> bool | None:
        inputs = self.inputs()
        self.model.store(state, inputs)
        if state.godot_exe is not None and state.godot_exe.is_file():
            app_settings.update(godot_exe=str(state.godot_exe))
        if inputs.target is None or not inputs.sources:
            return None
        previous = model_mod.load_previous(state, inputs.target, self.ask_resume)
        key = tuple(str(p) for p in inputs.sources)
        if not model_mod.needs_analysis(state, key, previous):
            return True
        if previous is not None:
            state.catalog = previous
        if not self._run_analysis(state):
            return False
        state.analyzed_key = key
        model_mod.refresh_config(state)
        return True

    def _default_config(self, state: WizardState) -> config_mod.GeneratorConfig:
        return model_mod.default_config(state)

    def _run_analysis(self, state: WizardState) -> bool:
        """Analyze in a worker behind a modal progress dialog; False when cancelled or failed."""
        return analysis_progress.run_analysis(self, state)
