"""T17.11: the generated README of a farm has the kind's sentence and its own section 22."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rpggen import paths
from rpggen.core import catalog, config, crop_plan, people_plan, staging


def _readme(tmp_path: Path, archetype: str) -> str:
    pack = config.PackRef("pack_a", "x", "0" * 64, "folder")
    stg = staging.create_staging(tmp_path / archetype)
    cfg = config.default_for("Green Acre", [pack], archetype=archetype)
    staging.write_project_files(stg, cfg, catalog.Catalog())
    return (stg.staging / "README.md").read_text(encoding="utf-8")


def test_the_readme_of_a_farm_has_its_sentence_and_its_section(tmp_path: Path) -> None:
    text = _readme(tmp_path, "farm")
    assert "## 22. Days, crops, the shop and the people (farm)" in text
    assert "Everything is yours to change.\n\n**This game is a farm**" in text
    assert "{kind_note}" not in text
    assert text.count("## 22.") == 1
    section = text.split("## 22.")[1]
    for words in (
        "### A day",
        "### Energy",
        "### Crops",
        "### Money: the shipping bin and the shop",
        "### The weather and the seasons",
        "### People",
        "### Where things are",
        "game/data/crops.json",
        "game/data/people.json",
        "game/data/shops/village_shop.tres",
        "generated/data/seasons.json",
        "rpggen/world_plan.json",
        "9:00 to 17:00",
        "rain waters your fields",
        "starter_map.pass_out_loss",
    ):
        assert words in section, words
    # the sections of the other kinds are not in it
    for other in ("racing", "shoot 'em up", "metroidvania", "turn-based"):
        assert f"({other})" not in text
    # and no other kind got the farm's
    assert "(farm)" not in _readme(tmp_path, "arpg")
    assert "This game is a farm" not in _readme(tmp_path, "turn_based")


def test_the_controls_of_the_farms_readme_are_its_default_bindings() -> None:
    text = (paths.templates_root() / "project_files" / "README.farm.md").read_text("utf-8")
    bindings = config.default_input("farm")
    rows = {
        "Use what you hold": ("use", ["Space", "J"]),
        "Talk, read": ("interact", ["E"]),
        "Next thing": ("next_item", ["R"]),
        "Previous thing": ("prev_item", ["Q"]),
        "Menu, pause": ("menu", ["Escape", "Tab"]),
    }
    for start, (action, keys) in rows.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {start}"))
        assert bindings[action]["keys"] == keys, action
        for key in keys:
            assert key in row.split("|")[2], (action, key)
    assert bindings["use"]["joy_buttons"] == [0] and bindings["interact"]["joy_buttons"] == [2]
    assert bindings["next_item"]["joy_buttons"] == [10]
    assert bindings["prev_item"]["joy_buttons"] == [9]
    assert [bindings[f"hotbar_{n}"]["keys"] for n in (1, 9, 10)] == [["1"], ["9"], ["0"]]
    assert "Space" not in bindings["interact"]["keys"]


def test_the_crop_of_the_farms_readme_is_a_real_entry() -> None:
    text = (paths.templates_root() / "project_files" / "README.farm.md").read_text("utf-8")
    found = re.search(r"```json\n(.*?)\n```", text, re.S)
    assert found is not None
    shown = json.loads(found.group(1))
    # the crops of a project whose packs have none: the three drawn ones, by their id
    drawn = sorted(name for name, _colour in crop_plan.DRAWN)
    facts = {
        "crops": [
            {"asset": f"rpggen_farm_kit.{name}", "name": name, "stages": crop_plan.DRAWN_STAGES}
            for name in drawn
        ]
    }
    section = crop_plan.plan({}, 12345, facts)
    scene = f"res://generated/scenes/farm/crops/{drawn[0]}.tscn"
    planned = crop_plan.crops_file(section, {drawn[0]: scene})["crops"][0]
    assert shown == planned
    # what the README says of the people's file is what the plan writes
    for key in ("loves", "likes", "dislikes"):
        assert key in people_plan.TASTES and f"`{key}`" in text
    assert people_plan.RAIN == "rain" and '`"rain"`' in text
