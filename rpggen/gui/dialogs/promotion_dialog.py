"""What a regeneration is about to change, shown before it changes anything (T12.40)."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rpggen.core.promote import PromotionSummary
from rpggen.gui import icons
from rpggen.gui.widgets.card import INFO, Banner


def group_by_folder(files: list[str]) -> dict[str, list[str]]:
    """``{"game/maps": ["starter_map.tscn", ...]}`` in folder order ("" is the project folder)."""
    groups: dict[str, list[str]] = defaultdict(list)
    for rel in sorted(files):
        folder, _, name = rel.rpartition("/")
        groups[folder].append(name)
    return dict(sorted(groups.items()))


class PromotionDialog(QDialog):
    """Lists the files to update (by folder), the conflicts, the deletions that are respected and
    where the backup goes. Accepting regenerates; rejecting cancels the run."""

    def __init__(self, summary: PromotionSummary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("promotionDialog")
        self.setWindowTitle(self.tr("Changes to your project"))
        self.resize(640, 520)
        self.summary = summary
        layout = QVBoxLayout(self)
        intro = QLabel(
            self.tr(
                "Regenerating will change the project in the ways below. Nothing has been "
                "written yet."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tree = QTreeWidget()
        self.tree.setObjectName("promotionTree")
        self.tree.setHeaderHidden(True)
        self.tree.setAccessibleName(self.tr("Files the regeneration changes"))
        layout.addWidget(self.tree, 1)
        self.update_item = self._section(
            self.tr("Files to update ({0})").format(len(summary.write)), summary.write, True
        )
        self.conflict_item = self._section(
            self.tr(
                "Files you changed ({0}): the new version is written beside as .rpggen-new"
            ).format(len(summary.conflicts)),
            summary.conflicts,
            False,
        )
        self.delete_item = self._section(
            self.tr("Files rpggen no longer makes ({0}): removed").format(len(summary.delete)),
            summary.delete,
            False,
        )
        self.respected_item = self._section(
            self.tr("Files you deleted ({0}): they stay deleted").format(
                len(summary.skipped_deleted)
            ),
            summary.skipped_deleted,
            False,
        )
        for item, icon_name, colour in (
            (self.update_item, "refresh-cw", "accent"),
            (self.conflict_item, "alert-triangle", "warning"),
            (self.delete_item, "trash", "danger"),
            (self.respected_item, "info", "text_muted"),
        ):
            item.setIcon(0, icons.icon(icon_name, colour))
        self.backup_banner = Banner(
            INFO, self.tr("The old versions are saved first, in {0}.").format(summary.backup)
        )
        self.backup_banner.setObjectName("promotionBackupBanner")
        self.backup_label = self.backup_banner.text_label
        self.backup_label.setObjectName("promotionBackup")
        layout.addWidget(self.backup_banner)
        buttons = QDialogButtonBox()
        self.go_button = buttons.addButton(
            self.tr("Regenerate"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.go_button.setObjectName("promotionGo")
        self.cancel_button = buttons.addButton(
            self.tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.cancel_button.setObjectName("promotionCancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _section(self, title: str, files: list[str], expanded: bool) -> QTreeWidgetItem:
        item = QTreeWidgetItem([title])
        item.setHidden(not files)
        self.tree.addTopLevelItem(item)
        for folder, names in group_by_folder(files).items():
            parent = QTreeWidgetItem([f"{folder or '.'} ({len(names)})"])
            item.addChild(parent)
            for name in names:
                parent.addChild(QTreeWidgetItem([name]))
        item.setExpanded(expanded and bool(files))
        return item

    def listed(self, section: QTreeWidgetItem) -> list[str]:
        """The file paths under a section (folder + name), for tests and screen readers."""
        out: list[str] = []
        for i in range(section.childCount()):
            folder_item = section.child(i)
            assert folder_item is not None
            folder = folder_item.text(0).rsplit(" (", 1)[0]
            for j in range(folder_item.childCount()):
                name_item = folder_item.child(j)
                assert name_item is not None
                name = name_item.text(0)
                out.append(name if folder == "." else f"{folder}/{name}")
        return out
