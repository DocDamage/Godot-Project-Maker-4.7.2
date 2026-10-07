"""Shared fixtures of the editor tools (M8): the GDScript ports in
godot_templates/addons/rpg_project_tools/tools/ must give the same answers as Python."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import catalog, ledger

FIXTURES = Path(__file__).resolve().parents[2] / "godot_templates" / "tests" / "fixtures"
HASH_VECTORS = json.loads((FIXTURES / "hash_vectors.json").read_text(encoding="utf-8"))
STATUS_CASES = json.loads((FIXTURES / "status_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", HASH_VECTORS, ids=[v["name"] for v in HASH_VECTORS])
def test_file_hash_matches_shared_vectors(vector: dict, tmp_path: Path) -> None:
    path = tmp_path / vector["file"]
    path.write_bytes(bytes.fromhex(vector["hex"]))
    assert ledger.file_hash(path) == vector["sha256"]


@pytest.mark.parametrize("case", STATUS_CASES, ids=[c["name"] for c in STATUS_CASES])
def test_recompute_status_matches_shared_cases(case: dict) -> None:
    asset = catalog.Asset(
        id="p.a",
        pack_id="p",
        path="assets/packs/p/a.png",
        sha256="0" * 64,
        kind="image",
        status=case["asset"].get("status", "AUTO_DETECTED"),
        detected=case["asset"].get("detected", {}),
        overrides=case["asset"].get("overrides", {}),
        confidence=case["asset"].get("confidence", 0.0),
        rule=case["asset"].get("rule", {}),
    )
    got = catalog.recompute_status(asset, file_missing=case.get("file_missing", False))
    assert got == case["expected"]
