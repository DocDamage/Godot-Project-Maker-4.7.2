"""Page 3: audit the detected assets (grid on the left, detail panel on the right)."""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

from PySide6.QtCore import QT_TRANSLATE_NOOP, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from rpggen import ids
from rpggen.core import (
    app_settings,
    contact_sheet,
    labels,
    learned_rules,
    profile_registry,
    profiles,
)
from rpggen.core import catalog as catalog_mod
from rpggen.core import variants as variants_mod
from rpggen.core.analyzer import similarity
from rpggen.core.inventory import Inventory
from rpggen.errors import RpgGenError
from rpggen.gui import edits as edits_mod
from rpggen.gui import icons, theme, workers
from rpggen.gui.dialogs.contact_sheet_dialog import ContactSheetDialog, SheetOptions
from rpggen.gui.dialogs.profile_dialogs import ExportProfileDialog, FindProfileDialog
from rpggen.gui.dialogs.variant_dialog import VariantDialog
from rpggen.gui.edits import EditSession
from rpggen.gui.pages.base import WizardPage
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import analysis_progress
from rpggen.gui.widgets.anim_preview import AnimEditorDialog
from rpggen.gui.widgets.asset_detail import AssetDetail
from rpggen.gui.widgets.asset_grid import AssetGrid, PathResolver, split_folder_key
from rpggen.gui.widgets.bulk_panel import (
    BulkPanel,
    FolderRuleDialog,
    RulesPanel,
    common_folder,
    default_glob,
)
from rpggen.gui.widgets.changes_panel import ChangesPanel
from rpggen.gui.widgets.grid_editor import GridEditorDialog
from rpggen.gui.widgets.object_cutter import ObjectCutterDialog
from rpggen.gui.widgets.pack_info import PackInfoPanel
from rpggen.gui.widgets.review_mode import ReviewMode
from rpggen.gui.widgets.task_progress import error_text, run_task
from rpggen.gui.widgets.terrain_tab import TerrainTab
from rpggen.gui.widgets.tour import Tour, TourStep

log = logging.getLogger(__name__)

TOUR_NAME = "audit"
REVIEW_BAR_WIDTH = 200  # the review progress bar in the page header
TOUR_DELAY_MS = 400  # the page must still be shown then: walking through it starts no tour

QUICK_ROLES = ["GROUND", "WALL", "DECORATION", "BUILDING", "PLAYER", "NPC", "ENEMY", "ITEM", "UI"]


def learn_from_fixes(edits: list[learned_rules.Edit], weight: int) -> None:
    """Record role, usage and collision fixes as evidence for learned rules (T12.59); an undo
    takes it back. The file stays on this computer."""
    try:
        book = learned_rules.load()
        learned_rules.learn(book, edits, weight=weight)
        learned_rules.save(book)
    except OSError:
        log.warning("learned rules could not be saved", exc_info=True)


def make_resolver(state: WizardState) -> PathResolver:
    """Absolute file of an asset: the extracted/opened root of its pack plus the pack-relative
    path (generated assets such as placeholders have no file here)."""
    roots = {p.pack_id: Path(p.root) for p in state.opened_packs}
    generated_root = Path(state.target) / ".rpggen_staging" if state.target else None

    def resolve(asset: catalog_mod.Asset) -> Path | None:
        parts = asset.path.split("/", 3)
        if len(parts) == 4 and parts[:2] == ["assets", "packs"] and asset.pack_id in roots:
            return roots[asset.pack_id] / parts[3]
        if asset.path.startswith(variants_mod.VARIANT_DIR + "/"):  # rendered into the cache
            cached = variants_mod.cached_file(asset.sha256)
            if cached.is_file():
                return cached
        if generated_root is not None:
            candidate = generated_root / asset.path
            return candidate if candidate.exists() else None
        return None

    return resolve


