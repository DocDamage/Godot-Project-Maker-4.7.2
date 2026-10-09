"""Custom sound slots and footsteps by surface reach the generated project (T13.16)."""

from __future__ import annotations

import shutil
import wave
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, mapping, orchestrator, sound_slots
from rpggen.gui import edits

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
BASIC16 = REPO / "test_packs" / "synthetic" / "basic16"


def _wav(path: Path, seconds: float = 0.2, rate: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(2) * int(rate * seconds))


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
    for name in ("town_theme", "battle_theme"):  # long enough to be music
        _wav(pack / "music" / f"{name}.wav", seconds=24, rate=1000)
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
    # the town theme loops between two points (T13.17); the battle theme as a whole
    town = next(a for a in cat.assets if a.path.endswith("town_theme.wav"))
    battle = next(a for a in cat.assets if a.path.endswith("battle_theme.wav"))
    assert catalog.effective(town)["audio"]["loop"] is True
    cat = edits.set_override(cat, town.id, "audio", {"loop_start_ms": 2000, "loop_end_ms": 20000})
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, cat, target, godot_exe)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    bank = jsonio.read(target / "rpggen/sound_bank.json")
    assert bank["sfx_magic"].endswith("sfx/magic.wav")
    assert bank["sfx_step_grass"].endswith("sfx/step_grass.wav")
    assert bank["sfx_step"].endswith("sfx/step.wav")
    assert "sfx_later" not in bank, "a slot without a sound is silent"
    assert jsonio.read(target / "rpggen/surfaces.json") == {ground.id: "grass"}
    stored = jsonio.read(target / "rpggen/generator_config.json")["sounds"]
    assert stored["sfx_magic"] == "steps.sfx.magic" and stored["sfx_later"] == ""
    loops = jsonio.read(target / "rpggen/audio_loops.json")
    assert loops == {
        f"res://{town.path}": {"start_ms": 2000, "end_ms": 20000},
        f"res://{battle.path}": {"start_ms": 0, "end_ms": 0},
    }, "the sound effects do not loop"
    stored_catalog = jsonio.read(target / "rpggen/asset_catalog.json")
    kept = next(a for a in stored_catalog["assets"] if a["id"] == town.id)
    assert kept["overrides"]["audio"] == {"loop_start_ms": 2000, "loop_end_ms": 20000}
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "  - `sfx_later`\n  - `sfx_magic`\n  - `sfx_step_grass`" in readme
    ledger = jsonio.read(target / "rpggen/ownership_ledger.json")
    assert ledger["files"]["rpggen/surfaces.json"]["owner"] == "generated"
