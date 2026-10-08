"""The wizard window: sidebar of pages, stacked page widgets and the Back / Next / Quit bar."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import app_settings
from rpggen.errors import Issue, Severity
from rpggen.gui import state as state_mod
from rpggen.gui.pages.base import EMPTY_CODE, WizardPage, form_error
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.welcome_page import WelcomePage
from rpggen.gui.window_menus import WindowMenus

log = logging.getLogger(__name__)

PAGE_NAMES = ["Project", "Archetype", "Audit", "Mapping", "Options", "Generate", "Results"]
OPTIONS_INDEX = 4  # the last page before generation: its Next button reads "Generate"
DEFAULT_WINDOW = (1100, 720)
NARROW_BELOW = 1000  # narrower than this the sidebar shows the numbers only
SIDEBAR_WIDE, SIDEBAR_NARROW = 170, 52
MIN_WINDOW = (880, 540)  # the layout test (tests/gui/test_layout_fit.py) runs at this size


class StubPage(WizardPage):
    """Placeholder for a page that a later task provides."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        layout = QVBoxLayout(self)
        label = QLabel(self.tr("{0} (not built yet)").format(title))
        label.setObjectName("stubLabel")
        layout.addWidget(label)
        layout.addStretch(1)


def stub_pages() -> list[WizardPage]:
    """Seven placeholder pages whose first one needs a pack (used by tests of the shell)."""
    pages: list[WizardPage] = [StubPage(name) for name in PAGE_NAMES]
    pages[0].validate = lambda state: (  # type: ignore[method-assign]
        [] if state.pack_sources else [form_error("Add at least one asset pack.")]
    )
    return pages


def default_pages() -> list[WizardPage]:
    from rpggen.gui.pages.archetype_page import ArchetypePage
    from rpggen.gui.pages.audit_page import AuditPage
    from rpggen.gui.pages.generate_page import GeneratePage
    from rpggen.gui.pages.mapping_page import MappingPage
    from rpggen.gui.pages.options_page import OptionsPage
    from rpggen.gui.pages.results_page import ResultsPage

    pages = stub_pages()
    pages[0] = ProjectPage()
    pages[1] = ArchetypePage()
    pages[2] = AuditPage()
    pages[3] = MappingPage()
    pages[4] = OptionsPage()
    pages[5] = GeneratePage()
    pages[6] = ResultsPage()
    return pages


