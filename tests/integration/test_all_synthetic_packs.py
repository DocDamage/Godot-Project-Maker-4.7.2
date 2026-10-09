from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import archive, catalog, config, inventory, orchestrator, requirements

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
PACKS = sorted(p for p in SYNTH.iterdir() if p.is_dir() or p.suffix == ".zip")


def _missing_required(pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "analysis_cache"))
    opened = archive.open_pack(pack, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = orchestrator.default_config_for_pack(pack, "x")
    return [i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"]


@pytest.mark.parametrize("pack", PACKS, ids=[p.stem for p in PACKS])
def test_pack_generates_end_to_end(
    pack: Path, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Packs with a PLAYER and GROUND generate as they are; for the others the missing
    required roles are filled with debug placeholders so the rest of the pipeline is exercised."""
    missing = _missing_required(pack, tmp_path, monkeypatch)
    cfg = orchestrator.default_config_for_pack(pack, "Synthetic " + pack.stem)
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    result = orchestrator.run(cfg_path, tmp_path / "out", godot_exe, placeholders=missing)
    assert result.ok, [
        f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"
    ]
    assert (result.target / "game" / "maps" / "starter_map.tscn").exists()
    assert not (result.target / ".rpggen_staging").exists()


@pytest.mark.metroidvania
@pytest.mark.parametrize("pack", PACKS, ids=[p.stem for p in PACKS])
def test_pack_generates_as_a_metroidvania(
    pack: Path, godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T14.11: every synthetic pack makes a metroidvania that validates and plays, whatever it
    has: a top-down pack gets the side kit (platforms, ladders, spikes) in its tile size, a pack
    without enemies gets its first ability as a pickup, and missing required roles get debug
    placeholders as above."""
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "analysis_cache"))
    opened = archive.open_pack(pack, set())
    cat, _, _ = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = orchestrator.default_config_for_pack(
        pack, "Side " + pack.stem, tile_size=catalog.dominant_tile_size(cat) or 16,
        archetype="metroidvania",
    )  # fmt: skip
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    cfg_path = tmp_path / "cfg.json"
    config.save(cfg, cfg_path)
    result = orchestrator.run(cfg_path, tmp_path / "out", godot_exe, placeholders=missing)
    assert result.ok, [
        f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"
    ]
    rooms = sorted(p.name for p in (result.target / "game" / "maps" / "rooms").glob("*.tscn"))
    assert len(rooms) == 6
    assert not (result.target / "game" / "maps" / "starter_map.tscn").exists()
    assert not (result.target / ".rpggen_staging").exists()
