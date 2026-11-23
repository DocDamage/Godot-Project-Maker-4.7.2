"""Shared hazards must compile in projects that do not install the side-view runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import orchestrator

pytestmark = pytest.mark.integration
REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("archetype", ["turn_based", "arpg"])
def test_top_down_generation_has_no_side_runtime_dependency(
    godot_exe, tmp_path, monkeypatch, archetype
):
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    source = REPO / "test_packs/synthetic/basic16"
    cfg = orchestrator.default_config_for_pack(
        source, "Shared Hazard Regression", archetype=archetype
    )
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(
        cfg, None, target, godot_exe, placeholders=["PLAYER", "GROUND"]
    )
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert (target / "addons/rpg_runtime/world/tile_hazards.gd").is_file()
    assert not (target / "addons/rpg_runtime/archetypes/metroidvania").exists()
