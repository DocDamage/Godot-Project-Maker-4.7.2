"""The menu bar, the welcome view and the Help actions of the main window (T11.10, T11.11)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

import rpggen
from rpggen.core import app_settings, preflight, profile_registry, update_check
from rpggen.errors import format_message
from rpggen.gui import state as state_mod
from rpggen.gui import theme, translations, workers
from rpggen.gui.dialogs import diagnostic_export, help_viewer
from rpggen.gui.dialogs.about_dialog import AboutDialog
from rpggen.gui.dialogs.error_lookup import ErrorLookupDialog
from rpggen.gui.dialogs.storage_dialog import StorageDialog
from rpggen.gui.widgets.task_progress import error_text, run_task

if TYPE_CHECKING:  # pragma: no cover
    from rpggen.gui.pages.base import WizardPage

SHORTCUTS = (
    ("F1", "Open the user guide at the current page"),
    ("Alt+N / Alt+B", "Next / Back"),
    ("Ctrl+Q", "Quit rpggen"),
    ("Ctrl+= / Ctrl+-", "Larger / smaller thumbnails (Audit page)"),
    ("Ctrl+Z / Ctrl+Y", "Undo / Redo (Audit page)"),
    ("C", "Confirm the selected assets (Audit page)"),
    ("X", "Exclude the selected assets (Audit page)"),
    ("N / Shift+N", "Next / previous asset that needs attention (Audit page)"),
    ("F7", "Review mode: one asset at a time with a large preview (Audit page; Esc leaves)"),
    ("1 - 9", "Give the selected assets the role in that slot (Audit page)"),
    ("Ctrl+Shift+S", "Select the assets that look like the selected one (Audit page)"),
    ("Ctrl + mouse wheel", "Zoom the asset grid (Audit page)"),
)


def shortcuts_text() -> str:
    return "\n".join(f"{keys:<20} {what}" for keys, what in SHORTCUTS)


class WindowMenus:
    """Mixed into ``MainWindow``; it relies on ``pages``, ``state``, ``root_stack``, ``welcome``,
    ``show_page`` and ``open_target``."""

    # ------------------------------------------------------------------ construction

    def _build_menus(self: QMainWindow) -> None:  # type: ignore[misc]
        bar = self.menuBar()
        bar.setObjectName("mainMenuBar")

        file_menu = bar.addMenu(self.tr("&File"))
        self.new_action = self._action(
            file_menu, self.tr("&New project"), "newProject", self.new_project
        )
        self.open_action = self._action(
            file_menu, self.tr("&Open project…"), "openProject", self.open_project_dialog
        )
        self.recent_menu = file_menu.addMenu(self.tr("Recent projects"))
        self.recent_menu.setObjectName("recentMenu")
        file_menu.aboutToShow.connect(self._fill_recent_menu)
        file_menu.addSeparator()
        self.sheet_action = self._action(
            file_menu,
            self.tr("Export contact s&heet…"),
            "contactSheetMenuAction",
            self.export_contact_sheet,
        )
        self.conflicts_action = self._action(
            file_menu, self.tr("Resolve &conflicts…"), "resolveConflictsAction", self.show_conflicts
        )
        file_menu.addSeparator()
        self.exit_action = self._action(file_menu, self.tr("&Quit"), "exitAction", self.close)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))

        edit_menu = bar.addMenu(self.tr("&Edit"))
        self.undo_menu_action = self._action(
            edit_menu,
            self.tr("&Undo\tCtrl+Z"),
            "undoMenuAction",
            lambda: self._forward_edit("undo_action"),
        )
        self.redo_menu_action = self._action(
            edit_menu,
            self.tr("&Redo\tCtrl+Y"),
            "redoMenuAction",
            lambda: self._forward_edit("redo_action"),
        )
        edit_menu.addSeparator()
        self.storage_action = self._action(
            edit_menu, self.tr("&Storage…"), "storageAction", self.show_storage
        )
        self.learned_action = self._action(
            edit_menu, self.tr("&Learned rules…"), "learnedRulesAction", self.show_learned_rules
        )
        self.confirm_regen_action = self._action(
            edit_menu,
            self.tr("Show changes before regenerating"),
            "confirmRegeneration",
            lambda checked=False: app_settings.update(confirm_regeneration=bool(checked)),
        )
        self.confirm_regen_action.setCheckable(True)
        self.confirm_regen_action.setChecked(app_settings.get().confirm_regeneration)
        edit_menu.aboutToShow.connect(self._sync_edit_actions)

        view_menu = bar.addMenu(self.tr("&View"))
        theme_menu = view_menu.addMenu(self.tr("Theme"))
        theme_group = QActionGroup(self)
        self.theme_actions: dict[str, QAction] = {}
        for key, label in (
            ("system", self.tr("Follow the system")),
            ("dark", self.tr("Dark")),
            ("light", self.tr("Light")),
        ):
            action = self._action(
                theme_menu, label, f"theme_{key}", lambda _=False, k=key: self.set_theme(k)
            )
            action.setCheckable(True)
            theme_group.addAction(action)
            self.theme_actions[key] = action
        self.theme_actions[theme.saved_theme()].setChecked(True)
        self.review_action = self._action(
            view_menu, self.tr("Review mode"), "reviewModeAction", self.toggle_review_mode
        )
        self.review_action.setShortcut(QKeySequence("F7"))
        self.review_action.setCheckable(True)
        view_menu.aboutToShow.connect(self._sync_review_action)
        self.motion_action = self._action(
            view_menu, self.tr("Reduce motion"), "reduceMotionAction", self.set_reduce_motion
        )
        self.motion_action.setCheckable(True)
        self.motion_action.setToolTip(
            self.tr("No fading or rolling menus, lists and tooltips. Follows the system until set.")
        )
        self.motion_action.setChecked(theme.apply_motion())
        size_menu = view_menu.addMenu(self.tr("Thumbnail size"))
        size_group = QActionGroup(self)
        self.thumb_actions: dict[int, QAction] = {}
        current = app_settings.get().thumb_size
        for size in app_settings.THUMB_SIZES:
            action = self._action(
                size_menu,
                f"{size} px",
                f"thumb_{size}",
                lambda _=False, s=size: self.set_thumb_size(s),
            )
            action.setCheckable(True)
            action.setChecked(size == current)
            size_group.addAction(action)
            self.thumb_actions[size] = action
        size_menu.addSeparator()
        self.larger_action = self._action(
            size_menu, self.tr("Larger"), "thumbLarger", lambda: self.step_thumb_size(1)
        )
        self.larger_action.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        self.smaller_action = self._action(
            size_menu, self.tr("Smaller"), "thumbSmaller", lambda: self.step_thumb_size(-1)
        )
        self.smaller_action.setShortcut(QKeySequence("Ctrl+-"))
        # the wizard's language (T12.56): the system's, or one that has a translation
        language_menu = view_menu.addMenu(self.tr("Language"))
        language_menu.setObjectName("languageMenu")
        language_group = QActionGroup(self)
        self.language_actions: dict[str, QAction] = {}
        choices = [(translations.SYSTEM, self.tr("Follow the system"))]
        choices += [(lang, translations.display_name(lang)) for lang in translations.available()]
        choices.append(("en", "English"))
        for key, label in choices:
            action = self._action(
                language_menu,
                label,
                f"language_{key or 'system'}",
                lambda _=False, k=key: self.set_language(k),
            )
            action.setCheckable(True)
            language_group.addAction(action)
            self.language_actions[key] = action
        saved = app_settings.get().language
        self.language_actions[saved if saved in self.language_actions else ""].setChecked(True)

        help_menu = bar.addMenu(self.tr("&Help"))
        self.guide_action = self._action(
            help_menu, self.tr("User guide\tF1"), "guideAction", self.show_user_guide
        )
        self.codes_action = self._action(
            help_menu, self.tr("Error codes…"), "codesAction", self.show_error_codes
        )
        self.shortcuts_action = self._action(
            help_menu, self.tr("Keyboard shortcuts"), "shortcutsAction", self.show_shortcuts
        )
        self.tour_action = self._action(
            help_menu, self.tr("Show the tour again"), "tourAction", self.show_tour_again
        )
        help_menu.addSeparator()
        self.report_action = self._action(
            help_menu, self.tr("Report a problem…"), "reportAction", self.report_problem
        )
        self.update_action = self._action(
            help_menu, self.tr("Check for updates…"), "updateAction", self.check_for_updates
        )
        self.about_action = self._action(
            help_menu, self.tr("About rpggen"), "aboutAction", self.show_about
        )

    def _action(self, menu, text: str, name: str, slot) -> QAction:  # type: ignore[no-untyped-def]
        action = menu.addAction(text)
        action.setObjectName(name)
        action.triggered.connect(slot)
        return action

    def _wire_welcome(self) -> None:
        w = self.welcome  # type: ignore[attr-defined]
        w.trySampleRequested.connect(self.try_sample)
        w.trySideSampleRequested.connect(self.try_side_sample)
        w.ownPackRequested.connect(self.start_own_pack)
        w.openProjectRequested.connect(self.open_project_dialog)
        w.recentChosen.connect(lambda folder: self.open_project(Path(folder)))
        w.regenerateRequested.connect(lambda folder: self.regenerate_project(Path(folder)))
        w.downloadGodotRequested.connect(self.download_godot_from_welcome)

    # ------------------------------------------------------------------ welcome view

    def show_welcome_view(self) -> None:
        self.welcome.refresh()  # type: ignore[attr-defined]
        self.root_stack.setCurrentIndex(0)  # type: ignore[attr-defined]
        self._update_title()

    def leave_welcome(self) -> None:
        self.root_stack.setCurrentIndex(1)  # type: ignore[attr-defined]
        self._update_title()

    @property
    def welcome_visible(self) -> bool:
        return self.root_stack.currentIndex() == 0  # type: ignore[attr-defined]

    def _project_page(self):  # type: ignore[no-untyped-def]
        from rpggen.gui.pages.project_page import ProjectPage

        for page in self.pages:  # type: ignore[attr-defined]
            if isinstance(page, ProjectPage):
                return page
        return None

    def try_sample(self) -> None:
        """The welcome card: the same path as the small button on the Project page."""
        self.leave_welcome()
        self.show_page(0)  # type: ignore[attr-defined]
        page = self._project_page()
        if page is not None:
            page.try_sample()

    def try_side_sample(self) -> None:
        """The welcome card's second entry (T14.09): the side-view pack as a metroidvania, by
        the same walk to the Options page."""
        from rpggen.gui.models import project_model

        self.leave_welcome()
        self.show_page(0)  # type: ignore[attr-defined]
        page = self._project_page()
        if page is not None:
            # the Archetype page starts on the state's archetype when the walk reaches it
            self.state.archetype = project_model.SIDE_SAMPLE_ARCHETYPE  # type: ignore[attr-defined]
            page.try_sample(side=True)

    def start_own_pack(self) -> None:
        self.leave_welcome()
        self.show_page(0)  # type: ignore[attr-defined]

    def download_godot_from_welcome(self) -> None:
        page = self._project_page()
        if page is not None and page.download_godot() is not None:
            self.welcome.check_godot()  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ File menu

    def _blocked_by_running_page(self) -> bool:
        for page in self.pages:  # type: ignore[attr-defined]
            request = getattr(page, "request_close", None)
            if request is not None and not request():
                return True
        return False

    def new_project(self) -> None:
        if self._blocked_by_running_page():
            return
        self.state = state_mod.WizardState()  # type: ignore[attr-defined]
        self.visited.clear()  # type: ignore[attr-defined]
        self.show_page(0)  # type: ignore[attr-defined]
        self.show_welcome_view()

    def choose_project_folder(self) -> Path | None:  # overridden by tests
        folder = QFileDialog.getExistingDirectory(
            self,
            self.tr("Open project"),
            app_settings.get().last_target_dir,  # type: ignore[arg-type]
        )
        return Path(folder) if folder else None

    def open_project_dialog(self) -> None:
        folder = self.choose_project_folder()
        if folder is not None:
            self.open_project(folder)

    def regenerate_project(self, folder: Path) -> bool:
        """A project card's Regenerate (T13.08): open the project and walk to the Generate page
        as soon as its pages allow it. The generation then shows the changes before it writes
        them (Edit > Show changes before regenerating). The walk is given up when a page stops
        it or the user goes elsewhere."""
        if not self.open_project(folder):
            return False
        self._walk_to_generate = True
        self.continue_walk()
        return True

    def continue_walk(self) -> None:
        """Called whenever the window's state changed: go on towards Generate if a card asked."""
        if not getattr(self, "_walk_to_generate", False) or getattr(self, "_walking", False):
            return
        if self.welcome_visible or not self.next_button.isEnabled():  # type: ignore[attr-defined]
            return  # the packs are still being read, or a page has something to say
        from rpggen.gui.wizard import OPTIONS_INDEX

        self._walking = True
        try:
            self.continue_to(OPTIONS_INDEX)  # type: ignore[attr-defined]
            if self.current_index == OPTIONS_INDEX and self.next_button.isEnabled():  # type: ignore[attr-defined]
                self._walk_to_generate = False
                self.go_next()  # type: ignore[attr-defined]
            elif self.current_index > 0:  # type: ignore[attr-defined]
                self._walk_to_generate = False  # a page in between stopped the walk
        finally:
            self._walking = False

    def open_project(self, folder: Path) -> bool:
        """Open a generated project for regeneration; False when the folder is not one."""
        if not preflight.is_rpggen_project(folder):
            QMessageBox.warning(
                self,  # type: ignore[arg-type]
                self.tr("Open project"),
                self.tr("{0} is not a project made with rpggen.").format(folder),
            )
            return False
        if self._blocked_by_running_page():
            return False
        self.state = state_mod.WizardState()  # type: ignore[attr-defined]
        self.visited.clear()  # type: ignore[attr-defined]
        self.leave_welcome()
        self.show_page(0)  # type: ignore[attr-defined]
        self.open_target(folder)  # type: ignore[attr-defined]
        return True

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = app_settings.get().recent_projects
        unreachable = self.welcome.unavailable  # type: ignore[attr-defined]
        for project in recent:
            label = project.name or Path(project.target).name
            action = self.recent_menu.addAction(f"{label}  ({project.target})")
            action.triggered.connect(lambda _=False, t=project.target: self.open_project(Path(t)))
            action.setEnabled(project.target not in unreachable)  # known from the welcome view
        self.recent_menu.setEnabled(bool(recent))

    # ------------------------------------------------------------------ Edit menu

    def _audit_page(self):  # type: ignore[no-untyped-def]
        from rpggen.gui.pages.audit_page import AuditPage

        for page in self.pages:  # type: ignore[attr-defined]
            if isinstance(page, AuditPage):
                return page
        return None

    def _sync_edit_actions(self) -> None:
        audit = self._audit_page()
        on_audit = audit is not None and self.current_page is audit  # type: ignore[attr-defined]
        for menu_action, attr in (
            (self.undo_menu_action, "undo_action"),
            (self.redo_menu_action, "redo_action"),
        ):
            source = getattr(audit, attr, None) if on_audit else None
            menu_action.setEnabled(bool(source is not None and source.isEnabled()))

    def _forward_edit(self, attr: str) -> None:
        audit = self._audit_page()
        source = getattr(audit, attr, None) if audit is not None else None
        if source is not None and source.isEnabled():
            source.trigger()

    # ------------------------------------------------------------------ View menu

    def set_theme(self, name: str) -> None:
        theme.apply_theme(name)
        action = self.theme_actions.get(name)
        if action is not None:
            action.setChecked(True)

    def set_language(self, language: str) -> None:
        """Remember the wizard's language; it applies at the next start (the texts of the open
        window were set when it was made)."""
        if language == app_settings.get().language:
            return
        app_settings.update(language=language)
        action = self.language_actions.get(language)
        if action is not None:
            action.setChecked(True)
        self.tell_language_restart()

    def tell_language_restart(self) -> None:  # overridden by tests
        QMessageBox.information(
            self,  # type: ignore[arg-type]
            self.tr("Language"),
            self.tr("rpggen will use the new language the next time it starts."),
        )

    def set_reduce_motion(self, checked: bool = False) -> None:
        """View > Reduce motion: from now on the user's choice, not the system's."""
        app_settings.update(reduce_motion="on" if checked else "off")
        self.motion_action.setChecked(theme.apply_motion())

    def toggle_review_mode(self) -> None:
        """F7: the Audit page's review mode (only there)."""
        audit = self._audit_page()
        if audit is not None and self.current_page is audit:  # type: ignore[attr-defined]
            audit.toggle_review_mode()
        self._sync_review_action()

    def _sync_review_action(self) -> None:
        audit = self._audit_page()
        on_audit = audit is not None and self.current_page is audit  # type: ignore[attr-defined]
        self.review_action.setChecked(bool(on_audit and audit.in_review_mode))

    def set_thumb_size(self, size: int) -> None:
        app_settings.schedule(thumb_size=size)
        if size in self.thumb_actions:
            self.thumb_actions[size].setChecked(True)
        audit = self._audit_page()
        if audit is not None and hasattr(audit, "set_thumb_size"):
            audit.set_thumb_size(size)

    def step_thumb_size(self, direction: int) -> None:
        """Ctrl+= and Ctrl+-: the next larger or smaller thumbnail size."""
        sizes = app_settings.THUMB_SIZES
        current = app_settings.get().thumb_size
        index = sizes.index(current) if current in sizes else 0
        self.set_thumb_size(sizes[max(0, min(len(sizes) - 1, index + direction))])

    # ------------------------------------------------------------------ Help menu

    def show_user_guide(self, anchor: str = "") -> None:
        help_viewer.HelpViewer(self, anchor if isinstance(anchor, str) else "").exec()  # type: ignore[arg-type]

    def show_help_here(self) -> None:
        """F1: the guide at the section of the current page."""
        page: WizardPage = self.current_page  # type: ignore[attr-defined]
        anchor = getattr(page, "help_anchor", "")
        self.show_user_guide(anchor)

    def show_error_codes(self) -> None:
        ErrorLookupDialog(self).exec()  # type: ignore[arg-type]

    def show_tour_again(self) -> bool:
        """Help > Show the tour again: the Audit page's tour starts now when that page is shown,
        else the next time it is. True when it started now."""

        def forget(settings: app_settings.AppSettings) -> None:
            settings.tours_seen = [t for t in settings.tours_seen if t != "audit"]

        app_settings.store().update(forget)
        audit = self._audit_page()
        on_audit = audit is not None and self.current_page is audit  # type: ignore[attr-defined]
        if on_audit and not self.welcome_visible and audit.session is not None:
            return bool(audit.start_tour())
        QMessageBox.information(
            self,  # type: ignore[arg-type]
            self.tr("Tour"),
            self.tr("The tour starts the next time the Audit page is shown."),
        )
        return False

    def show_shortcuts(self) -> None:
        QMessageBox.information(self, self.tr("Keyboard shortcuts"), shortcuts_text())  # type: ignore[arg-type]

    def show_about(self) -> None:
        AboutDialog(self).exec()  # type: ignore[arg-type]

    def export_contact_sheet(self) -> None:
        """The Audit page's contact sheet (T12.57); it needs an analysed pack."""
        audit = self._audit_page()
        if audit is None or getattr(audit, "session", None) is None:
            QMessageBox.information(
                self,  # type: ignore[arg-type]
                self.tr("Export contact sheet"),
                self.tr("Add a pack and open the Audit page first."),
            )
            return
        audit.export_contact_sheet()

    def show_conflicts(self) -> None:
        """The resolver (T12.58) for the project the wizard has open."""
        from rpggen.core import conflicts
        from rpggen.gui.dialogs.conflict_dialog import ConflictDialog

        target = self.state.target  # type: ignore[attr-defined]
        if target is None or not conflicts.list_conflicts(target):
            QMessageBox.information(
                self,  # type: ignore[arg-type]
                self.tr("Resolve conflicts"),
                self.tr("The open project has no files with a .rpggen-new version.")
                if target is not None
                else self.tr("Open a generated project first."),
            )
            return
        ConflictDialog(target, None, self).exec()

    def show_learned_rules(self) -> None:
        """The rules learned from the audit fixes (T12.59); with an audit open they can become
        that project's folder rules."""
        from rpggen.gui.dialogs.learned_rules_dialog import LearnedRulesDialog

        audit = self._audit_page()
        session = getattr(audit, "session", None)
        pack_ids = [p.pack_id for p in session.catalog.packs] if session is not None else []
        add = audit.add_folder_rules if session is not None else None
        LearnedRulesDialog(None, pack_ids, add, self).exec()  # type: ignore[arg-type]

    def show_storage(self) -> None:
        StorageDialog(self).exec()  # type: ignore[arg-type]

    def ask_export_before_report(self) -> bool | None:  # overridden by tests
        """True: export a bundle first, False: just open the issues page, None: cancel."""
        answer = QMessageBox.question(
            self,  # type: ignore[arg-type]
            self.tr("Report a problem"),
            self.tr(
                "A diagnostic bundle (logs and settings, no art) helps a lot. Export one now and "
                "attach it to your report?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return None
        return answer == QMessageBox.StandardButton.Yes

    def open_url(self, url: str) -> None:  # overridden by tests
        QDesktopServices.openUrl(QUrl(url))

    def report_problem(self) -> None:
        choice = self.ask_export_before_report()
        if choice is None:
            return
        if choice:
            target = self.state.target  # type: ignore[attr-defined]
            diagnostic_export.export_bundle(self, target, self.state.godot_exe)  # type: ignore[attr-defined,arg-type]
        self.open_url(rpggen.ISSUES_URL)

    # -- update check: never automatic, only from this menu entry

    def update_fetcher(self):  # type: ignore[no-untyped-def]  # overridden by tests
        return None

    def show_update_result(self, message: str, url: str | None) -> None:  # overridden by tests
        box = QMessageBox(self)  # type: ignore[arg-type]
        box.setWindowTitle(self.tr("Check for updates"))
        box.setText(message)
        open_button = None
        if url:
            open_button = box.addButton(
                self.tr("Open download page"), QMessageBox.ButtonRole.AcceptRole
            )
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if open_button is not None and box.clickedButton() is open_button:
            self.open_url(url)  # type: ignore[arg-type]

    def check_for_updates(self) -> str:
        """One of "latest", "newer", "failed" (also shown to the user)."""
        outcome = run_task(
            self,  # type: ignore[arg-type]
            self.tr("Checking for updates…"),
            workers.check_for_update,
            fetch=self.update_fetcher(),
            object_name="updateProgress",
        )
        if outcome.cancelled:
            return "failed"
        if outcome.error is not None or outcome.value is None:
            reason = (
                error_text(outcome.error)
                if outcome.error is not None
                else self.tr("no published release was found")
            )
            if isinstance(outcome.error, profile_registry.RegistryError):
                reason = str(outcome.error)
            self.show_update_result(format_message("ENV-012", reason=reason), None)
            return "failed"
        release = outcome.value
        if update_check.is_newer(release.tag, rpggen.__version__):
            self.show_update_result(
                self.tr("Version {0} is available (you have {1}).").format(
                    release.tag.lstrip("v"), rpggen.__version__
                ),
                release.url,
            )
            return "newer"
        self.show_update_result(
            self.tr("You have the latest version ({0}).").format(rpggen.__version__), None
        )
        return "latest"

    # ------------------------------------------------------------------ window title

    def _update_title(self) -> None:
        state = self.state  # type: ignore[attr-defined]
        if self.welcome_visible:
            self.setWindowTitle("rpggen")
            return
        self.setWindowTitle(self.title_text())

    def title_text(self) -> str:
        """ "36 % · My game · 6. Generate — rpggen" (T15.18): the project (its name, else its
        folder's), the step, and in front the percentage while a run is on, so that the taskbar
        and Alt-Tab say where the user is and how far a minimised run has come."""
        state = self.state  # type: ignore[attr-defined]
        index = self.current_index  # type: ignore[attr-defined]
        name = (state.project_name or "").strip()
        if not name and state.target is not None:
            name = Path(state.target).name
        parts: list[str] = []
        if 0 <= index < len(self.pages):  # type: ignore[attr-defined]
            percent = getattr(self.pages[index], "run_percent", None)  # type: ignore[attr-defined]
            if percent is not None:
                parts.append(f"{percent} %")
        if name:
            parts.append(name + (" [regenerating]" if state.regenerating else ""))
        if 0 <= index < len(self._sidebar_names):  # type: ignore[attr-defined]
            parts.append(f"{index + 1}. {self._sidebar_names[index]}")  # type: ignore[attr-defined]
        return " · ".join(parts) + (" — " if parts else "") + "rpggen"
