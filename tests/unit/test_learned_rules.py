"""T12.59: rules learned from the user's fixes."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, explain, inventory, learned_rules
from rpggen.core.learned_rules import Edit, LearnedRule, RuleBook

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _taught(n: int = 3, value: str = "DECORATION") -> RuleBook:
    book = RuleBook()
    learned_rules.learn(
        book, [Edit(f"loot/items/thing_{i}.png", "role", value) for i in range(n)], "2026-10-08"
    )
    return book


def _assemble(pack: str, rules: list[LearnedRule] | None) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], learned=rules)
    return cat


def test_rules_are_created_from_edits() -> None:
    book = _taught(3)
    folder = book.find("folder", "items", "role", "DECORATION")
    assert folder is not None and folder.hits == 3 and folder.misses == 0 and folder.active
    assert book.find("folder", "loot", "role", "DECORATION") is not None
    assert book.find("name", "thing", "role", "DECORATION") is not None
    assert all(r.kind != "name" or r.token != "png" for r in book.rules)  # no stop words
    # the same folder fixed to another value: a miss for the first rule
    learned_rules.learn(book, [Edit("loot/items/x.png", "role", "ITEM")])
    assert book.find("folder", "items", "role", "DECORATION").misses == 1
    assert not _taught(1).find("folder", "items", "role", "DECORATION").active  # one fix: not yet


def test_an_undone_fix_is_taken_back() -> None:
    book = _taught(2)
    learned_rules.learn(book, [Edit("loot/items/thing_1.png", "role", "DECORATION")], weight=-1)
    assert book.find("folder", "items", "role", "DECORATION").hits == 1
    learned_rules.learn(book, [Edit("loot/items/thing_0.png", "role", "DECORATION")], weight=-1)
    assert book.rules == []  # no evidence left


def test_learned_rules_apply_on_a_new_pack_and_stay_auto_detected() -> None:
    book = _taught(5)
    plain = {a.path: a for a in _assemble("mixed", None).assets}
    learned = {a.path: a for a in _assemble("mixed", book.rules).assets}
    item = next(p for p in learned if "/items/" in p)
    assert catalog.effective(plain[item]).get("role") != "DECORATION"
    asset = learned[item]
    assert catalog.effective(asset)["role"] == "DECORATION"
    assert asset.detected_by == "learned"
    assert asset.confidence <= learned_rules.CAP  # the cap holds
    assert asset.status == "AUTO_DETECTED"
    others = [p for p in learned if "/items/" not in p]
    assert all(learned[p].to_json() == plain[p].to_json() for p in others)  # nothing else moves


def test_the_confidence_is_the_hit_rate_capped() -> None:
    rule = LearnedRule("folder", "items", "role", "ITEM", hits=50, misses=0)
    assert rule.confidence == learned_rules.CAP == 0.85
    rule.misses = 50  # half the time corrected: 0.5, below the 0.6 needed to be used
    assert rule.confidence == 0.5 and not rule.active
    assert LearnedRule("folder", "items", "role", "ITEM", hits=7, misses=3).confidence == 0.7


def test_a_disabled_rule_is_not_used(tmp_path: Path) -> None:
    book = _taught(5)
    for rule in book.rules:
        rule.enabled = False
    learned_rules.save(book, tmp_path / "rules.json")
    again = learned_rules.load(tmp_path / "rules.json")
    assert again.to_json() == book.to_json()
    assert learned_rules.proposals(again.rules, "loot/items/new.png") == {}
    item = next(a for a in _assemble("mixed", again.rules).assets if "/items/" in a.path)
    assert item.detected_by != "learned"


def test_without_rules_the_catalog_does_not_change() -> None:
    a = _assemble("mixed", None)
    b = _assemble("mixed", [])
    assert [x.to_json() for x in a.assets] == [x.to_json() for x in b.assets]
    assert all("learned" not in p.adapters_matched for p in a.packs)


def test_the_audit_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    book = _taught(4)
    monkeypatch.setattr(learned_rules, "cached", lambda path=None: book)
    item = next(a for a in _assemble("mixed", book.rules).assets if "/items/" in a.path)
    assert explain.why(item).startswith("learned from your earlier fixes (4 times)")


def test_a_folder_rule_is_made_from_a_rule() -> None:
    rule = LearnedRule("folder", "items", "role", "ITEM", hits=3)
    assert learned_rules.as_folder_rule(rule, "pack") == {
        "pack_id": "pack",
        "glob": "**/*items*/**",
        "set": {"role": "ITEM"},
    }
    name = LearnedRule("name", "tree", "usage", "object", hits=3)
    assert learned_rules.as_folder_rule(name, "p")["glob"] == "**/*tree*"


def test_a_broken_file_starts_empty(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text("{not json", encoding="utf-8")
    assert learned_rules.load(path).rules == []
    path.write_text('{"version": 1, "rules": [{"kind": "x"}, 5]}', encoding="utf-8")
    assert learned_rules.load(path).rules == []
