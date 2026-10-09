"""A recolour variant of the sample pack's slime becomes an enemy of the game (T13.18)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image

from rpggen import jsonio
from rpggen.core import (
    archive,
    catalog,
    config,
    inventory,
    mapping,
    orchestrator,
    profiles,
    variants,
)
from rpggen.gui import edits

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "sample_pack"


@pytest.mark.parametrize("archetype", ["turn_based", "arpg"])
def test_a_variant_enemy_has_its_definition_and_is_not_placed(
    godot_exe: Path, tmp_path: Path, monkeypatch, archetype: str
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    slime = next(a for a in cat.assets if a.path.endswith("slime_idle.png"))
    definition = variants.normalized(
        {
            "id": variants.new_id({a.id for a in cat.assets}, slime.pack_id, "Fire slime"),
            "source": slime.id,
            "name": "Fire slime",
            "op": "hue",
            "params": {"shift": 120, "saturation": 1.0, "value": 1.0},
            "stats": {"hp": 2.0, "attack": 1.5, "xp": 2.0, "gold": 3.0},
        }
    )
    cat = edits.add_variant(cat, definition, {"sample_pack": Path(opened.root)})
    assert cat.asset(definition["id"]) is not None
    cfg = config.default_for(
        "Variants", [config.pack_ref_from_source(SAMPLE, "sample_pack")], archetype=archetype
    )
    cfg.starter = mapping.default_starter(cat, archetype)
    assert cfg.starter["enemy"] == slime.id, "the pack's own slime stays the starter enemy"
    target = tmp_path / "out"
    result = orchestrator.run_in_memory(cfg, cat, target, godot_exe)
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    assert not [i for i in result.issues if i.code == "ASSET-029"]

    # the recoloured picture is in the project, owned by the generator
    picture = target / "generated/variants/sample_pack_variants_fire_slime.png"
    with Image.open(picture) as out, Image.open(SAMPLE / "enemies" / "slime_idle.png") as src:
        assert out.size == src.size
        assert out.convert("RGBA").tobytes() != src.convert("RGBA").tobytes()
    ledger = jsonio.read(target / "rpggen/ownership_ledger.json")
    rel = "generated/variants/sample_pack_variants_fire_slime.png"
    assert ledger["files"][rel]["owner"] == "generated"
    stored = jsonio.read(target / "rpggen/asset_catalog.json")
    assert [v["name"] for v in stored["variants"]] == ["Fire slime"]

    # its enemy definition: the name, and the source's stats times the multipliers
    base = (target / "game/data/enemies/slime_idle.tres").read_text(encoding="utf-8")
    fire = (target / "game/data/enemies/fire_slime.tres").read_text(encoding="utf-8")

    def number(text: str, key: str) -> int:
        found = re.search(rf"^{key} = (\d+)$", text, re.M)
        assert found, key
        return int(found.group(1))

    assert 'display_name = "Fire slime"' in fire
    assert number(fire, "max_hp") == 2 * number(base, "max_hp")
    assert number(fire, "attack") == round(1.5 * number(base, "attack"))
    # the first enemy gives 5 XP and 3 gold (the definition's defaults, so not in its file)
    assert "xp_reward" not in base and "gold_reward" not in base
    assert number(fire, "xp_reward") == 2 * 5
    assert number(fire, "gold_reward") == 3 * 3
    assert "sample_pack.variants.fire_slime" in fire, "it uses the variant's own SpriteFrames"
    assert (target / "generated/scenes/enemies/fire_slime.tscn").is_file()
    assert ledger["files"]["game/data/enemies/fire_slime.tres"]["owner"] == "user_seed"

    # nothing of it is placed on the demo maps
    for scene in (target / "game" / "maps").glob("*.tscn"):
        assert "fire_slime" not in scene.read_text(encoding="utf-8"), scene.name

    # a second generation changes neither the picture nor the definition
    before = (picture.read_bytes(), fire)
    again = orchestrator.run_in_memory(cfg, cat, target, godot_exe)
    assert again.ok, [f"{i.code}: {i.message}" for i in again.issues]
    after_fire = (target / "game/data/enemies/fire_slime.tres").read_text(encoding="utf-8")
    assert (picture.read_bytes(), after_fire) == before
