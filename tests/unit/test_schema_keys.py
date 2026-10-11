"""No schema file has a key twice in one object.

JSON allows it and the last one wins without a word: a second ``size`` among the options of the
starter map once replaced the first (T16.13), and only the tests of the Options page noticed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMAS = sorted((Path(__file__).resolve().parents[2] / "rpggen" / "schema").glob("*.json"))


def _no_key_twice(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _value in pairs]
    twice = sorted({key for key in keys if keys.count(key) > 1})
    assert not twice, f"twice in one object: {', '.join(twice)}"
    return dict(pairs)


def test_there_are_schemas_to_look_at() -> None:
    assert len(SCHEMAS) >= 5


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda p: p.name)
def test_no_object_of_a_schema_has_a_key_twice(path: Path) -> None:
    json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_key_twice)


def test_the_check_finds_a_key_that_is_there_twice() -> None:
    with pytest.raises(AssertionError, match="twice in one object: size"):
        json.loads('{"a": {"size": 1, "b": 2, "size": 3}}', object_pairs_hook=_no_key_twice)
