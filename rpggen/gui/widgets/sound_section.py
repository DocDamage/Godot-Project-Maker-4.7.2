"""The Sound group of the Mapping page: one row per sound slot, collapsed by default (T11.20).

Custom slots (T13.16): **Add slot…** makes a row for a slot of the user's own, and such a row has
a remove button. ``aboutToChange`` is emitted before every change, so the page can remember the
state for its Undo.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rpggen.core import catalog as catalog_mod
from rpggen.core import classifier, sound_slots
from rpggen.gui.widgets import audio_preview

Resolver = Callable[[catalog_mod.Asset], Path | None]


def describe(asset: catalog_mod.Asset, resolver: Resolver | None = None) -> str:
    """``name · pack · 24.0 s`` of an audio asset."""
    name = asset.path.rsplit("/", 1)[-1]
    text = f"{name} · {asset.pack_id}"
    seconds = sound_slots.duration_of(asset)
    if seconds is None and resolver is not None and (path := resolver(asset)) is not None:
        seconds = classifier.audio_duration(Path(path))
    if seconds is not None:
        text += f" · {seconds:.1f} s"
    return text


class SoundPickerDialog(QDialog):
    """The audio assets of the right kind, each with its length and a ▶ button."""

    def __init__(
        self,
        catalog: catalog_mod.Catalog,
        slot: sound_slots.Slot,
        resolver: Resolver | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("soundPicker")
        self.setWindowTitle(self.tr("Choose a sound for {0}").format(slot.label))
        self.resize(560, 380)
        self.resolver = resolver
        self.picked: str | None = None
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setObjectName("soundList")
        self.assets = sound_slots.audio_assets(catalog, slot.kind)
        for asset in self.assets:
            item = QListWidgetItem(describe(asset, resolver))
            item.setData(Qt.ItemDataRole.UserRole, asset.id)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.play_button = QPushButton("▶ " + self.tr("Play"))
        self.play_button.setObjectName("soundPlay")
        self.play_button.setToolTip(self.tr("Listen to the selected sound"))
        self.play_button.setEnabled(False)
        self.play_button.setVisible(audio_preview.available())
        row.addWidget(self.play_button)
        row.addStretch(1)
        layout.addLayout(row)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.list.currentItemChanged.connect(self._on_current)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        self.play_button.clicked.connect(self.play_current)
        self.finished.connect(lambda _code: audio_preview.stop())

    def _on_current(self, item: QListWidgetItem | None) -> None:
        self.picked = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.ok_button.setEnabled(self.picked is not None)
        self.play_button.setEnabled(self.picked is not None)

    def play_current(self) -> bool:
        asset = next((a for a in self.assets if a.id == self.picked), None)
        path = self.resolver(asset) if asset is not None and self.resolver else None
        return bool(path) and audio_preview.play(Path(path))  # type: ignore[arg-type]


class SoundSection(QFrame):
    """Collapsed to "3 music tracks, 14 sound effects assigned" with an Edit… expander."""

    changed = Signal()
    aboutToChange = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("soundSection")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.catalog: catalog_mod.Catalog | None = None
        self.resolver: Resolver | None = None
        self.sounds: dict[str, str] = {}
        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        self.title_label = QLabel("<b>" + self.tr("Sound") + "</b>")
        self.summary_label = QLabel()
        self.summary_label.setObjectName("soundSummary")
        self.edit_button = QPushButton(self.tr("Edit…"))
        self.edit_button.setObjectName("soundEdit")
        self.edit_button.setCheckable(True)
        self.edit_button.setToolTip(self.tr("Show a row for every sound slot"))
        head.addWidget(self.title_label)
        head.addWidget(self.summary_label, 1)
        head.addWidget(self.edit_button)
        layout.addLayout(head)
        self.body = QWidget()
        self.body.setObjectName("soundBody")
        self.grid = QGridLayout(self.body)
        self.grid.setColumnStretch(1, 1)
        self.rows: dict[str, tuple[QLabel, QPushButton, QPushButton, QPushButton]] = {}
        self.remove_buttons: dict[str, QPushButton] = {}
        self._row_widgets: list[QWidget] = []
        self._build_rows()
        self.body.setVisible(False)
        layout.addWidget(self.body)
        foot = QHBoxLayout()
        self.add_button = QPushButton(self.tr("Add slot…"))
        self.add_button.setObjectName("soundAddSlot")
        self.add_button.setToolTip(
            self.tr(
                "A slot of your own, played by its name: sfx_<name> or music_<name>. "
                "sfx_step_<surface> is the footstep on ground tagged surface:<surface>."
            )
        )
        self.add_button.setVisible(False)
        self.add_error = QLabel()
        self.add_error.setObjectName("soundAddError")
        self.add_error.setProperty("role", "error")
        self.add_error.setWordWrap(True)
        self.add_error.setVisible(False)
        foot.addWidget(self.add_button)
        foot.addWidget(self.add_error, 1)
        layout.addLayout(foot)
        self.edit_button.toggled.connect(self.body.setVisible)
        self.edit_button.toggled.connect(self.add_button.setVisible)
        self.add_button.clicked.connect(self.ask_new_slot)

    def slot_keys(self) -> list[str]:
        """The rows, top to bottom: the fixed slots, then the custom ones by name."""
        return list(sound_slots.SLOT_KEYS) + sound_slots.custom_slots(self.sounds)

    def _build_rows(self) -> None:
        for widget in self._row_widgets:
            self.grid.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._row_widgets = []
        self.rows = {}
        self.remove_buttons = {}
        for i, key in enumerate(self.slot_keys()):
            slot = sound_slots.slot(key)
            name = QLabel(slot.label)
            name.setToolTip(slot.help)
            asset_label = QLabel()
            asset_label.setObjectName(f"sound_{key}")
            choose = QPushButton(self.tr("Choose…"))
            choose.setObjectName(f"soundChoose_{key}")
            choose.setToolTip(self.tr("Pick another sound for this slot"))
            play = QPushButton("▶")
            play.setObjectName(f"soundPlay_{key}")
            play.setToolTip(self.tr("Listen to the current sound"))
            play.setVisible(audio_preview.available())
            clear = QPushButton(self.tr("Clear"))
            clear.setObjectName(f"soundClear_{key}")
            clear.setToolTip(self.tr("Leave this slot silent"))
            widgets: list[QWidget] = [name, asset_label, choose, play, clear]
            if sound_slots.is_custom(key):
                remove = QPushButton("✕")
                remove.setObjectName(f"soundRemove_{key}")
                remove.setToolTip(self.tr("Remove this slot"))
                remove.setAccessibleName(self.tr("Remove the slot {0}").format(key))
                remove.clicked.connect(lambda _=False, k=key: self.remove_slot(k))
                self.remove_buttons[key] = remove
                widgets.append(remove)
            for col, widget in enumerate(widgets):
                self.grid.addWidget(widget, i, col)
            self._row_widgets.extend(widgets)
            self.rows[key] = (asset_label, choose, play, clear)
            choose.clicked.connect(lambda _=False, k=key: self.choose(k))
            play.clicked.connect(lambda _=False, k=key: self.play(k))
            clear.clicked.connect(lambda _=False, k=key: self.clear(k))

    # ------------------------------------------------------------------ data

    def set_data(
        self, catalog: catalog_mod.Catalog, sounds: dict[str, str], resolver: Resolver | None
    ) -> None:
        self.catalog = catalog
        self.sounds = sound_slots.resolve_sounds(catalog, sounds)
        self.resolver = resolver
        self.setVisible(
            bool(
                sound_slots.audio_assets(catalog, sound_slots.MUSIC)
                or sound_slots.audio_assets(catalog, sound_slots.SFX)
            )
        )
        self._refresh()

    def _refresh(self) -> None:
        assert self.catalog is not None
        self.summary_label.setText(sound_slots.summary(self.sounds))
        if list(self.rows) != self.slot_keys():
            self._build_rows()
        for key in self.slot_keys():
            slot = sound_slots.slot(key)
            label, choose, play, clear = self.rows[key]
            ident = self.sounds.get(slot.key, "")
            asset = self.catalog.asset(ident) if ident else None
            label.setText(describe(asset, self.resolver) if asset else self.tr("(silent)"))
            clear.setEnabled(asset is not None)
            play.setEnabled(asset is not None)
            has_any = bool(sound_slots.audio_assets(self.catalog, slot.kind))
            choose.setEnabled(has_any)

    # ------------------------------------------------------------------ actions

    def run_picker(self, dialog: SoundPickerDialog) -> bool:  # overridden by tests
        return bool(dialog.exec())

    def choose(self, key: str) -> bool:
        assert self.catalog is not None
        dialog = SoundPickerDialog(self.catalog, sound_slots.slot(key), self.resolver, self)
        if not self.run_picker(dialog) or dialog.picked is None:
            return False
        self.aboutToChange.emit()
        self.sounds[key] = dialog.picked
        self._refresh()
        self.changed.emit()
        return True

    def clear(self, key: str) -> None:
        self.aboutToChange.emit()
        self.sounds[key] = sound_slots.CLEARED
        self._refresh()
        self.changed.emit()

    # ------------------------------------------------------------------ custom slots (T13.16)

    def slot_problem(self, key: str) -> str:
        """Why ``key`` cannot be added, or "" when it can."""
        if not sound_slots.is_valid_name(key):
            return self.tr(
                "Name the slot sfx_<name> or music_<name>: lower-case letters, digits and "
                "underscores, starting with a letter."
            )
        if key in self.slot_keys():
            return self.tr("There is a slot named {0} already.").format(key)
        return ""

    def add_slot(self, key: str) -> bool:
        """A new, silent custom slot. False (with the reason under the rows) when the name is
        not a slot name or is taken."""
        key = key.strip()
        problem = self.slot_problem(key)
        self.add_error.setText(problem)
        self.add_error.setVisible(bool(problem))
        if problem:
            return False
        self.aboutToChange.emit()
        self.sounds[key] = sound_slots.CLEARED
        self._refresh()
        self.changed.emit()
        return True

    def remove_slot(self, key: str) -> bool:
        if not sound_slots.is_custom(key) or key not in self.sounds:
            return False
        self.aboutToChange.emit()
        del self.sounds[key]
        self._refresh()
        self.changed.emit()
        return True

    def ask_name(self) -> str | None:  # overridden by tests
        text, ok = QInputDialog.getText(
            self,
            self.tr("Add a sound slot"),
            self.tr("The slot's name (sfx_<name> or music_<name>):"),
            text="sfx_",
        )
        return text if ok else None

    def ask_new_slot(self) -> bool:
        name = self.ask_name()
        return name is not None and self.add_slot(name)

    def restore(self, sounds: dict[str, str]) -> None:
        """Put back an earlier state (the page's Undo)."""
        self.sounds = dict(sounds)
        self.add_error.setVisible(False)
        if self.catalog is not None:
            self._refresh()

    def play(self, key: str) -> bool:
        assert self.catalog is not None
        asset = self.catalog.asset(self.sounds.get(key, ""))
        path = self.resolver(asset) if asset is not None and self.resolver else None
        return bool(path) and audio_preview.play(Path(path))  # type: ignore[arg-type]
