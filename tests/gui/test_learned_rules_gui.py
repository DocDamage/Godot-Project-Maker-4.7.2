"""T12.59: the audit learns from fixes; Edit > Learned rules lists, turns off, deletes, exports."""

from __future__ import annotations

from PySide6.QtCore import Qt

from rpggen.core import learned_rules
from rpggen.gui.dialogs.learned_rules_dialog import LearnedRulesDialog
from tests.gui.test_bulk import _page


def test_a_fix_in_the_audit_is_learned_and_an_undo_takes_it_back(qtbot) -> None:
    page, state = _page(qtbot)  # the data folder is a temporary one (tests/gui/conftest.py)
    items = [a.id for a in state.catalog.assets if "/items/" in a.path][:3]
    assert page.session is not None and page.session.learner is not None
    page.session.bulk_edit(items, {"role": "DECORATION"})
    rule = learned_rules.load().find("folder", "items", "role", "DECORATION")
    assert rule is not None and rule.hits == 3 and rule.active
    page.session.undo_stack.undo()
    assert learned_rules.load().find("folder", "items", "role", "DECORATION") is None


def test_the_dialog_turns_off_deletes_and_exports(qtbot, tmp_path) -> None:
    path = tmp_path / "rules.json"
    book = learned_rules.RuleBook(
        [
            learned_rules.LearnedRule("folder", "items", "role", "ITEM", hits=4),
            learned_rules.LearnedRule("name", "tree", "usage", "object", hits=1),
        ]
    )
    learned_rules.save(book, path)
    added: list[list[dict]] = []
    dialog = LearnedRulesDialog(path, ["mixed"], lambda rules: added.append(rules) or len(rules))
    qtbot.addWidget(dialog)
    assert dialog.table.rowCount() == 2 and "used (85%)" in dialog.table.item(0, 4).text()
    assert "needs more fixes" in dialog.table.item(1, 4).text()
    dialog.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)  # turn the first off
    assert learned_rules.load(path).rules[0].enabled is False
    assert dialog.table.item(0, 4).text() == "off"
    dialog.table.selectRow(0)
    assert dialog.export_selected() == 1
    assert added == [[{"pack_id": "mixed", "glob": "**/*items*/**", "set": {"role": "ITEM"}}]]
    dialog.table.selectRow(1)
    assert dialog.delete_selected() == 1
    assert [r.token for r in learned_rules.load(path).rules] == ["items"]


def test_without_an_audit_the_export_is_off(qtbot, tmp_path) -> None:
    dialog = LearnedRulesDialog(tmp_path / "none.json")
    qtbot.addWidget(dialog)
    assert not dialog.export_button.isEnabled() and dialog.table.rowCount() == 0
    assert dialog.empty_label.isVisibleTo(dialog)
