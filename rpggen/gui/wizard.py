"""The wizard window: sidebar of pages, stacked page widgets and the Back / Next / Cancel bar."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
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

from rpggen.errors import Issue, Severity
from rpggen.gui import state as state_mod
from rpggen.gui.pages.base import WizardPage, form_error

log = logging.getLogger(__name__)

PAGE_NAMES = ["Project", "Archetype", "Audit", "Mapping", "Options", "Generate", "Results"]
OPTIONS_INDEX = 4  # the last page before generation: its Next button reads "Generate"


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


def default_pages() -> list[WizardPage]:
    pages: list[WizardPage] = [StubPage(name) for name in PAGE_NAMES]
    pages[0].validate = lambda state: (  # type: ignore[method-assign]
        [] if state.pack_sources else [form_error("Add at least one asset pack.")]
    )
    return pages


class MainWindow(QMainWindow):
    def __init__(
        self,
        state: state_mod.WizardState | None = None,
        pages: list[WizardPage] | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle(self.tr("rpggen"))
        self.resize(1100, 720)
        self.state = state or state_mod.WizardState()
        self.pages = pages if pages is not None else default_pages()
        self.visited: set[int] = set()
        self.current_index = -1
        self.issues: list[Issue] = []

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        body = QHBoxLayout()
        outer.addLayout(body, 1)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(170)
        for i, page in enumerate(self.pages):
            name = PAGE_NAMES[i] if i < len(PAGE_NAMES) else page.title
            item = QListWidgetItem(f"{i + 1}. {self.tr(name)}")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.sidebar.addItem(item)
        self.sidebar.itemClicked.connect(self._on_sidebar_clicked)
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        for page in self.pages:
            page.setObjectName(f"page_{page.title.lower()}" if page.title else "page")
            page.changed.connect(self.refresh)
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
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setObjectName("cancelButton")
        bar.addWidget(self.cancel_button)
        bar.addStretch(1)
        bar.addWidget(self.back_button)
        bar.addWidget(self.next_button)
        outer.addLayout(bar)
        self.back_button.clicked.connect(self.go_back)
        self.next_button.clicked.connect(self.go_next)
        self.cancel_button.clicked.connect(self.close)

        if self.pages:
            self.show_page(0)

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
        self._leave_current()
        self.show_page(self.current_index + 1)

    def go_back(self) -> None:
        if self.current_index <= 0:
            return
        self._leave_current()
        self.show_page(self.current_index - 1)

    def _leave_current(self) -> None:
        self.current_page.leave(self.state)
        if self.state.target is not None:
            try:
                state_mod.save_draft(self.state)
            except OSError:
                log.warning("could not save the draft", exc_info=True)

    def _on_sidebar_clicked(self, item: QListWidgetItem) -> None:
        index = self.sidebar.row(item)
        if index in self.visited and index != self.current_index:
            self._leave_current()
            self.show_page(index)

    # ------------------------------------------------------------------ state of the controls

    def refresh(self) -> None:
        """Re-validate the current page and update the sidebar and buttons."""
        if self.current_index < 0:
            return
        page = self.current_page
        self.issues = page.validate(self.state)
        errors = [i for i in self.issues if i.severity is Severity.ERROR]
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
        self.next_button.setEnabled(not errors and page.allow_next)
        label = page.next_label or (
            self.tr("Generate") if self.current_index == OPTIONS_INDEX else self.tr("Next")
        )
        self.next_button.setText(label)
        self.problem_label.setText("\n".join(i.message for i in errors))
        self.problem_label.setVisible(bool(errors))
