"""Custom sound slots and footsteps by surface reach the generated project (T13.16)."""

from __future__ import annotations

import shutil
import wave
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, mapping, orchestrator, sound_slots

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
BASIC16 = REPO / "test_packs" / "synthetic" / "basic16"


def _wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(bytes(2) * 1600)


def test_the_bank_has_the_custom_slots_and_the_ground_its_surface(
    godot_exe: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    pack = tmp_path / "steps"
    shutil.copytree(BASIC16, pack)
    # the ground of the pack is grass, by its folder
    (pack / "tiles" / "grass").mkdir()
    shutil.move(str(pack / "tiles" / "terrain.png"), str(pack / "tiles" / "grass" / "terrain.png"))
    for name in ("step", "step_grass", "magic"):
        _wav(pack / "sfx" / f"{name}.wav")
    opened = archive.open_pack(pack, set(), pack_id="steps")
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    ground = next(a for a in cat.assets if a.path.endswith("grass/terrain.png"))
    assert sound_slots.surface_of(ground) == "grass"
    cfg = config.default_for("Steps", [config.pack_ref_from_source(pack, "steps")])
    cfg.starter = mapping.default_starter(cat, "turn_based")
    cfg.sounds = {
        **sound_slots.default_sounds(cat),
        "sfx_magic": "steps.sfx.magic",
        "sfx_later": "",  # a custom slot without a sound yet
    }
    assert cfg.sounds["sfx_step_grass"] == "steps.sfx.step_grass"
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, None, target, godot_exe)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    bank = jsonio.read(target / "rpggen/sound_bank.json")
    assert bank["sfx_magic"].endswith("sfx/magic.wav")
    assert bank["sfx_step_grass"].endswith("sfx/step_grass.wav")
    assert bank["sfx_step"].endswith("sfx/step.wav")
    assert "sfx_later" not in bank, "a slot without a sound is silent"
    assert jsonio.read(target / "rpggen/surfaces.json") == {ground.id: "grass"}
    stored = jsonio.read(target / "rpggen/generator_config.json")["sounds"]
    assert stored["sfx_magic"] == "steps.sfx.magic" and stored["sfx_later"] == ""
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "  - `sfx_later`\n  - `sfx_magic`\n  - `sfx_step_grass`" in readme
    ledger = jsonio.read(target / "rpggen/ownership_ledger.json")
    assert ledger["files"]["rpggen/surfaces.json"]["owner"] == "generated"
