"""Page 5: features, presets, starter map, resolution, window size, map layers and advanced
settings. The decisions are in ``rpggen.gui.models.options_model``, the sections in
``rpggen.gui.widgets.options_sections``; this module lays them out and wires them."""

from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import QT_TRANSLATE_NOOP
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import config as config_mod
from rpggen.core import options, vcs
from rpggen.errors import Issue
from rpggen.gui import icons, theme
from rpggen.gui.dialogs.options_dialogs import ManagePresetsDialog, SolidValuesDialog
from rpggen.gui.models.options_model import (  # noqa: F401 - tests import DEFAULTS_ITEM
    DEFAULTS_ITEM,
    ROOM_LAYERS,
    SEED_MAX,
    OptionsModel,
    OptionValues,
)
from rpggen.gui.pages.base import WizardPage, form_error
from rpggen.gui.state import WizardState
from rpggen.gui.widgets import buttons
from rpggen.gui.widgets import options_sections as sections
from rpggen.gui.widgets.options_summary import OptionsSummary

WIDE_WIDTH = 920  # at this width of the page and more the feature cards are side by side
SUMMARY_SIDE_WIDTH = 1200  # at this width and more the summary has a column of its own


class OptionsPage(WizardPage):
    title = "Options"
    purpose = str(
        QT_TRANSLATE_NOOP(
            "WizardPage", "What the project includes. Presets fill the page in one click."
        )
    )
    help_anchor = "3. Using a pack you bought"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = OptionsModel(self.tr)
        self._loading = False
        outer = self.page_layout()

        self.presets = sections.PresetBar()
        self.header.add_widget(self.presets)  # in the header's slot (T15.14)
        self.preset_combo = self.presets.combo
        self.save_preset_button = self.presets.save_button
        self.manage_presets_button = self.presets.manage_button

        scroll = QScrollArea()
        scroll.setObjectName("optionsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("optionsBody")
        column_box = QVBoxLayout(content)  # the feature cards, then every section full width
        column_box.setContentsMargins(0, 0, theme.px("space_8"), 0)
        column_box.setSpacing(theme.px("space_12"))
        scroll.setWidget(content)
        # the summary card: on top, or in a right-hand column at SUMMARY_SIDE_WIDTH and more
        self.summary = OptionsSummary()
        outer.addWidget(self.summary)
        main_row = QHBoxLayout()
        main_row.addWidget(scroll, 1)
        self.side = QWidget()
        self.side.setObjectName("summarySide")
        self.side_layout = QVBoxLayout(self.side)
        self.side_layout.setContentsMargins(theme.px("space_12"), 0, 0, 0)
        self.side_layout.addStretch(1)
        self.side.setFixedWidth(300)
        self.side.setVisible(False)
        main_row.addWidget(self.side)
        outer.addLayout(main_row, 1)
        self._summary_outer = outer
        self._summary_on_side = False

        self.features = sections.FeatureGroups()
        self.starter_box = sections.StarterMapBox()
        self.world_box = sections.StarterWorldBox()  # a metroidvania's, instead of the map's
        self.world_box.setVisible(False)
        # the three arcade kinds (T16.16): each has its box, with a preview of its plan
        self.arcade_boxes: dict[str, sections.ArcadeBox] = {
            "shmup": sections.ShmupBox(),
            "run_and_gun": sections.RunAndGunBox(),
            "racing": sections.RacingBox(),
        }
        for arcade in self.arcade_boxes.values():
            arcade.setVisible(False)
        self.imported_box = sections.ImportedMapsBox()
        self.screen_box = sections.ScreenBox()
        self.layers_box = sections.LayersBox()
        self.version_control = sections.VersionControlBox()
        self.export_targets = sections.ExportTargetsBox()
        self.advanced = sections.AdvancedOptions()
        column: tuple[QWidget, ...] = (
            self.features,
            self.starter_box,
            self.world_box,
            *self.arcade_boxes.values(),
            self.imported_box,
            self.screen_box,
            self.layers_box,
            self.version_control,
            self.export_targets,
            self.advanced,
        )
        for widget in column:
            column_box.addWidget(widget)
        column_box.addStretch(1)

        # the widgets under the names the tests and the other pages use
        self.feature_boxes, self.feature_needs = self.features.boxes, self.features.needs
        self.features_reset = self.features.reset
        buttons.set_kind(self.features_reset, buttons.QUIET)
        icons.set_icon(self.features_reset, "refresh-cw")
        self.features_reset.setToolTip(self.tr("Put the feature check boxes back to the defaults"))
        self.header.add_widget(self.features_reset)  # it left the first feature group
        box = self.starter_box
        self.starter_note, self.starter_size = box.note, box.size_editor
        self.starter_counts, self.starter_reset = box.counts, box.reset
        self.ground_label, self.ground_combo = box.ground_label, box.ground_combo
        self.preview = box.preview
        imported = self.imported_box
        self.imported_list, self.imported_starter = imported.list, imported.starter
        self.solid_button, self.imported_note = imported.solid_button, imported.note
        screen = self.screen_box
        self.resolution, self.window_editor = screen.resolution, screen.window_editor
        self.hint_label, self.screen_reset = screen.hint_label, screen.reset
        layers = self.layers_box
        self.layer_list, self.layer_name = layers.list, layers.name
        self.add_layer_button, self.remove_layer_button = layers.add_button, layers.remove_button
        self.up_button, self.down_button = layers.up_button, layers.down_button
        self.layers_reset = layers.reset
        self.git_box = self.version_control.git_box
        self.pack_art_radios = self.version_control.pack_art_radios
        self.export_target_boxes = self.export_targets.boxes
        self.advanced_body = self.advanced.body
        self.seed_box, self.input_table = self.advanced.seed_box, self.advanced.input_table

        for key, check in self.feature_boxes.items():
            check.toggled.connect(lambda checked, k=key: self._on_feature(k, checked))
        self.features_reset.clicked.connect(self._reset_features)
        self.preview.rerollRequested.connect(self.reroll)
        self.starter_box.edited.connect(self._on_starter_edited)
        self.starter_reset.clicked.connect(self._reset_starter)
        self.world_box.edited.connect(self._on_starter_edited)
        self.world_box.reset.clicked.connect(self._reset_starter)
        for arcade in self.arcade_boxes.values():
            arcade.edited.connect(self._on_starter_edited)
            arcade.reset.clicked.connect(self._reset_starter)
        self.imported_box.edited.connect(self._on_imported_edited)
        self.solid_button.clicked.connect(self.edit_solid_values)
        for editor in (self.resolution, self.window_editor):
            editor.width_box.valueChanged.connect(self._on_edited)
            editor.height_box.valueChanged.connect(self._on_edited)
        self.screen_reset.clicked.connect(self._reset_screen)
        self.layers_box.edited.connect(self._on_edited)
        self.git_box.toggled.connect(self.model.set_git)
        for choice, radio in self.pack_art_radios.items():
            radio.toggled.connect(lambda on, c=choice: self._on_pack_art(c) if on else None)
        for key, check in self.export_target_boxes.items():
            check.toggled.connect(lambda on, k=key: self._on_export_target(k, on))
        self.seed_box.valueChanged.connect(self._on_seed_edited)
        self.repair_box = self.advanced.repair_box
        self.repair_box.toggled.connect(self._on_repair_toggled)
        self.input_table.itemChanged.connect(lambda _item: self._on_edited())
        self.preset_combo.activated.connect(self._on_preset_chosen)
        self.save_preset_button.clicked.connect(self.save_preset)
        self.manage_presets_button.clicked.connect(self.manage_presets)
        self._wide: bool | None = None
        self._apply_columns(False)

    @property
    def state(self) -> WizardState | None:
        return self.model.state

    @property
    def draft(self) -> config_mod.GeneratorConfig | None:
        return self.model.draft

    # ------------------------------------------------------------------ layout

    def _apply_columns(self, wide: bool) -> None:
        if wide == self._wide:
            return
        self._wide = wide
        self.features.set_columns(2 if wide else 1)

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802
        super().resizeEvent(event)
        self._apply_columns(self.width() >= WIDE_WIDTH)
        self._place_summary(self.width() >= SUMMARY_SIDE_WIDTH)

    def _place_summary(self, side: bool) -> None:
        """Move the summary card between the top of the page and the right-hand column."""
        if side == self._summary_on_side:
            return
        self._summary_on_side = side
        if side:
            self._summary_outer.removeWidget(self.summary)
            self.side_layout.insertWidget(0, self.summary)
        else:
            self.side_layout.removeWidget(self.summary)
            self._summary_outer.insertWidget(1, self.summary)
        self.side.setVisible(side)
        self.summary.show()

    @property
    def summary_on_side(self) -> bool:
        return self._summary_on_side

    @property
    def two_columns(self) -> bool:
        return bool(self._wide)

    def refresh_summary(self) -> None:
        """Re-draw the summary from the options as they are now (it updates live)."""
        if self.draft is None:
            return
        summary, seconds, size = self.model.summary(self.features.values(), self.resolution.value())
        self.summary.set_summary(summary, seconds, size)

    # ------------------------------------------------------------------ loading

    def enter(self, state: WizardState) -> None:
        self.model.enter(state)
        available = vcs.git_available()
        text, tooltip, checked = self.model.git_box(available)
        self.version_control.show_git(text, available, tooltip, checked)
        self._fill_presets()
        if self.draft is None:
            return
        self.starter_box.fill_ground(self.model.ground_choices())
        self.imported_box.fill(self.model.imported_rows(), self.model.has_intgrid())
        self._show_archetype()
        self._update_starter_state()
        self._load_draft()
        self.changed.emit()

    def _show_archetype(self) -> None:
        """A metroidvania has a starter world instead of a starter map, no imported maps, no
        pathfinding and the layers of a room (T14.10)."""
        side = self.model.is_side
        arcade = self.arcade_box
        self.starter_box.setVisible(not self.model.planned)
        self.world_box.setVisible(side)
        for box in self.arcade_boxes.values():
            box.setVisible(box is arcade)
        if self.model.planned:
            self.imported_box.setVisible(False)
        hidden = set(options.ARCADE_HIDDEN) if arcade is not None else set()
        self.features.set_hidden({"navigation"} if side else hidden)
        self.layers_box.set_fixed(side)
        # a stage is not a map of layers: an arcade kind builds its own
        self.layers_box.setVisible(arcade is None)

    @property
    def arcade_box(self) -> sections.ArcadeBox | None:
        """The box of the draft's arcade kind; None for the other kinds."""
        if self.draft is None or not self.model.is_arcade:
            return None
        return self.arcade_boxes.get(self.draft.archetype)

    def _load_draft(self) -> None:
        """Shows the draft in the widgets."""
        draft = self.draft
        assert draft is not None
        self._loading = True
        try:
            self.model.loaded()
            self.features.set_values(draft.features)
            self.resolution.set_value(draft.resolution)
            self.window_editor.set_value(draft.window_size)
            self.seed_box.setValue(min(draft.seed, SEED_MAX))
            self.repair_box.setChecked(draft.repair_world)
            self.advanced.fill_input(self.model.input_rows())
            if self.model.is_side:
                self.layers_box.fill(list(ROOM_LAYERS))
                self.world_box.load(draft.starter_map_options(), self.model.built_added_rooms())
            elif (arcade := self.arcade_box) is not None:
                self.layers_box.fill(draft.map_layers)
                arcade.load(draft.starter_map_options(), self.model.built_added_stages())
            else:
                self.layers_box.fill(draft.map_layers)
                self.starter_box.load(
                    draft.starter_map_options(),
                    self.model.starter_locked,
                    self.model.world_names(),
                )
            chosen = self.model.chosen_imported()
            if chosen is not None:
                self.imported_box.load(chosen)
            self._update_starter_state()
            self._show_world()
            self.pack_art_radios[draft.pack_art].setChecked(True)
            self.export_targets.set_values(draft.selected_export_targets())
        finally:
            self._loading = False
        self._update_dependencies()
        self._update_hint()
        self._schedule_preview()
        self.refresh_summary()

    def leave(self, state: WizardState) -> bool | None:
        if state.config is None or self.draft is None:
            return None
        self._collect()
        self.model.apply_to(state.config)
        return None

    def _on_pack_art(self, choice: str) -> None:
        if self._loading or self.draft is None:
            return
        self.model.set_pack_art(choice)
        self.changed.emit()

    def _on_export_target(self, key: str, checked: bool) -> None:
        if self._loading or self.draft is None:
            return
        if not self.model.set_export_target(key, checked):  # the last one stays on
            self.export_targets.set_values(self.draft.selected_export_targets())
            return
        self.changed.emit()

    # ------------------------------------------------------------------ features

    def _on_feature(self, key: str, checked: bool) -> None:
        if self._loading:
            return
        self.model.feature_wish(key, checked)
        self._update_dependencies()
        self._on_edited()

    def _update_dependencies(self) -> None:
        was = self._loading
        self._loading = True
        try:
            self.features.show_states(self.model.dependent_features(self.features.values()))
        finally:
            self._loading = was

    def _reset_features(self) -> None:
        self._loading = True
        try:
            self.features.set_values(self.model.default_features())
        finally:
            self._loading = False
        self._update_dependencies()
        self._on_edited()

    # ------------------------------------------------------------------ screen

    def _update_hint(self) -> None:
        text, suggested = self.model.screen_hint(self.resolution.value())
        self.hint_label.setText(text)
        self.resolution.mark_suggested(suggested)

    def _reset_screen(self) -> None:
        resolution, window = self.model.default_screen()
        self.resolution.set_value(resolution)
        self.window_editor.set_value(window)
        self._on_edited()

    # ------------------------------------------------------------------ starter map

    def _update_starter_state(self) -> None:
        state = self.model.starter_state()
        if self.model.is_side:
            self.world_box.show_state(state)
            return
        if (arcade := self.arcade_box) is not None:
            arcade.show_state(state)
            return
        self.starter_box.show_state(state)
        self.imported_starter.setEnabled(state.imported_enabled)

    def starter_values(self) -> dict[str, Any]:
        """The starter map options as the widgets show them (the starter world's for a
        metroidvania, the stages' or the tracks' for an arcade kind)."""
        if self.model.is_side:
            return self.world_box.values()
        if (arcade := self.arcade_box) is not None:
            return arcade.values()
        return self.starter_box.values()

    def _on_starter_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self.model.store_starter(self.starter_values())
        self._schedule_preview()
        self._show_world()
        self.refresh_summary()
        self.changed.emit()

    def _show_world(self) -> None:
        """The world of the areas table, drawn under it (planned at once: it is cheap); for a
        metroidvania the rooms, seen from the side."""
        if self.model.is_side:
            self.world_box.show_plan(*self.model.rooms_preview(self.starter_values()))
            return
        if (arcade := self.arcade_box) is not None:
            arcade.show_plan(*self.model.stages_preview(self.starter_values()))
            return
        self.starter_box.show_world(self.model.world_preview(self.starter_values()))

    def _reset_starter(self) -> None:
        if self.draft is None:
            return
        self._loading = True
        try:
            if self.model.is_side:
                self.world_box.load(self.model.starter_defaults())
            elif (arcade := self.arcade_box) is not None:
                arcade.load(self.model.starter_defaults())
            else:
                self.starter_box.load(
                    self.model.starter_defaults(),
                    self.model.starter_locked,
                    self.model.world_names(),
                )
        finally:
            self._loading = False
        self._on_starter_edited()

    def _schedule_preview(self) -> None:
        values = self.model.preview_options(self.starter_values())
        if values is None or self.state is None or self.state.catalog is None:
            return
        from rpggen.gui.pages.audit_page import make_resolver

        assert self.draft is not None
        self.preview.request(
            self.state.catalog,
            make_resolver(self.state),
            values,
            self.draft.seed,
            self.draft.archetype,
            values["ground"],
            "",
        )

    def reroll(self) -> None:
        """A new seed (shown under Advanced) gives another arrangement."""
        self.seed_box.setValue(random.randint(0, SEED_MAX))

    def _on_repair_toggled(self, on: bool) -> None:
        if self._loading or self.draft is None:
            return
        self.draft.repair_world = on
        self._on_edited()

    def _on_seed_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self.draft.seed = self.seed_box.value()
        self._schedule_preview()
        self._show_world()
        self._on_edited()

    # ------------------------------------------------------------------ imported maps

    def imported_map_ids(self) -> list[str]:
        """The ids of the maps the catalog read from the packs."""
        return self.model.imported_map_ids()

    def imported_values(self) -> dict[str, Any]:
        """The imported maps selection as the widgets show it (empty when nothing is chosen)."""
        return self.model.normalize_imported(*self.imported_box.selection())

    def _imported_or_none(self) -> dict[str, Any] | None:
        return self.imported_values() if self.imported_list.count() else None

    def _on_imported_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self.imported_box.sync_starter_item()
        if (selection := self._imported_or_none()) is not None:
            self.draft.imported_maps = selection
        self._update_starter_state()
        self._schedule_preview()
        self.refresh_summary()
        self.changed.emit()

    def edit_solid_values(self) -> bool:
        """Opens the list of IntGrid values; returns True when a value changed."""
        rows = self.model.solid_rows()
        if not rows:
            return False
        dialog = SolidValuesDialog(rows, self)
        if not self.run_dialog(dialog):
            return False
        changed = self.model.set_solid(dialog.choices())
        if changed:
            self.changed.emit()
        return changed > 0

    # ------------------------------------------------------------------ layers

    def layers(self) -> list[str]:
        return self.layers_box.layers()

    # ------------------------------------------------------------------ presets

    def _fill_presets(self) -> None:
        self.presets.fill(self.model.builtin_items(), self.model.user_items())

    def apply_preset_named(self, name: str) -> bool:
        """Applies a saved preset (or the defaults) to the page; False when it does not fit."""
        if self.draft is None:
            return False
        self._collect()
        try:
            if not self.model.apply_preset(name):
                return False
        except ValueError as exc:
            self.show_message(
                self.tr("Preset"), self.tr("The preset does not fit: {0}").format(exc)
            )
            return False
        self._load_draft()
        self.changed.emit()
        return True

    def _on_preset_chosen(self, index: int) -> None:
        name = self.preset_combo.itemData(index)
        if name is not None:
            self.apply_preset_named(name)
        self.preset_combo.setCurrentIndex(0)

    def ask_preset_name(self) -> str | None:  # overridden by tests
        text, ok = QInputDialog.getText(
            self, self.tr("Save as preset"), self.tr("Name of the preset")
        )
        return text.strip() if ok and text.strip() else None

    def show_message(self, title: str, text: str) -> None:  # overridden by tests
        QMessageBox.warning(self, title, text)

    def save_preset(self) -> str | None:
        if self.draft is None:
            return None
        name = self.ask_preset_name()
        if name is None:
            return None
        self._collect()
        if not self.model.save_preset(name):
            self.show_message(
                self.tr("Preset"),
                self.tr("{0} is a built-in preset. Choose another name for your copy.").format(
                    name
                ),
            )
            return None
        self._fill_presets()
        return name

    def manage_presets(self) -> None:
        dialog = ManagePresetsDialog(self.model.preset_names(), self)
        self.run_dialog(dialog)
        self.model.edit_presets(dialog.renames, dialog.deleted)
        self._fill_presets()

    def run_dialog(self, dialog) -> bool:  # noqa: ANN001 - overridden by tests
        return bool(dialog.exec())

    # ------------------------------------------------------------------ collecting

    def _collect(self) -> None:
        self.model.collect(
            OptionValues(
                features=self.features.values(),
                resolution=self.resolution.value(),
                window_size=self.window_editor.value(),
                layers=self.layers(),
                seed=self.seed_box.value(),
                starter=self.starter_values(),
                imported=self._imported_or_none(),
                input_rows=self.advanced.input_rows(),
            )
        )

    def _on_edited(self, *_args: object) -> None:
        if self._loading or self.draft is None:
            return
        self._update_hint()
        if self.arcade_box is not None and self.draft.resolution != self.resolution.value():
            self.draft.resolution = self.resolution.value()  # a stage is as long as its screens
            self._show_world()
        self.layers_box.update_buttons()
        self.refresh_summary()
        self.changed.emit()

    # ------------------------------------------------------------------ wizard hooks

    def status(self, state: WizardState) -> tuple[str, int]:
        return ("ok", 0) if state.config is not None else ("none", 0)

    def validate(self, state: WizardState) -> list[Issue]:
        if self.draft is None:
            return []
        self._collect()
        return [form_error(p) for p in self.model.validate()]
