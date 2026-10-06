from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import catalog

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "godot_templates"
    / "tests"
    / "fixtures"
    / "effective_cases.json"
)
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_effective_matches_shared_fixture(case: dict) -> None:
    assert catalog.effective(case["asset"]) == case["expected"]


def test_merge_does_not_mutate_inputs() -> None:
    base = {"grid": {"cell": [16, 16]}}
    over = {"grid": {"cell": None, "margin": [1, 1]}}
    assert catalog.merge(base, over) == {"grid": {"margin": [1, 1]}}
    assert base == {"grid": {"cell": [16, 16]}}
    assert over == {"grid": {"cell": None, "margin": [1, 1]}}
