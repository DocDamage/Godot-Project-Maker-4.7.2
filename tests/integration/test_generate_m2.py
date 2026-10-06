from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen.core import config, orchestrator

pytestmark = pytest.mark.integration

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _run(godot_exe: Path, tmp_path: Path, pack: str, name: str, placeholders=None):
    cfg = orchestrator.default_config_for_pack(SYNTH / pack, name)
    cfg_path = tmp_path / f"{name}_cfg.json"
    config.save(cfg, cfg_path)
    return orchestrator.run(cfg_path, tmp_path / name, godot_exe, placeholders=placeholders)


def test_missing_required_role_stops_before_godot_runs(godot_exe: Path, tmp_path: Path) -> None:
    result = _run(godot_exe, tmp_path, "mixed", "noplayer")  # ground tiles, but no PLAYER
    assert not result.ok
    errors = [i for i in result.issues if i.severity.value == "error"]
    assert [(i.code, i.detail["role"]) for i in errors] == [("ASSET-010", "PLAYER")]
    assert result.failed_staging is not None
    logs = result.failed_staging / "rpggen" / "logs"
    assert not list(logs.glob("godot_*.log")), "Godot must not run when a required role is missing"
    assert not (result.target / "project.godot").exists()


def test_placeholder_player_lets_generation_succeed(godot_exe: Path, tmp_path: Path) -> None:
    result = _run(godot_exe, tmp_path, "mixed", "placeheld", placeholders=["PLAYER"])
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    target = result.target
    assert (target / "generated/debug_placeholders/player.png").exists()
    assert (target / "generated/sprite_frames/debug_placeholders.player.tres").exists()
    assert (target / "game/maps/starter_map.tscn").exists()
    assert any(i.code == "ASSET-011" for i in result.issues)
    catalog = json.loads((target / "rpggen/asset_catalog.json").read_text(encoding="utf-8"))
    placeholder = next(a for a in catalog["assets"] if a["id"] == "debug_placeholders.player")
    assert placeholder["status"] == "CONFIRMED"
    assert "debug_placeholder" in placeholder["detected"]["tags"]


def test_zipped_generation_equals_folder_generation(godot_exe: Path, tmp_path: Path) -> None:
    folder = _run(godot_exe, tmp_path, "basic16", "from_folder")
    archive = _run(godot_exe, tmp_path, "zipped.zip", "from_zip")
    assert folder.ok and archive.ok

    def normalized(result: orchestrator.RunResult) -> str:
        text = (result.target / "rpggen/asset_catalog.json").read_text(encoding="utf-8")
        data = json.loads(text)
        pack_id = data["packs"][0]["pack_id"]
        sha = data["packs"][0]["source_sha256"]
        return text.replace(pack_id, "PACK").replace(sha, "SHA")

    assert normalized(folder) == normalized(archive)
    assert (archive.target / "assets/packs/zipped/tiles/terrain.png").read_bytes() == (
        folder.target / "assets/packs/basic16/tiles/terrain.png"
    ).read_bytes()
