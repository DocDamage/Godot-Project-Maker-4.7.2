"""The first paragraph of a generated README says what the project is, for each of the seven
kinds (the template's sentence was written for the two RPGs: it called a race "a **racing** RPG
starter" with "a talking NPC, a chest"); and the racing README's list of a track's nodes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import catalog, config, staging

KINDS = ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing", "farm")
# what the opening calls the kind
NAMED = {
    "turn_based": "a **turn_based** RPG starter",
    "arpg": "an **arpg** RPG starter",
    "metroidvania": "a **metroidvania** starter",
    "shmup": "a **shoot 'em up** starter",
    "run_and_gun": "a **run and gun** starter",
    "racing": "a **racing game** starter",
    "farm": "a **farm** game starter",
}
# the opening of the two RPGs, as every release since 1.0 wrote it
RPG_PARAGRAPH = (
    "This is a Godot game project made with rpggen. It is a **{kind}** RPG starter: a small\n"
    "map, a player you can walk around with, a talking NPC, a chest, a title screen, a pause "
    "menu and\nsaving and loading. Everything is yours to change."
)


def _readme(tmp_path: Path, archetype: str) -> str:
    pack = config.PackRef("pack_a", "x", "0" * 64, "folder")
    stg = staging.create_staging(tmp_path / archetype)
    cfg = config.default_for("Some Game", [pack], archetype=archetype)
    staging.write_project_files(stg, cfg, catalog.Catalog())
    return (stg.staging / "README.md").read_text(encoding="utf-8")


def _opening(text: str) -> str:
    """The first paragraph after the title."""
    return text.split("\n\n")[1]


def test_the_seven_kinds_are_the_kinds_there_are() -> None:
    assert set(KINDS) == set(staging.ARCHETYPES)


@pytest.mark.parametrize("kind", KINDS)
def test_the_opening_names_the_kind_rightly(tmp_path: Path, kind: str) -> None:
    text = _readme(tmp_path, kind)
    first = _opening(text)
    assert first.startswith("This is a Godot game project made with rpggen. It is a")
    article = "an" if kind == "arpg" else "a"
    named = NAMED[kind].split(" ", 1)[1]
    assert f"It is a {named}" in first or f"It is {article} {named}" in first, first
    assert first.endswith("Everything is yours to change."), first
    assert "{" not in first and all(len(line) <= 100 for line in first.split("\n"))
    if kind in ("turn_based", "arpg"):
        assert first == RPG_PARAGRAPH.format(kind=kind), "a released RPG's README is unchanged"
    else:
        assert "RPG starter" not in first, "only the two RPGs are RPG starters"
        assert "_" not in first, "the kind is named in words, not by its key"
    if kind in config.ARCADE_KINDS:
        # nobody to talk to and nothing to open in a shoot 'em up, a run and gun or a race
        for words in ("talking NPC", "a chest", "saving and loading", "a small\nmap"):
            assert words not in first, (kind, words)
        flat = " ".join(first.split())
        assert "the high scores" in flat or "with high scores" in flat
        assert "a pause menu" in flat
    if kind == "farm":
        assert "a chest" not in first and "crops to grow and sell" in first
    # the paragraph of the kind follows as it did
    note = staging.KIND_NOTES.get(kind, "")
    assert text.split("\n\n")[2].startswith(note.strip().split("\n")[0])


def test_the_racing_readme_says_which_nodes_of_a_track_may_be_missing() -> None:
    """The track recipes drop a layer that has nothing in it (``_keep``); only the ground is in
    every track. The README named the five as if each track had them all."""
    files = paths.templates_root()
    text = (files / "project_files" / "README.racing.md").read_text(encoding="utf-8")
    recipes = files / "builder" / "recipes" / "racing"
    dropped: set[str] = set()
    for name in ("track_recipe.gd", "iso_track.gd"):
        source = (recipes / name).read_text(encoding="utf-8")
        assert "if layer.get_child_count() == 0:\n\t\tlayer.free()" in source, name
        dropped |= set(re.findall(r'_keep\(root, \w+, "(\w+)"', source))
    assert {"Road", "Marks", "Walls", "Scenery"} >= dropped >= {"Road", "Marks"}
    passage = text[text.index("**Ground**, **Road**, **Marks**") :].split("\n- ")[0]
    assert "only\n  when the track has something for them" in passage
    assert "Of these only\n  **Ground** is in every track" in passage
    for node in sorted(dropped | {"Scenery"}):
        assert passage.count(f"**{node}**") >= 2, f"{node} is named as one that may be missing"