class AuditPage(WizardPage):
    focus_next = Signal()  # everything that needed attention is done: the window may focus Next

    title = "Audit"
    purpose = str(
        QT_TRANSLATE_NOOP(
            "WizardPage",
            "Check what rpggen found in your packs. Confirm what is right, fix what is not.",
        )
    )
    help_anchor = "3. Using a pack you bought"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._done_announced = False
        self.session: EditSession | None = None
        self.tour: Tour | None = None
        self.resolver: PathResolver = lambda asset: None
        layout = self.page_layout()
        self.state: WizardState | None = None
        # the progress of the review: "328 of 340 reviewed - 12 need attention"
        # ... in the header's slot (T15.06, T15.12), with its bar and the Review mode button
        review_box = QVBoxLayout()
        review_box.setContentsMargins(0, 0, 0, 0)
        review_box.setSpacing(theme.px("space_4"))
        self.progress_label = QLabel()
        self.progress_label.setObjectName("reviewProgressLabel")
        self.progress_label.setProperty("role", "caption")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("reviewProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(REVIEW_BAR_WIDTH)
        self.progress_bar.setToolTip(self.tr("How much of the pack you have looked at"))
        review_box.addWidget(self.progress_label)
        review_box.addWidget(self.progress_bar, 0, Qt.AlignmentFlag.AlignRight)
        review_holder = QWidget()
        review_holder.setObjectName("reviewProgressBox")
        review_holder.setLayout(review_box)
        # what the last command did to the selection: "9 similar assets selected" (T13.04)
        self.selection_note = QLabel()
        self.selection_note.setObjectName("selectionNote")
        self.selection_note.setProperty("role", "caption")
        self.similar_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.similar_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.similar_shortcut.activated.connect(self.select_similar)
        self.review_button = QPushButton(self.tr("Review mode"))
        self.review_button.setObjectName("reviewModeButton")
        self.review_button.setCheckable(True)
        self.review_button.setToolTip(
            self.tr("One asset at a time with a large preview (F7). The keys stay the same.")
        )
        self.review_button.clicked.connect(lambda on: self.set_review_mode(bool(on)))
        icons.set_icon(self.review_button, "eye")
        self.header.add_widget(self.selection_note)
        self.header.add_widget(review_holder)
        self.header.add_widget(self.review_button)
        self.done_label = QLabel()
        self.done_label.setObjectName("reviewDoneLabel")
        self.done_label.setProperty("state", "ok")
        self.done_label.setWordWrap(True)
        self.done_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.done_label.setVisible(False)
        layout.addWidget(self.done_label)
        self.profile_button = QToolButton()
        self.profile_button.setObjectName("profileButton")
        self.profile_button.setText(self.tr("Profile"))
        self.profile_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        profile_menu = QMenu(self.profile_button)
        self.export_action = profile_menu.addAction(self.tr("Export pack profile…"))
        self.export_action.setObjectName("exportProfileAction")
        self.import_action = profile_menu.addAction(self.tr("Import profile…"))
        self.import_action.setObjectName("importProfileAction")
        self.online_action = profile_menu.addAction(self.tr("Find profile online…"))
        self.online_action.setObjectName("findProfileAction")
        profile_menu.addSeparator()
        self.sheet_action = profile_menu.addAction(self.tr("Export contact sheet…"))
        self.sheet_action.setObjectName("contactSheetAction")
        self.profile_button.setMenu(profile_menu)
        self.profile_button.setToolTip(self.tr("Export, import or look online for a pack profile"))
        self.profile_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        icons.set_icon(self.profile_button, "settings")
        self.export_action.triggered.connect(lambda: self.export_profile())
        self.import_action.triggered.connect(lambda: self.import_profile())
        self.online_action.triggered.connect(lambda: self.find_profile_online())
        self.sheet_action.triggered.connect(lambda: self.export_contact_sheet())
        self.quick_roles = list(app_settings.get().quick_roles) or list(QUICK_ROLES)
        self.archetype = "turn_based"
        self.grid = AssetGrid()
        self.tabs = QTabWidget()
        self.tabs.setObjectName("auditTabs")
        self.tabs.addTab(self.grid, self.tr("Assets"))
        # at the end of the filter row (T15.12): the tab strip has no corner widget to clip
        self.grid.add_filter_widget(self.profile_button)
        self.rules_panel: RulesPanel | None = None
        self.terrain_tab: TerrainTab | None = None
        self.packs_panel: PackInfoPanel | None = None
        self.changes_panel: ChangesPanel | None = None
        self.changes_index = -1
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("auditSplitter")
        self.splitter.addWidget(self.tabs)
        self.side = QStackedWidget()
        self.side.setObjectName("auditSide")
        self.empty_label = QLabel(
            self.tr("Select an asset to see and correct what rpggen detected.")
        )
        self.empty_label.setObjectName("emptySelectionLabel")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.side.addWidget(self.empty_label)
        self.detail: AssetDetail | None = None
        self.splitter.addWidget(self.side)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        # the body: the grid with its side panel, or review mode (T13.01)
        self.review = ReviewMode()
        self.review.quickKey.connect(self._on_quick_key)
        self.review.leaveRequested.connect(lambda: self.set_review_mode(False))
        self.body = QStackedWidget()
        self.body.setObjectName("auditBody")
        self.body.addWidget(self.splitter)
        self.body.addWidget(self.review)
        layout.addWidget(self.body, 1)  # the grid takes the spare height, not the labels
        saved_sizes = app_settings.get().splitters.get("audit")
        if saved_sizes and len(saved_sizes) == 2 and all(s > 0 for s in saved_sizes):
            self.splitter.setSizes(saved_sizes)
        self.splitter.splitterMoved.connect(self._save_splitter)
        self.bulk: BulkPanel | None = None
        self.grid.selectionChanged.connect(self._on_selection)
        view = self.grid.view
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(self._on_context_menu)
        view.quickKey.connect(self._on_quick_key)
        self.grid.confirmAutoRequested.connect(self.confirm_all_auto)
        self.grid.shortcutsRequested.connect(self.show_shortcuts)
        self.grid.thumbSizeChanged.connect(self._remember_thumb_size)
        self.grid.set_thumb_size(app_settings.get().thumb_size)
        self.grid.set_grouped(app_settings.get().group_by_folder)
        self.grid.groupedChanged.connect(lambda on: app_settings.schedule(group_by_folder=on))
        self.grid.folderConfirmRequested.connect(self.confirm_folder)
        self.grid.folderRuleRequested.connect(self.make_folder_rule)

    def set_thumb_size(self, size: int) -> None:
        """Called by the View menu."""
        self.grid.set_thumb_size(size)

    def _remember_thumb_size(self, size: int) -> None:
        app_settings.schedule(thumb_size=size)

    # ------------------------------------------------------------------ progress and queue

    def update_progress(self) -> None:
        if self.session is None:
            return
        done, attention, total = catalog_mod.review_progress(self.session.catalog)
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)
        self.progress_label.setText(
            self.tr("{0} of {1} reviewed - {2} need attention").format(done, total, attention)
        )
        finished = total > 0 and attention == 0
        self.done_label.setVisible(finished)
        self.grid.set_queue_text(self.review_counter())
        self.done_label.setText(
            self.tr(
                "Everything that needed attention is done. Auto-detected assets can be left as "
                "they are."
            )
        )
        if finished and not self._done_announced:
            self._done_announced = True
            self.focus_next.emit()
        if not finished:
            self._done_announced = False

    def confirm_all_auto(self) -> bool:
        """Confirms every auto-detected asset as one undo step."""
        if self.session is None:
            return False
        ids = [a.id for a in self.session.catalog.assets if a.status == "AUTO_DETECTED"]
        return bool(ids) and self.session.confirm(ids)

    def confirm_folder(self, key: str) -> bool:
        """A folder header's Confirm all: the folder's assets that pass the filter and are not
        confirmed yet, as one undo step."""
        if self.session is None:
            return False
        wanted = set(self.grid.folder_ids(key))
        ids = [
            a.id for a in self.session.catalog.assets if a.id in wanted and a.status != "CONFIRMED"
        ]
        return bool(ids) and self.session.confirm(ids)

    def make_folder_rule(self, key: str) -> bool:
        """A folder header's Make rule…: the rule dialog with the folder's glob filled in."""
        if self.session is None:
            return False
        pack_id, folder = split_folder_key(key)
        dialog = FolderRuleDialog(
            [p.pack_id for p in self.session.catalog.packs], pack_id, default_glob(folder), {}, self
        )
        if not self.run_rule_dialog(dialog):
            return False
        return self.session.add_rule(dialog.rule())

    def shortcut_sheet(self) -> str:
        roles = "\n".join(
            f"  {i + 1}  {labels.role_label(r)}" for i, r in enumerate(self.quick_roles[:9])
        )
        return self.tr(
            "C  confirm the selected assets (then go to the next one that needs attention)\n"
            "X  exclude the selected assets (likewise)\n"
            "N / Shift+N  next / previous asset that needs attention\n"
            "Ctrl+Shift+S  select the assets that look like the selected one\n"
            "F7  review mode: one asset at a time with a large preview (Esc leaves it)\n"
            "1-9  give the selected assets a role:\n{0}\n"
            "Ctrl+Z / Ctrl+Y  undo / redo\n"
            "Ctrl + mouse wheel  zoom the preview"
        ).format(roles)

    def show_shortcuts(self) -> None:
        QMessageBox.information(self, self.tr("Shortcuts of the audit"), self.shortcut_sheet())

    def _save_splitter(self, *_args: object) -> None:
        sizes = self.splitter.sizes()
        app_settings.schedule(splitters={**app_settings.get().splitters, "audit": sizes})

    def _fit_side(self) -> None:
        """Until the user places the splitter, the detail panel gets the width its content needs
        (no sideways scrolling), up to 55% of the page (a long path must not take the grid's
        room) and as far as the grid's own minimum allows."""
        if self.detail is None or app_settings.get().splitters.get("audit"):
            return
        grid_width, side_width = self.splitter.sizes()
        total = grid_width + side_width
        bar = self.detail_scroll.verticalScrollBar().sizeHint().width()
        wanted = self.detail.minimumSizeHint().width() + bar
        wanted = min(wanted, total * 55 // 100, total - self.tabs.minimumSizeHint().width())
        if wanted > side_width:
            self.splitter.setSizes([total - wanted, wanted])

    def _on_quick_key(self, key: str) -> None:
        if key == "C":
            self._confirm_selection()
        elif key == "X":
            self._exclude_selection()
        elif key == "N":
            self._step(True)
        elif key == "SHIFT+N":
            self._step(False)
        else:
            self._quick_role(int(key))

    def _step(self, forward: bool) -> None:
        """N and Shift+N: the next asset that needs attention. In review mode, once nothing
        needs attention, they walk the assets the filter shows instead."""
        if self.grid.select_next_attention(forward) is not None or not self.in_review_mode:
            return
        order = self.grid.visible_ids()
        if not order:
            return
        current = self.grid.selected_ids()
        position = order.index(current[0]) if current and current[0] in order else -1
        target = order[(position + (1 if forward else -1)) % len(order)]
        self.grid.select_ids([target])
        self.grid.scroll_to(target)

    # ------------------------------------------------------------------ review mode (T13.01)

    @property
    def in_review_mode(self) -> bool:
        return self.body.currentWidget() is self.review

    def toggle_review_mode(self) -> None:
        """View > Review mode (F7)."""
        self.set_review_mode(not self.in_review_mode)

    def set_review_mode(self, on: bool) -> bool:
        """Show one asset at a time, or go back to the grid. The grid's selection is the asset
        shown in both, so entering and leaving change nothing but the view."""
        self.review_button.setChecked(on and self.detail is not None)
        if self.detail is None or on == self.in_review_mode:
            return self.in_review_mode
        if on:
            self.tabs.setCurrentWidget(self.grid)
            queue = self.grid.attention_ids()
            selected = self.grid.selected_ids()
            if queue and (len(selected) != 1 or selected[0] not in queue):
                self.grid.select_ids([queue[0]])
            elif not queue and len(selected) != 1:
                self.grid.select_ids(self.grid.visible_ids()[:1])
            self.detail.stop_animation()
            self.detail.show_preview = False
            self.detail.extra_view = self.review.preview  # the picture and the playback go there
            self.review.side.addWidget(self.detail_scroll)  # the same panel, moved
            # a third of the page, or what the form needs when that is more (at most half)
            bar = self.detail_scroll.verticalScrollBar().sizeHint().width()
            needs = self.detail.minimumSizeHint().width() + bar
            self.detail_scroll.setMinimumWidth(min(needs, self.width() // 2))
            self.detail_scroll.show()
            self.body.setCurrentWidget(self.review)
            self._show_in_review()
            self.review.setFocus()
        else:
            self.detail.stop_animation()
            self.detail.show_preview = True
            self.detail.extra_view = None
            self.detail_scroll.setMinimumWidth(0)
            self.side.addWidget(self.detail_scroll)
            self.body.setCurrentWidget(self.splitter)
            selected = self.grid.selected_ids()
            self._on_selection(selected)
            self.detail.reload(reload_image=True)
            if selected:
                self.grid.scroll_to(selected[0])
            self.grid.view.setFocus()
        return self.in_review_mode

    def review_counter(self) -> str:
        """ "12 of 37 need attention", or the place in the filter once nothing does."""
        queue = self.grid.attention_ids()
        selected = self.grid.selected_ids()
        current = selected[0] if len(selected) == 1 else None
        if queue:
            if current in queue:
                return self.tr("{0} of {1} need attention").format(
                    queue.index(current) + 1, len(queue)
                )
            return self.tr("{0} need attention").format(len(queue))
        order = self.grid.visible_ids()
        if current in order:
            return self.tr("Nothing needs attention · {0} of {1} shown").format(
                order.index(current) + 1, len(order)
            )
        return self.tr("Nothing needs attention")

    def _show_in_review(self) -> None:
        """The selected asset in the large preview, with the grid its usage has."""
        assert self.detail is not None
        self.review.set_counter(self.review_counter())
        asset = self.detail.asset()
        if asset is None:
            self.review.show_note(False, self.tr("Nothing to review with this filter."))
            return
        path = self.resolver(asset) if asset.kind == "image" else None
        eff = catalog_mod.effective(asset)
        note = labels.role_label(str(eff.get("role", ""))) or asset.kind
        self.review.show_note(path is not None, f"{asset.path.rsplit('/', 1)[-1]}\n{note}")
        self.detail.reload(reload_image=False)  # its own picture is off in this mode
        if not self.detail.player.playing:
            self.detail.render_picture()  # into the large view: the panel's own picture is off here

    def _advance(self, order_before: list[str], edited: list[str]) -> None:
        """Review flow: after a single asset was confirmed or excluded, select the next one that
        needs attention, so a review is "look, press C, look, press C"."""
        if len(edited) == 1:
            self.grid.advance_after(order_before, edited[0])

    def _confirm_selection(self) -> None:
        ids = self.grid.selected_ids()
        if ids and self.session is not None:
            order = self.grid.visible_ids()
            if self.session.confirm(ids):
                self._advance(order, ids)

    def _exclude_selection(self) -> None:
        ids = self.grid.selected_ids()
        if ids and self.session is not None:
            order = self.grid.visible_ids()
            if self.session.bulk_edit(ids, {"role": "NONE"}):
                self._advance(order, ids)

    def _quick_role(self, number: int) -> None:
        ids = self.grid.selected_ids()
        if ids and self.session is not None and number <= len(self.quick_roles):
            self.session.bulk_edit(ids, {"role": self.quick_roles[number - 1]})

    # ------------------------------------------------------------------ session wiring

    @staticmethod
    def _scrolled(panel: QWidget) -> QScrollArea:
        """The side panels scroll when the window is too short for them (the 540 px minimum)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _on_changes_counted(self, count: int) -> None:
        self.tabs.setTabText(self.changes_index, self.tr("Changes ({0})").format(count))

    def show_asset(self, asset_id: str) -> None:
        """Select an asset in the grid (the Changes tab's double-click): back on the Assets tab,
        with the filters that would hide it put aside."""
        self.tabs.setCurrentWidget(self.grid)
        if asset_id not in self.grid.visible_ids():
            self.grid.chips["chipAll"].click()
        self.grid.select_ids([asset_id])
        self.grid.scroll_to(asset_id)

    def show_assets(self, asset_ids: set[str]) -> None:
        """Filter the grid to these assets (the ones the results named)."""
        self.grid.show_ids(asset_ids)

    def status(self, state: WizardState) -> tuple[str, int]:
        """How many assets still need attention (a warning, never a block)."""
        if state.catalog is None:
            return ("none", 0)
        _done, attention, _total = catalog_mod.review_progress(state.catalog)
        return ("attention", attention) if attention else ("ok", 0)

    def _ensure_session(self, state: WizardState) -> EditSession:
        assert state.catalog is not None
        if self.session is None:
            self.session = EditSession(state.catalog, self)
            self.session.learner = learn_from_fixes
            self.detail = AssetDetail(self.session)
            self.detail_scroll = self._scrolled(self.detail)
            self.side.addWidget(self.detail_scroll)
            self.detail.gridEditRequested.connect(self.edit_grid)
            self.detail.animationsRequested.connect(self.edit_animations)
            self.detail.cutObjectsRequested.connect(self.cut_objects)
            self.bulk = BulkPanel(self.session)
            self.bulk_scroll = self._scrolled(self.bulk)
            self.side.addWidget(self.bulk_scroll)
            self.rules_panel = RulesPanel(self.session)
            self.tabs.addTab(self.rules_panel, self.tr("Rules"))
            self.terrain_tab = TerrainTab(self.session)
            self.terrain_tab.changed.connect(self.changed.emit)
            self.tabs.addTab(self.terrain_tab, self.tr("Terrain"))
            self.packs_panel = PackInfoPanel(self.session)
            self.tabs.addTab(self._scrolled(self.packs_panel), self.tr("Packs"))
            self.changes_panel = ChangesPanel(self.session)
            self.changes_index = self.tabs.addTab(self.changes_panel, self.tr("Changes (0)"))
            self.changes_panel.countChanged.connect(self._on_changes_counted)
            self.changes_panel.assetActivated.connect(self.show_asset)
            self._on_changes_counted(self.changes_panel.count())
            self.session.changed.connect(self._on_catalog_changed)
            undo = self.session.undo_stack.createUndoAction(self, self.tr("Undo"))
            redo = self.session.undo_stack.createRedoAction(self, self.tr("Redo"))
            undo.setShortcut(QKeySequence.StandardKey.Undo)
            redo.setShortcuts([QKeySequence(QKeySequence.StandardKey.Redo), QKeySequence("Ctrl+Y")])
            for action in (undo, redo):
                action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                self.addAction(action)
            self.undo_action, self.redo_action = undo, redo
        elif self.session.catalog is not state.catalog:
            self.session.reset(state.catalog)
        return self.session

    def enter(self, state: WizardState) -> None:
        if state.catalog is None:
            return
        self.state = state
        self.archetype = state.archetype
        session = self._ensure_session(state)
        self.resolver = make_resolver(state)
        assert self.detail is not None
        self.detail.resolver = self.resolver
        if self.terrain_tab is not None:
            self.terrain_tab.resolver = self.resolver
            self.terrain_tab.refresh()
        self.grid.set_catalog(session.catalog, self.resolver)
        changed = {a.id for a in session.catalog.assets if a.path in state.changed_paths}
        self.grid.set_changed(changed)
        self.update_progress()
        if TOUR_NAME not in app_settings.get().tours_seen:
            # not at once: "Try the sample" passes through this page on its way to the options
            QTimer.singleShot(TOUR_DELAY_MS, self.maybe_start_tour)

    # ------------------------------------------------------------------ the tour (T13.09)

    def tour_steps(self) -> list[TourStep]:
        """What the tour points at, in order: the cards, the queue, the panel, the keys, the
        profile menu."""
        return [
            TourStep(
                self.grid.view,
                self.tr("What rpggen detected"),
                self.tr(
                    "Every file of your packs is a card. The coloured edge and the glyph in the "
                    "corner say how sure rpggen is: ✔ green is confirmed, · blue was detected "
                    "with confidence, ? orange and ! red want a look from you, – grey is unused."
                ),
            ),
            TourStep(
                self.progress_label,
                self.tr("The queue"),
                self.tr(
                    "This line counts what is left. You only need to look at the assets that "
                    "need attention; the chips below filter the grid, and Review mode shows them "
                    "one at a time."
                ),
            ),
            TourStep(
                self.side,
                self.tr("The detail panel"),
                self.tr(
                    "Select a card to see why rpggen chose its role, and to correct the usage, "
                    "the role, the grid or the animations. Every change can be undone."
                ),
            ),
            TourStep(
                self.grid.help_button,
                self.tr("The keys"),
                self.tr(
                    "C confirms, X excludes, 1 to 9 give a role and N goes to the next asset "
                    "that needs attention. This button lists them all."
                ),
            ),
            TourStep(
                self.profile_button,
                self.tr("Profiles"),
                self.tr(
                    "When the audit is done you can save it as a profile: the next release of "
                    "the pack, or a friend with the same pack, starts from your decisions."
                ),
            ),
        ]

    def maybe_start_tour(self) -> bool:
        """The first time the page is really shown (with packs of your own or the sample's
        audit): start the tour. Never again once it was finished or skipped."""
        if TOUR_NAME in app_settings.get().tours_seen or not self.isVisible():
            return False
        if self.session is None or (self.tour is not None and self.tour.running):
            return False
        return self.start_tour()

    def start_tour(self) -> bool:
        """Start the tour now (Help > Show the tour again does, on this page)."""
        self.end_tour()
        self.set_review_mode(False)
        self.tabs.setCurrentWidget(self.grid)
        self.tour = Tour(self, self.tour_steps(), TOUR_NAME)
        self.tour.finished.connect(self._on_tour_finished)
        return self.tour.start()

    def end_tour(self) -> None:
        """Take a running tour away without calling it seen (the page was left)."""
        if self.tour is not None:
            self.tour.finished.disconnect(self._on_tour_finished)
            self.tour.hide()
            self.tour.deleteLater()
            self.tour = None

    def hideEvent(self, event) -> None:  # noqa: ANN001, N802
        self.end_tour()  # however the page was left: the tour belongs to the page being shown
        super().hideEvent(event)

    def _on_tour_finished(self, _skipped: bool) -> None:
        def seen(settings: app_settings.AppSettings) -> None:
            settings.tours_seen = sorted({*settings.tours_seen, TOUR_NAME})

        app_settings.store().update(seen)
        self.grid.view.setFocus()

    def leave(self, state: WizardState) -> bool | None:
        self.end_tour()
        self.set_review_mode(False)
        if self.detail is not None:
            self.detail.stop_animation()
        if self.session is not None:
            state.catalog = self.session.catalog
        return None

    # ------------------------------------------------------------------ reacting

    def _on_catalog_changed(self, ids: list[str]) -> None:
        assert self.session is not None
        self.grid.model.catalog = self.session.catalog
        self.grid.model.refresh(ids or None)
        self.grid._update_counts()
        self.update_progress()
        if self.in_review_mode:
            self._show_in_review()  # an edit may change the grid drawn over the picture
        self.changed.emit()

    def _on_selection(self, ids: list[str]) -> None:
        self.grid.set_queue_text(self.review_counter())  # the footer under the grid
        if self.detail is None:
            return
        if self.in_review_mode:  # the panel is in the review widget; one asset at a time
            self.detail.set_asset(ids[0] if len(ids) == 1 else None)
            self._show_in_review()
            return
        if len(ids) == 1:
            self.detail.set_asset(ids[0])
            self.side.setCurrentWidget(self.detail_scroll)
            self._fit_side()
        elif len(ids) > 1 and self.bulk is not None:
            self.detail.set_asset(None)
            self.bulk.set_assets(ids)
            self.side.setCurrentWidget(self.bulk_scroll)
        else:
            self.detail.set_asset(None)
            self.side.setCurrentWidget(self.empty_label)

    # ------------------------------------------------------------------ dialogs

    def run_dialog(self, dialog) -> bool:  # noqa: ANN001 - overridden by tests
        return bool(dialog.exec())

    def edit_grid(self, asset_id: str) -> bool:
        """Open the grid editor; Apply writes a ``grid`` override."""
        assert self.session is not None
        asset = self.session.catalog.asset(asset_id)
        path = self.resolver(asset) if asset else None
        if asset is None or path is None:
            return False
        grid = catalog_mod.effective(asset).get("grid")
        dialog = GridEditorDialog(path, grid, asset.path, self)
        if not self.run_dialog(dialog):
            return False
        return self.session.set_override(asset_id, "grid", dialog.grid())

    def edit_animations(self, asset_id: str) -> bool:
        """Open the animation editor; Apply writes ``animations``/``origin``/``frame``."""
        assert self.session is not None
        asset = self.session.catalog.asset(asset_id)
        path = self.resolver(asset) if asset else None
        if asset is None or path is None:
            return False
        eff = catalog_mod.effective(asset)
        grid = eff.get("grid")
        frame = tuple(eff.get("frame") or (grid["cell"] if grid else (16, 16)))

        def sheet_for(source: str) -> Path | None:
            return self.resolver(dataclasses.replace(asset, path=source))

        dialog = AnimEditorDialog(
            path,
            eff.get("animations") or {},
            frame,
            tuple(eff["origin"]) if eff.get("origin") else None,
            grid,
            arpg=self.archetype == "arpg",
            sheet_resolver=sheet_for,
            parent=self,
        )
        if not self.run_dialog(dialog):
            return False
        values = dialog.overrides()
        if not values:
            return False
        return self.session.set_overrides([asset_id], values, "Edit animations")

    def cut_objects(self, asset_id: str) -> bool:
        """Open the object cutter for a sheet; Apply replaces the sheet's objects."""
        assert self.session is not None
        catalog = self.session.catalog
        asset = catalog.asset(asset_id)
        path = self.resolver(asset) if asset else None
        if asset is None or path is None:
            return False
        dialog = ObjectCutterDialog(
            path,
            asset_id,
            [o for o in catalog.objects if o.sheet == asset_id],
            catalog_mod.effective(asset).get("grid"),
            {o.id for o in catalog.objects},
            self,
        )
        if not self.run_dialog(dialog):
            return False
        return self.session.set_sheet_objects(asset_id, dialog.result_objects())

    # ------------------------------------------------------------------ pack profiles

    def choose_save_path(self, default_name: str) -> Path | None:  # overridden by tests
        name, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export pack profile"),
            default_name,
            self.tr("Pack profiles (*.rpgprofile.json)"),
        )
        return Path(name) if name else None

    def choose_open_path(self) -> Path | None:  # overridden by tests
        name, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import profile"),
            "",
            self.tr("Pack profiles (*.rpgprofile.json);;JSON (*.json)"),
        )
        return Path(name) if name else None

    def show_error(self, title: str, message: str) -> None:  # overridden by tests
        QMessageBox.warning(self, title, message)

    def run_analysis(self, state: WizardState) -> bool:  # overridden by tests
        return analysis_progress.run_analysis(self, state)

    def add_folder_rules(self, rules: list[dict]) -> int:
        """Add folder rules (``{pack_id, glob, set}``, e.g. learned rules) as one undo step;
        returns how many were added."""
        if self.session is None or not rules:
            return 0

        def change(catalog: catalog_mod.Catalog) -> catalog_mod.Catalog:
            for rule in rules:
                catalog = edits_mod.add_folder_rule(catalog, catalog_mod.FolderRule.from_json(rule))
            return catalog

        return len(rules) if self.session.apply(self.tr("Add folder rules"), change) else 0

    # ------------------------------------------------------------------ contact sheet (T12.57)

    def ask_sheet_options(self, shown: int, total: int) -> SheetOptions | None:  # tests override
        dialog = ContactSheetDialog(shown, total, self)
        return dialog.options() if dialog.exec() == QDialog.DialogCode.Accepted else None

    def ask_sheet_path(self, fmt: str) -> Path | None:  # tests override
        state = self.state
        start = Path(state.target).parent if state and state.target else Path.home()
        name = "contact_sheet.pdf" if fmt == "pdf" else "contact_sheet.png"
        pattern = self.tr("PDF (*.pdf)") if fmt == "pdf" else self.tr("PNG images (*.png)")
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export contact sheet"), str(start / name), pattern
        )
        return Path(path) if path else None

    def export_contact_sheet(self) -> list[Path]:
        """The assets shown (as filtered) or all of them on A4 or Letter pages, as a PDF or
        PNGs, drawn in a worker. Returns the files written."""
        if self.session is None:
            return []
        shown_ids = self.grid.visible_ids()
        total = len(self.session.catalog.assets)
        options = self.ask_sheet_options(len(shown_ids), total)
        if options is None:
            return []
        out = self.ask_sheet_path(options.fmt)
        if out is None:
            return []
        entries = contact_sheet.entries_for(
            self.session.catalog, self.resolver, shown_ids if options.filtered else None
        )
        title = self.state.config.project_name if self.state and self.state.config else ""

        def job(*, callbacks: workers.Callbacks) -> list[Path]:
            return contact_sheet.export(
                entries,
                out,
                options.fmt,
                options.paper,
                options.grid_overlay,
                title,
                is_cancelled=callbacks.is_cancelled,
                progress=lambda done, n: callbacks.on_phase(
                    self.tr("Drawing the contact sheet…"), done, n
                ),
            )

        outcome = run_task(
            self,
            self.tr("Drawing the contact sheet…"),
            job,
            object_name="contactSheetProgress",
            determinate=True,
        )
        if not outcome.ok:
            if outcome.error is not None:
                QMessageBox.warning(
                    self, self.tr("Export contact sheet"), error_text(outcome.error)
                )
            return []
        files: list[Path] = list(outcome.value or [])
        self.say_sheet_written(files)
        return files

    def say_sheet_written(self, files: list[Path]) -> None:  # tests override
        if files:
            QMessageBox.information(
                self,
                self.tr("Export contact sheet"),
                self.tr("Written: {0}").format(", ".join(str(f) for f in files[:3]))
                + (self.tr(" and {0} more").format(len(files) - 3) if len(files) > 3 else ""),
            )

    def export_profile(self) -> Path | None:
        """Ask for the profile's details and a file, then write the profile of one pack."""
        state = self.state
        if self.session is None or state is None or not state.inventories:
            return None
        catalog = self.session.catalog
        pack_ids = [inv.pack_id for inv in state.inventories]
        dialog = ExportProfileDialog(pack_ids, pack_ids[0], self)
        if not self.run_dialog(dialog):
            return None
        pack_id = dialog.pack_id() or pack_ids[0]
        inventory = next(inv for inv in state.inventories if inv.pack_id == pack_id)
        meta = dialog.meta()
        path = self.choose_save_path(f"{ids.slug(meta['title'])}{profiles.PROFILE_SUFFIX}")
        if path is None:
            return None
        try:
            data = profiles.export_profile(catalog, pack_id, inventory, meta)
            profiles.write_profile(data, path)
        except (RpgGenError, OSError) as exc:
            self.show_error(self.tr("Could not export the profile"), str(exc))
            return None
        return path

    def registry_message(self, error: object) -> str:
        """Plain words for the three ways the lookup can fail."""
        if isinstance(error, (profile_registry.RegistryOffline, OSError)):
            return self.tr(
                "No connection to the profile registry. Check your network and try again.\n\n"
                "Details: {0}"
            ).format(error_text(error))
        return self.tr("The registry returned something unusable: {0}").format(error_text(error))

    def fetch_registry(self, inventories: list[Inventory]) -> list[profile_registry.Candidate]:
        """Download the registry index and match it (overridden by tests). Network only here."""
        return profile_registry.candidates(profile_registry.fetch_index(), inventories)

    def download_registry_profile(self, profile_id: str) -> None:  # overridden by tests
        profile_registry.download_profile(profile_id)

    def find_profile_online(self) -> bool:
        """The user-initiated network call: list matching community profiles, install the one
        the user picks, then analyze again (the user's edits are kept). True when installed."""
        state = self.state
        if state is None or self.session is None or not state.inventories:
            return False
        outcome = run_task(
            self,
            self.tr("Looking for matching profiles…"),
            workers.fetch_registry,
            state.inventories,
            fetch=self.fetch_registry,
            object_name="registryProgress",
        )
        if outcome.cancelled:
            return False
        if outcome.error is not None:
            self.show_error(
                self.tr("Could not reach the profile registry"),
                self.registry_message(outcome.error),
            )
            return False
        found = outcome.value
        if not found:
            self.show_error(
                self.tr("Find profile online"),
                self.tr("No community profile matches your packs yet."),
            )
            return False
        dialog = FindProfileDialog(found, self)
        if not self.run_dialog(dialog):
            return False
        chosen = dialog.selected()
        if chosen is None:
            return False
        outcome = run_task(
            self,
            self.tr("Downloading the profile…"),
            workers.download_profile,
            chosen.profile_id,
            download=self.download_registry_profile,
            object_name="registryProgress",
        )
        if outcome.cancelled:
            return False
        if outcome.error is not None:
            self.show_error(self.tr("Could not install the profile"), error_text(outcome.error))
            return False
        state.catalog = self.session.catalog
        if not self.run_analysis(state):
            return False
        self.enter(state)
        self.changed.emit()
        return True

    def import_profile(self) -> bool:
        """Install a profile file and analyze the packs again; the user's edits are kept."""
        state = self.state
        if state is None or self.session is None:
            return False
        path = self.choose_open_path()
        if path is None:
            return False
        try:
            profile = profiles.install_profile(path)
        except (RpgGenError, OSError, ValueError) as exc:
            self.show_error(self.tr("Could not import the profile"), str(exc))
            return False
        state.catalog = self.session.catalog  # re-assembly builds on the current edits
        if not self.run_analysis(state):
            return False
        self.enter(state)
        self.changed.emit()
        return bool(profile)

    # ------------------------------------------------------------------ folder rules

    def _on_context_menu(self, pos: QPoint) -> None:
        if not self.grid.selected_ids():
            return
        menu = QMenu(self)
        action = menu.addAction(self.tr("Make rule for this folder…"))
        action.setObjectName("makeRuleAction")
        action.triggered.connect(self.make_rule)
        similar = menu.addAction(self.tr("Select similar"))
        similar.setObjectName("selectSimilarAction")
        similar.setShortcut(QKeySequence("Ctrl+Shift+S"))
        similar.setEnabled(self.can_select_similar())
        similar.triggered.connect(self.select_similar)
        variant = menu.addAction(self.tr("Make variant…"))
        variant.setObjectName("makeVariantAction")
        variant.setEnabled(self.can_make_variant())
        variant.triggered.connect(self.make_variant)
        if self.selected_variant() is not None:
            remove = menu.addAction(self.tr("Remove variant"))
            remove.setObjectName("removeVariantAction")
            remove.triggered.connect(self.remove_variant)
        menu.exec(self.grid.view.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------ recolour variants (T13.18)

    def _one_selected(self) -> catalog_mod.Asset | None:
        ids = self.grid.selected_ids()
        return self.session.catalog.asset(ids[0]) if self.session and len(ids) == 1 else None

    def can_make_variant(self) -> bool:
        """One sprite, object or tile picture of a pack is selected (not a variant itself)."""
        asset = self._one_selected()
        return (
            asset is not None
            and asset.kind == "image"
            and asset.status != "MISSING"
            and not variants_mod.is_variant(asset)
            and self.grid.model.resolver(asset) is not None
        )

    def selected_variant(self) -> str | None:
        asset = self._one_selected()
        return asset.id if asset is not None and variants_mod.is_variant(asset) else None

    def run_variant_dialog(self, dialog: VariantDialog) -> bool:  # overridden by tests
        return bool(dialog.exec())

    def make_variant(self) -> str | None:
        """Ask for the recolour, then add the variant as one undo step. Returns its id."""
        asset = self._one_selected()
        if asset is None or not self.can_make_variant() or self.state is None:
            return None
        file = self.grid.model.resolver(asset)
        assert file is not None and self.session is not None
        dialog = VariantDialog(self.session.catalog, asset, Path(file), self)
        if not self.run_variant_dialog(dialog):
            return None
        definition = dialog.definition()
        roots = {p.pack_id: Path(p.root) for p in self.state.opened_packs}
        if not self.session.add_variant(definition, roots):
            return None
        self.grid.select_ids([definition["id"]])
        return str(definition["id"])

    def remove_variant(self) -> bool:
        variant_id = self.selected_variant()
        return (
            variant_id is not None
            and self.session is not None
            and (self.session.remove_variant(variant_id))
        )

    def can_select_similar(self) -> bool:
        """One image is selected (a sound or a font has no picture to compare)."""
        ids = self.grid.selected_ids()
        asset = self.session.catalog.asset(ids[0]) if self.session and len(ids) == 1 else None
        return asset is not None and asset.kind == "image"

    def select_similar(self) -> list[str]:
        """Select the assets that look like the selected one (and keep it selected), so the
        bulk panel applies to all of them. Returns the similar ones, nearest first."""
        if not self.can_select_similar() or self.session is None:
            return []
        origin = self.grid.selected_ids()[0]
        found = [i for i, _d in similarity.near(self.session.catalog, origin)]
        if found and not set(found) <= set(self.grid.visible_ids()):
            self.grid.chips["chipAll"].click()  # the filter hid some of them
        shown = set(self.grid.visible_ids())
        found = [i for i in found if i in shown]
        if found:
            self.grid.select_ids([origin, *found])
        self.selection_note.setText(
            self.tr("{0} similar assets selected").format(len(found))
            if found
            else self.tr("No similar assets found")
        )
        return found

    def make_rule(self) -> bool:
        """Open the rule dialog for the selection; True when a rule was added."""
        ids = self.grid.selected_ids()
        if not ids or self.session is None:
            return False
        found = common_folder(self.session.catalog, ids)
        if found is None:
            return False
        pack_id, folder = found
        values = self.bulk.values() if self.bulk is not None and len(ids) > 1 else {}
        dialog = FolderRuleDialog(
            [p.pack_id for p in self.session.catalog.packs],
            pack_id,
            default_glob(folder),
            values,
            self,
        )
        if not self.run_rule_dialog(dialog):
            return False
        return self.session.add_rule(dialog.rule())

    def run_rule_dialog(self, dialog: FolderRuleDialog) -> bool:
        return bool(dialog.exec())
