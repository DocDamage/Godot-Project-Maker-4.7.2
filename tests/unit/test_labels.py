from __future__ import annotations

from rpggen.core import classifier, explain, labels, requirements
from rpggen.gui.widgets import asset_detail


def test_every_role_and_usage_has_a_friendly_entry() -> None:
    roles = {
        *classifier.ROLE_ORDER,
        *asset_detail.ROLES,
        *requirements.REQUIRED_BY,
        *(r for r in requirements.RECOMMENDED),
        *(r for rs in requirements.REQUIRED.values() for r in rs),
    }
    for role in roles:
        assert role in labels.ROLE_INFO, role
        assert labels.role_label(role) and labels.role_help(role), role
    for usage in asset_detail.USAGES:
        assert usage in labels.USAGE_INFO, usage
        assert labels.usage_label(usage) and labels.usage_help(usage), usage


def test_unknown_names_are_shown_as_they_are() -> None:
    assert labels.role_label("MYSTERY") == "MYSTERY"
    assert labels.role_help("MYSTERY") == ""
    assert labels.usage_label("odd") == "odd"
    assert labels.group_of("PLAYER") == "Characters" and labels.group_of("AUDIO_SFX") == "Other"


def test_friendly_names_are_not_the_raw_ones() -> None:
    assert labels.role_label("GROUND") == "Ground tiles"
    assert labels.role_label("DECORATION") == "Decoration"
    assert labels.usage_label("tiles") == "Tile sheet"


def test_keywords_come_from_the_classifier_tables() -> None:
    folders, names = explain.matched_keywords("characters/hero.png", "PLAYER")
    assert names == ["hero"] and folders == []
    folders, names = explain.matched_keywords("npcs/guard.png", "NPC")
    assert folders == ["npcs"] and names == ["guard"]
