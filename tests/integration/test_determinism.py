from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from pathlib import Path

import pytest

from rpggen.core import config, orchestrator

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "test_packs" / "synthetic" / "basic16"
SIDE_PACK = REPO / "test_packs" / "synthetic" / "platformer"

# Excluded from the comparison: logs, Godot's import cache and *.import files.
EXCLUDED = ("rpggen/logs/*", ".godot/*", "*.import")
UNIQUE_ID = re.compile(rb"unique_id=\d+")
UID_ATTR = re.compile(rb'uid="uid://[a-z0-9]+"')


def _normalized(rel: str, data: bytes) -> bytes:
    if rel.startswith("generated/i18n/") and rel.endswith(".tres"):
        # Godot writes a Translation's messages in the order of its StringNames in memory, which
        # is not the same on every run: the same lines, in any order, are the same table.
        return b"\n".join(sorted(data.splitlines()))
    if rel == "rpggen/world_plan.json":
        # the plan records the hash of every map it built, raw bytes with Godot's random ids
        doc = json.loads(data)
        for entry in doc.get("maps", {}).values():
            entry["map_hash"] = "x"
        return json.dumps(doc, sort_keys=True, indent=1).encode("utf-8")
    if rel.endswith((".tscn", ".tres")):
        # Godot 4.7 writes a random unique_id per node on every save.
        return UID_ATTR.sub(b'uid="uid://x"', UNIQUE_ID.sub(b"unique_id=0", data))
    if rel.startswith("rpggen/results/") and rel.endswith(".json"):
        doc = json.loads(data)
        doc["elapsed_ms"] = 0
        for item in doc.get("items", []):
            if "ms" in item:
                item["ms"] = 0
        return json.dumps(doc, sort_keys=True, indent=1).encode("utf-8")
    if rel == "rpggen/generation_report.json":
        doc = json.loads(data)
        doc["run_id"] = "x"  # a new one for every run, by design (T12.24)
        return json.dumps(doc, sort_keys=True, indent=1).encode("utf-8")
    if rel == "rpggen/ownership_ledger.json":
        # the ledger hashes the raw bytes of Godot-saved files, which carry random ids
        doc = json.loads(data)
        for path, entry in doc["files"].items():
            if path.endswith((".tscn", ".tres")) or path == "rpggen/world_plan.json":
                entry["sha256"] = "x"
        return json.dumps(doc, sort_keys=True, indent=1).encode("utf-8")
    return data


def _tree_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, pat) for pat in EXCLUDED):
            continue
        out[rel] = hashlib.sha256(_normalized(rel, p.read_bytes())).hexdigest()
    return out


def _same_twice(godot_exe: Path, tmp_path: Path, cfg: config.GeneratorConfig) -> dict[str, str]:
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    results = []
    for name in ("run_a", "run_b"):
        result = orchestrator.run(cfg_path, tmp_path / name, godot_exe)
        assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
        results.append(_tree_hashes(tmp_path / name))
    a, b = results
    assert sorted(a) == sorted(b)
    assert len(a) > 30
    differing = sorted(k for k in a if a[k] != b[k])
    assert differing == []
    return a


def test_determinism_basic16(godot_exe: Path, tmp_path: Path) -> None:
    _same_twice(godot_exe, tmp_path, orchestrator.default_config_for_pack(PACK, "Determinism"))


@pytest.mark.metroidvania
def test_determinism_of_a_metroidvania(godot_exe: Path, tmp_path: Path) -> None:
    """The rooms come from the planner (Python, seeded) and the recipes that paint them: two
    runs give the same plan, the same rooms and the same side kit."""
    cfg = orchestrator.default_config_for_pack(SIDE_PACK, "Determinism", archetype="metroidvania")
    files = _same_twice(godot_exe, tmp_path, cfg)
    assert "rpggen/world_plan.json" in files
    assert sum(1 for rel in files if rel.startswith("game/maps/rooms/")) == 6