class MainWindow(WindowMenus, QMainWindow):
    def __init__(
        self,
        state: state_mod.WizardState | None = None,
        pages: list[WizardPage] | None = None,
        show_welcome: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle(self.tr("rpggen"))
        self.resize(*DEFAULT_WINDOW)
        self.setMinimumSize(*MIN_WINDOW)
        self._restore_geometry()
        self.state = state or state_mod.WizardState()
        self.pages = pages if pages is not None else default_pages()
        self.visited: set[int] = set()
        self.current_index = -1
        self.issues: list[Issue] = []

        central = QWidget()
        central.setObjectName("central")
        self.root_stack = QStackedWidget()
        self.root_stack.setObjectName("rootStack")
        self.welcome = WelcomePage()
        self.root_stack.addWidget(self.welcome)  # index 0
        self.root_stack.addWidget(central)  # index 1: the wizard
        self.root_stack.setCurrentIndex(1)
        self.setCentralWidget(self.root_stack)
        outer = QVBoxLayout(central)
        body = QHBoxLayout()
        outer.addLayout(body, 1)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDE)
        self._sidebar_names: list[str] = []
        for i, page in enumerate(self.pages):
            name = self.tr(PAGE_NAMES[i] if i < len(PAGE_NAMES) else page.title)
            self._sidebar_names.append(name)
            item = QListWidgetItem(f"{i + 1}. {name}")
            item.setToolTip(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.sidebar.addItem(item)
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        for page in self.pages:
            page.setObjectName(f"page_{page.title.lower()}" if page.title else "page")
            page.changed.connect(self.refresh)
            if isinstance(page, ProjectPage):
                page.sampleReady.connect(lambda: self.continue_to(OPTIONS_INDEX))
            if hasattr(page, "generateAnother"):
                page.generateAnother.connect(self.new_project)  # type: ignore[attr-defined]
                page.changeOptions.connect(self.change_options)  # type: ignore[attr-defined]
                page.goToProject.connect(lambda: self.show_page(0))  # type: ignore[attr-defined]
            focus_signal = getattr(page, "focus_next", None)
            if focus_signal is not None:  # a page that is finished points at the Next button
                focus_signal.connect(lambda: self.next_button.setFocus())  # type: ignore[has-type]
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)

        self.problem_label = QLabel()
        self.problem_label.setObjectName("problemLabel")
        self.problem_label.setWordWrap(True)
        outer.addWidget(self.problem_label)

        bar = QHBoxLayout()
        self.back_button = QPushButton(self.tr("Back"))
        self.back_button.setObjectName("backButton")
        self.next_button = QPushButton(self.tr("Next"))
        self.next_button.setObjectName("nextButton")
        self.quit_button = QPushButton(self.tr("Quit"))
        self.quit_button.setObjectName("quitButton")
        bar.addWidget(self.quit_button)
        bar.addStretch(1)
        bar.addWidget(self.back_button)
        bar.addWidget(self.next_button)
        outer.addLayout(bar)
        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.quit_button.clicked.connect(self.close)
        self.next_button.setShortcut("Alt+N")
        self.back_button.setShortcut("Alt+B")
        self.next_button.setToolTip(self.tr("Go to the next page (Alt+N)"))
        self.back_button.setToolTip(self.tr("Go back one page (Alt+B)"))
        self.quit_button.setToolTip(self.tr("Close rpggen (Ctrl+Q)"))

        self._wire_welcome()
        self._build_menus()
        help_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents), self)
        help_shortcut.activated.connect(self.show_help_here)
        if self.pages:
            self.show_page(0)
        if show_welcome:
            self.show_welcome_view()

    def open_target(self, target: Path) -> None:
        """Fill the project page's output folder (an existing project is regenerated)."""
        for page in self.pages:
            if isinstance(page, ProjectPage):
                page.target_edit.setText(str(target))
                return

    # ------------------------------------------------------------------ navigation

    @property
    def current_page(self) -> WizardPage:
        return self.pages[self.current_index]

    def show_page(self, index: int) -> None:
        self.current_index = index
        self.visited.add(index)
        self.stack.setCurrentIndex(index)
        self.current_page.enter(self.state)
        self.refresh()

    def go_next(self) -> None:
        if not self.next_button.isEnabled() or self.current_index >= len(self.pages) - 1:
            return
        if any(i.code == EMPTY_CODE for i in self.issues):
            self.current_page.reveal_missing(self.state)  # say what is missing; do not leave
            self.refresh()
            return
        if self._leave_current():
            self.show_page(self.current_index + 1)

    def continue_to(self, index: int) -> None:
        """Press Next until page ``index`` is shown or a page stops the way (errors, a veto)."""
        while self.current_index < index and self.next_button.isEnabled():
            before = self.current_index
            self.go_next()
            if self.current_index == before:
                break

    def change_options(self) -> None:
        """Results > Change options and regenerate: back to Options on the project that exists
        now, so the next run regenerates it safely."""
        self.state.regenerating = True
        self.state.run_result = None
        self.show_page(OPTIONS_INDEX)

    def go_back(self) -> None:
        if self.current_index <= 0:
            return
        if self._leave_current():
            self.show_page(self.current_index - 1)

    def _leave_current(self) -> bool:
        """Let the page write its values; False when the page vetoed leaving."""
        if self.current_page.leave(self.state) is False:
            return False
        if self.state.target is not None:
            try:
                state_mod.save_draft(self.state)
            except OSError:
                log.warning("could not save the draft", exc_info=True)
        return True

    def _on_sidebar_clicked(self, item: QListWidgetItem) -> None:
        index = self.sidebar.row(item)
        if index in self.visited and index != self.current_index and self._leave_current():
            self.show_page(index)

    # ------------------------------------------------------------------ state of the controls

    def _restore_geometry(self) -> None:
        saved = app_settings.get().window
        screens = [
            (g.x(), g.y(), g.width(), g.height())
            for g in (s.availableGeometry() for s in QGuiApplication.screens())
        ]
        fitted = app_settings.clamp_geometry(saved, screens, MIN_WINDOW)
        if fitted is None:
            return
        self.setGeometry(*fitted)
        if saved.get("maximized"):
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _save_geometry(self) -> None:
        maximized = bool(self.windowState() & Qt.WindowState.WindowMaximized)
        geometry = self.normalGeometry() if maximized else self.geometry()
        app_settings.update(
            window={
                "x": geometry.x(),
                "y": geometry.y(),
                "w": geometry.width(),
                "h": geometry.height(),
                "maximized": int(maximized),
            }
        )

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._fit_sidebar()

    def _fit_sidebar(self) -> None:
        """Below ``NARROW_BELOW`` px the sidebar keeps the step numbers; the names are tooltips."""
        narrow = self.width() < NARROW_BELOW
        self.sidebar.setFixedWidth(SIDEBAR_NARROW if narrow else SIDEBAR_WIDE)
        for i, name in enumerate(self._sidebar_names):
            self.sidebar.item(i).setText(f"{i + 1}" if narrow else f"{i + 1}. {name}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        for page in self.pages:
            request = getattr(page, "request_close", None)
            if request is not None and not request():
                event.ignore()
                return
        self._save_geometry()
        super().closeEvent(event)

    def refresh(self) -> None:
        """Re-validate the current page and update the sidebar and buttons."""
        if self.current_index < 0:
            return
        page = self.current_page
        self.issues = page.validate(self.state)
        errors = [i for i in self.issues if i.severity is Severity.ERROR]
        blocking = [i for i in errors if i.code != EMPTY_CODE]  # empty fields wait for the press
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            enabled = i in self.visited
            flags = item.flags()
            item.setFlags(
                flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled
            )
        self.sidebar.setCurrentRow(self.current_index)
        last = self.current_index >= len(self.pages) - 1
        self.back_button.setEnabled(self.current_index > 0 and page.allow_back)
        self.next_button.setVisible(not last)
        self.quit_button.setVisible(not getattr(page, "running", False))  # Cancel is the page's
        self.next_button.setEnabled(not blocking and page.allow_next)
        label = page.next_label or (
            self.tr("Generate") if self.current_index == OPTIONS_INDEX else self.tr("Next")
        )
        self.next_button.setText(label)
        inline = {"GUI-INPUT", EMPTY_CODE} if page.shows_inline_errors else set()
        shown = [i for i in errors if i.code not in inline]
        self.problem_label.setText("\n".join(i.message for i in shown))
        self.problem_label.setVisible(bool(shown))
        self._update_title()
