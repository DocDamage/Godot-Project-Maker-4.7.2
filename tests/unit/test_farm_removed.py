"""A crop, an animal, a fish or a thing to forage that the user's file takes away: the entry
``{"id": ..., "removed": true}`` is part of the four files' schemas (the game's data classes
honour it: ``godot_templates/tests/unit/test_field.gd``, ``test_farm_animals.gd``,
``test_farm_forage.gd``, ``test_friendship.gd``), and the generated README says how."""

from __future__ import annotations

import pytest

from rpggen import paths, schema
from rpggen.errors import RpgGenError

GONE = {"id": "turnip", "removed": True}
FILES = {
    "crops": {"crops": [GONE]},
    "animals": {"animals": [GONE]},
    "forage": {"forage": [GONE], "fish": [{"id": "fish_eel", "removed": True}]},
    "people": {"people": [GONE]},
}


@pytest.mark.parametrize("name", sorted(FILES))
def test_a_removed_entry_is_valid_in_the_users_file(name: str) -> None:
    schema.validate(name, FILES[name])
    for key, entries in FILES[name].items():
        # the mark is `true` and stands alone: an entry that is half a thing is still refused
        for bad in ({"id": "turnip", "removed": False}, {"id": "turnip"}, {"removed": True}):
            with pytest.raises(RpgGenError):
                schema.validate(name, {**FILES[name], key: [*entries, bad]})


def test_the_generated_readme_says_how_to_remove_a_thing() -> None:
    text = (paths.templates_root() / "project_files" / "README.farm.md").read_text(encoding="utf-8")
    assert text.count('"removed": true') >= 3, "the crops, the animals, the fish and the forage"
    for words in (
        '{ "id": "berry", "removed": true }',
        "comes back from that list",
        "a person you delete from it is gone",
    ):
        assert words in " ".join(text.split()), words
