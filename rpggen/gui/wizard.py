"""The wizard window: sidebar of pages, stacked page widgets and the Back / Next / Quit bar."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
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
from rpggen.gui import theme
from rpggen.gui.pages.base import EMPTY_CODE, WizardPage, form_error
from rpggen.gui.pages.project_page import ProjectPage
from rpggen.gui.pages.welcome_page import WelcomePage
from rpggen.gui.widgets import buttons, stepper
from rpggen.gui.widgets.card import DANGER, Banner
from rpggen.gui.window_menus import WindowMenus

log = logging.getLogger(__name__)

# marked for lupdate (T12.56); translated where the sidebar shows them
PAGE_NAMES: list[str] = cast(
    list[str],
    [
        QT_TRANSLATE_NOOP("MainWindow", "Project"),
        QT_TRANSLATE_NOOP("MainWindow", "Archetype"),
        QT_TRANSLATE_NOOP("MainWindow", "Audit"),
        QT_TRANSLATE_NOOP("MainWindow", "Mapping"),
        QT_TRANSLATE_NOOP("MainWindow", "Options"),
        QT_TRANSLATE_NOOP("MainWindow", "Generate"),
        QT_TRANSLATE_NOOP("MainWindow", "Results"),
    ],
)
AUDIT_INDEX = 2
OPTIONS_INDEX = 4  # the last page before generation: its Next button reads "Generate"
DEFAULT_WINDOW = (1100, 720)
NARROW_BELOW = 1000  # narrower than this the sidebar shows the numbers only
SIDEBAR_WIDE, SIDEBAR_NARROW = 170, 52
STATUS_GLYPHS = {"ok": "✓", "attention": "⚠", "error": "✖"}
MIN_WINDOW = (880, 540)  # the layout test (tests/gui/test_layout_fit.py) runs at this size


FADE_MS = 120


def fade_in(widget: QWidget) -> None:
    """Cross-fade a page that was just shown (T15.09): its opacity goes from 0 to 1 in 120 ms.
    With reduce motion on nothing is animated. The effect is removed when the fade ends, so a
    page is painted through an effect only while it fades."""
    if theme.reduce_motion() or not widget.isVisible():
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(FADE_MS)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done() -> None:
        try:
            if widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)  # type: ignore[arg-type]
        except RuntimeError:  # the window was closed during the fade
            pass

    animation.finished.connect(done)
    widget._fade = animation  # type: ignore[attr-defined]  # kept alive while it runs
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def fade_opacity(widget: QWidget) -> float:
    """1.0 for a page that is not fading (tests wait for it)."""
    effect = widget.graphicsEffect()
    return effect.opacity() if isinstance(effect, QGraphicsOpacityEffect) else 1.0


class StubPage(WizardPage):
    """Placeholder for a page that a later task provides."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.header.set_title(title)
        layout = self.page_layout()
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
        self._return_to: tuple[int, str] | None = None  # where Back goes after a side trip
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
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
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
        self.sidebar.setItemDelegate(stepper.StepDelegate(self.sidebar))
        self.sidebar.setMouseTracking(True)  # the hover look and the pointer of a row
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar.itemEntered.connect(self._on_sidebar_hover)
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        for page in self.pages:
            page.setObjectName(f"page_{page.title.lower()}" if page.title else "page")
            page.changed.connect(self.refresh)
            page.helpRequested.connect(self.show_user_guide)
            if isinstance(page, ProjectPage):
                page.sampleReady.connect(lambda p=page: self._on_sample_ready(p))
            if hasattr(page, "generateAnother"):
                page.generateAnother.connect(self.new_project)  # type: ignore[attr-defined]
                page.changeOptions.connect(self.change_options)  # type: ignore[attr-defined]
                page.goToProject.connect(lambda: self.show_page(0))  # type: ignore[attr-defined]
                page.showAssets.connect(self.show_assets_in_audit)  # type: ignore[attr-defined]
                page.generateAgain.connect(self.generate_again)  # type: ignore[attr-defined]
                page.showHelp.connect(self.show_user_guide)  # type: ignore[attr-defined]
            if hasattr(page, "showInAudit"):
                page.showInAudit.connect(self.show_asset_in_audit)  # type: ignore[attr-defined]
            focus_signal = getattr(page, "focus_next", None)
            if focus_signal is not None:  # a page that is finished points at the Next button
                focus_signal.connect(lambda: self.next_button.setFocus())  # type: ignore[has-type]
            self.stack.addWidget(page)
        body.addWidget(self.stack, 1)

        self.problem_label = Banner(DANGER)  # what stops Next, above the buttons (T15.06)
        self.problem_label.setObjectName("problemLabel")
        self.problem_label.setVisible(False)
        problem_row = QHBoxLayout()
        problem_row.setContentsMargins(theme.px("space_16"), 0, theme.px("space_16"), 0)
        problem_row.addWidget(self.problem_label)
        outer.addLayout(problem_row)

        bar = QHBoxLayout()
        bar.setContentsMargins(
            theme.px("space_12"), theme.px("space_8"), theme.px("space_16"), theme.px("space_12")
        )
        bar.setSpacing(theme.px("space_8"))
        self.back_button = QPushButton(self.tr("Back"))
        self.back_button.setObjectName("backButton")
        self.next_button = QPushButton(self.tr("Next"))
        self.next_button.setObjectName("nextButton")
        self.quit_button = QPushButton(self.tr("Quit"))
        self.quit_button.setObjectName("quitButton")
        buttons.set_kind(self.quit_button, buttons.QUIET)
        buttons.set_kind(self.back_button, buttons.SECONDARY)
        buttons.set_kind(self.next_button, buttons.PRIMARY)
        for button in (self.back_button, self.next_button):
            button.setMinimumWidth(buttons.BAR_BUTTON_WIDTH)
        bar.addWidget(self.quit_button)
        bar.addStretch(1)
        bar.addWidget(self.back_button)
        bar.addWidget(self.next_button)
        # a page's own button for the bar (the Generate page's Cancel): it takes Next's place
        # while that page runs
        self._bar_buttons: dict[int, QPushButton] = {}
        for i, page in enumerate(self.pages):
            extra = getattr(page, "bar_button", None)
            if isinstance(extra, QPushButton):
                bar.addWidget(extra)
                extra.setVisible(False)
                self._bar_buttons[i] = extra
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
        self._return_to = None  # only a jump to the audit sets it, right after this
        self.current_index = index
        self.visited.add(index)
        changed = self.stack.currentIndex() != index
        self.stack.setCurrentIndex(index)
        self.current_page.enter(self.state)
        self.refresh()
        if changed:
            fade_in(self.current_page)

    def go_next(self) -> None:
        if not self.next_button.isEnabled() or self.current_index >= len(self.pages) - 1:
            return
        if any(i.code == EMPTY_CODE for i in self.issues):
            self.current_page.reveal_missing(self.state)  # say what is missing; do not leave
            self.refresh()
            return
        if self._leave_current():
            self.show_page(self.current_index + 1)

    def _on_sample_ready(self, page) -> None:  # noqa: ANN001 - the Project page
        """A sample filled the Project page: on to the options. A sample that was chosen by
        its name is tried as the kind of game it is made for (the Archetype page starts on
        the state's kind when the walk reaches it)."""
        kind = getattr(page, "sample_archetype", "")
        if kind:
            self.state.archetype = kind
        self.continue_to(OPTIONS_INDEX)

    def continue_to(self, index: int) -> None:
        """Press Next until page ``index`` is shown or a page stops the way (errors, a veto)."""
        while self.current_index < index and self.next_button.isEnabled():
            before = self.current_index
            self.go_next()
            if self.current_index == before:
                break

    def show_asset_in_audit(self, asset_id: str, role: str = "") -> None:
        """Mapping > Show in audit: the Audit page with that asset selected and in view. Back
        then returns to the Mapping page, to the row that asked (T13.05)."""
        origin = self.current_index
        if not self._leave_current():
            return
        self.show_page(AUDIT_INDEX)
        audit = self.pages[AUDIT_INDEX]
        if hasattr(audit, "show_asset"):
            audit.show_asset(asset_id)
        self._return_to = (origin, role)

    def show_assets_in_audit(self, asset_ids: list[str]) -> None:
        """Results > Show these assets: the Audit page with only those assets in its grid."""
        if not self._leave_current():
            return
        self.show_page(AUDIT_INDEX)
        audit = self.pages[AUDIT_INDEX]
        if hasattr(audit, "show_assets"):
            audit.show_assets(set(asset_ids))

    def generate_again(self) -> None:
        """A one-click fix changed the state: generate again (the page starts on entry)."""
        self.show_page(OPTIONS_INDEX + 1)

    def change_options(self) -> None:
        """Results > Change options and regenerate: back to Options on the project that exists
        now, so the next run regenerates it safely."""
        self.state.regenerating = True
        self.state.run_result = None
        self.show_page(OPTIONS_INDEX)

    def go_back(self) -> None:
        self._walk_to_generate = False  # the user took over
        if self.current_index <= 0:
            return
        page = self.current_page
        stop = getattr(page, "stop_for_back", None)
        if getattr(page, "running", False) and callable(stop) and not stop():
            return  # a run that already writes the project is not left by Back
        self.state.sample_run = False  # the user looks at the options: they are their choice now
        if not self._leave_current():
            return
        came_from = self._return_to if self.current_index == AUDIT_INDEX else None
        if came_from is None:
            self.show_page(self.current_index - 1)
            return
        index, role = came_from  # the audit was a side trip from another page's row
        self.show_page(index)
        focus_row = getattr(self.pages[index], "focus_row", None)
        if callable(focus_row) and role:
            focus_row(role)

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

    def _on_sidebar_hover(self, item: QListWidgetItem) -> None:
        """The pointer over a step that can be clicked is a hand."""
        viewport = self.sidebar.viewport()
        if viewport is not None:
            enabled = bool(item.flags() & Qt.ItemFlag.ItemIsEnabled)
            viewport.setCursor(
                Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
            )

    def _on_sidebar_clicked(self, item: QListWidgetItem) -> None:
        index = self.sidebar.row(item)
        if index == self.current_index:
            return
        if index > self.current_index and index <= OPTIONS_INDEX and self.next_button.isEnabled():
            self.continue_to(index)  # forward: every page in between is entered and left, as
            return  # with Next, and the walk stops at the first one that blocks
        if index in self.visited and self._leave_current():
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
        self.sidebar.setFixedWidth(SIDEBAR_NARROW if self.width() < NARROW_BELOW else SIDEBAR_WIDE)
        self._update_sidebar_text()

    def _step_status(self, index: int) -> tuple[str, int]:
        """The status of a page the user has been to (the others show nothing)."""
        if index not in self.visited:
            return ("none", 0)
        try:
            return self.pages[index].status(self.state)
        except Exception:  # noqa: BLE001 - a status must never break the window
            log.warning("status of page %d failed", index, exc_info=True)
            return ("none", 0)

    def _update_sidebar_text(self) -> None:
        """ "3. Audit · 12 ⚠": number, name, a count, and a glyph so colour is never the only
        cue; narrow, only the number and the glyph (the rest is the tooltip)."""
        narrow = self.width() < NARROW_BELOW
        for i, name in enumerate(self._sidebar_names):
            kind, count = self._step_status(i)
            glyph = STATUS_GLYPHS.get(kind, "")
            number = f"{i + 1}"
            if narrow:
                text = f"{number} {glyph}".strip()
            else:
                text = f"{number}. {name}" + (f" · {count}" if count else "")
                text += f"  {glyph}" if glyph else ""
            item = self.sidebar.item(i)
            item.setText(text)
            meaning = {
                "ok": self.tr("done"),
                "attention": self.tr("needs attention"),
                "error": self.tr("must be fixed"),
            }.get(kind, "")
            spoken = self.tr("Step {0}, {1}").format(i + 1, name)
            if meaning:
                spoken += ", " + meaning + (f" ({count})" if count else "")
            item.setData(Qt.ItemDataRole.AccessibleTextRole, spoken)
            # what the step delegate paints (the text above stays for tests, narrow mode and
            # the screen reader, so the status is never icon-only)
            painted = (
                stepper.CURRENT
                if i == self.current_index
                else {
                    "ok": stepper.DONE,
                    "attention": stepper.ATTENTION,
                    "error": stepper.ERROR,
                }.get(kind, stepper.PENDING)
            )
            item.setData(stepper.StateRole, painted)
            item.setData(stepper.LabelRole, name)
            item.setData(stepper.NoteRole, str(count) if count else "")
            item.setData(stepper.NumberRole, number)
            item.setToolTip(spoken if meaning else name)

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
        forward_ok = not blocking and page.allow_next
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            enabled = i in self.visited or (
                i > self.current_index and i <= OPTIONS_INDEX and forward_ok
            )
            flags = item.flags()
            item.setFlags(
                flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled
            )
        self._update_sidebar_text()
        self.sidebar.setCurrentRow(self.current_index)
        last = self.current_index >= len(self.pages) - 1
        self.back_button.setEnabled(self.current_index > 0 and page.allow_back)
        running = bool(getattr(page, "running", False))
        for i, extra in self._bar_buttons.items():
            extra.setVisible(running and i == self.current_index)
        self.next_button.setVisible(
            not last and not (running and self.current_index in self._bar_buttons)
        )
        self.quit_button.setVisible(not getattr(page, "running", False))  # Cancel is the page's
        self.next_button.setEnabled(not blocking and page.allow_next)
        label = page.next_label or (
            self.tr("Generate") if self.current_index == OPTIONS_INDEX else self.tr("Next")
        )
        if self.next_button.text() != label:
            self.next_button.setText(label)
            # a new text takes a button's shortcut away: Alt+N is for Next, Generate and
            # Show results alike
            self.next_button.setShortcut("Alt+N")
        inline = {"GUI-INPUT", EMPTY_CODE} if page.shows_inline_errors else set()
        shown = [i for i in errors if i.code not in inline]
        self.problem_label.set_text("\n".join(i.message for i in shown))
        self.problem_label.setVisible(bool(shown))
        self._update_title()
        self.continue_walk()  # a project card's Regenerate is on its way to the Generate page
