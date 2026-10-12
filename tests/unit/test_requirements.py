from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from rpggen.core import archive, catalog, config, inventory, placeholders, requirements
from rpggen.errors import Severity

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(pack: str) -> catalog.Catalog:
    opened = archive.open_pack(SYNTH / pack, set())
    inv = inventory.build_inventory(opened)
    return catalog.assemble([(opened, inv)], None, [], use_cache=False)[0]


def _cfg(archetype: str = "turn_based") -> config.GeneratorConfig:
    ref = config.PackRef("x", "C:/x", "0" * 64, "folder")
    return config.default_for("T", [ref], archetype=archetype)


def _codes(issues) -> list[tuple[str, str, str]]:
    return [(i.code, i.severity.value, i.detail.get("role", "")) for i in issues]


def test_basic16_has_both_required_roles() -> None:
    issues = requirements.check(_catalog("basic16"), _cfg())
    assert not issues.has_errors()
    missing = [role for code, _, role in _codes(issues) if code == "ASSET-010"]
    assert missing == ["NPC", "ENEMY", "BUILDING", "WALL", "ITEM", "UI", "PORTRAIT"]
    assert all(i.severity is Severity.WARNING for i in issues if i.code == "ASSET-010")
    assert [i.code for i in issues if i.severity is Severity.INFO] == ["ASSET-026", "ASSET-027"]


def test_missing_required_roles_are_errors() -> None:
    issues = requirements.check(_catalog("mixed"), _cfg())  # ground + items, no player
    errors = [(c, r) for c, s, r in _codes(issues) if s == "error"]
    assert errors == [("ASSET-010", "PLAYER")]
    assert issues.has_errors()
    issues = requirements.check(_catalog("strips"), _cfg("arpg"))  # player but no ground
    assert [(c, r) for c, s, r in _codes(issues) if s == "error"] == [("ASSET-010", "GROUND")]
    assert "the starter map" in next(i.message for i in issues if i.severity is Severity.ERROR)


def test_a_farm_needs_a_player_and_ground_and_gets_the_rest_drawn() -> None:
    """T17.02. The kind is asked for by its name: the tables do not wait for the config's."""
    issues = requirements.check(_catalog("basic16"), _cfg("farm"))
    assert not issues.has_errors()
    drawn = {i.detail["role"] for i in issues if i.code == "ASSET-031"}
    assert {"CROP", "ANIMAL", "TOOL"} <= drawn
    assert all(i.severity is Severity.INFO for i in issues if i.code == "ASSET-031")
    missing = [role for code, _, role in _codes(issues) if code == "ASSET-010"]
    assert missing == ["BUILDING", "NPC", "DECORATION", "WALL", "UI", "PORTRAIT"]
    issues = requirements.check(_catalog("mixed"), _cfg("farm"))  # ground + items, no player
    assert [(c, r) for c, s, r in _codes(issues) if s == "error"] == [("ASSET-010", "PLAYER")]
    issues = requirements.check(_catalog("strips"), _cfg("farm"))  # player but no ground
    assert [(c, r) for c, s, r in _codes(issues) if s == "error"] == [("ASSET-010", "GROUND")]
    message = next(i.message for i in issues if i.severity is Severity.ERROR)
    assert "the farmyard, the field and the village" in message


def test_unused_and_missing_assets_do_not_count() -> None:
    cat = _catalog("basic16")
    cat.asset("basic16.characters.hero").overrides = {"role": "NONE"}
    cat.asset("basic16.characters.hero").status = "UNUSED"
    issues = requirements.check(cat, _cfg())
    assert [(c, r) for c, s, r in _codes(issues) if s == "error"] == [("ASSET-010", "PLAYER")]


def test_several_players_without_confirmation_warn() -> None:
    cat = _catalog("rpgmaker_like")  # eight Actor characters; c0 is PLAYER, others NPC
    cat.asset("rpgmaker_like.img.characters.actor1#c1").overrides = {"role": "PLAYER"}
    cat.asset("rpgmaker_like.img.characters.actor1#c1").status = "NEEDS_REVIEW"
    cat.asset("rpgmaker_like.img.characters.actor1#c0").status = "NEEDS_REVIEW"
    issues = requirements.check(cat, _cfg())
    warn = [i for i in issues if i.code == "ASSET-014"]
    assert len(warn) == 1 and "actor1#c0" in warn[0].message
    cat.asset("rpgmaker_like.img.characters.actor1#c1").status = "CONFIRMED"
    assert not [i for i in requirements.check(cat, _cfg()) if i.code == "ASSET-014"]


# ----------------------------------------------------------------------------- placeholders


def test_character_placeholder_sheet(tmp_path: Path) -> None:
    out = placeholders.make_placeholder("PLAYER", (16, 24), tmp_path / "p.png")
    with Image.open(out) as img:
        assert img.size == (64, 96) and img.mode == "RGBA"
        # checkerboard of magenta/black with a white border on every frame
        assert img.getpixel((0, 0)) == placeholders.WHITE
        assert img.getpixel((1, 1)) == placeholders.MAGENTA
        assert img.getpixel((5, 1)) == placeholders.BLACK
        # the arrow differs per row, so the frames of different rows are not identical
        frames = [img.crop((0, r * 24, 16, (r + 1) * 24)).tobytes() for r in range(4)]
        assert len(set(frames)) == 4


def test_ground_and_generic_placeholder_sizes(tmp_path: Path) -> None:
    ground = placeholders.make_placeholder("GROUND", (16, 16), tmp_path / "g.png")
    with Image.open(ground) as img:
        assert img.size == (64, 16)
    other = placeholders.make_placeholder("ITEM", (96, 64), tmp_path / "i.png")
    with Image.open(other) as img:
        assert img.size == (96, 64)
        # large placeholders carry readable white text
        white = int((np.asarray(img) == 255).all(axis=2).sum())
        assert white > 2 * (96 + 64)


def test_placeholders_are_deterministic(tmp_path: Path) -> None:
    a = placeholders.make_placeholder("ENEMY", (24, 36), tmp_path / "a.png").read_bytes()
    b = placeholders.make_placeholder("ENEMY", (24, 36), tmp_path / "b.png").read_bytes()
    assert a == b


def test_default_sizes() -> None:
    assert placeholders.default_size("PLAYER", 16) == (16, 24)
    assert placeholders.default_size("NPC", 32) == (32, 48)
    assert placeholders.default_size("GROUND", 16) == (16, 16)


def test_add_placeholder_assets(tmp_path: Path) -> None:
    cat = _catalog("strips")  # a player exists, no ground
    written, issues = placeholders.add_placeholder_assets(
        cat, ["GROUND", "PLAYER", "WALL"], 16, tmp_path
    )
    assert sorted(p.name for p in written) == ["ground.png", "wall.png"]  # PLAYER already exists
    assert [i.code for i in issues] == ["ASSET-011", "ASSET-011"]
    ground = cat.asset("debug_placeholders.ground")
    assert ground.path == "generated/debug_placeholders/ground.png"
    assert ground.status == "CONFIRMED" and ground.detected["tags"] == ["debug_placeholder"]
    assert ground.detected["usage"] == "tiles"
    assert any(p.pack_id == "debug_placeholders" for p in cat.packs)
    assert [s["asset"] for t in cat.tilesets for s in t.sources] == ["debug_placeholders.ground"]
    assert not requirements.check(cat, _cfg()).has_errors()
    from rpggen import schema

    schema.validate("catalog", cat.to_json())
    assert (tmp_path / "generated" / "debug_placeholders" / "ground.png").exists()
    # asking again changes nothing
    again, issues2 = placeholders.add_placeholder_assets(cat, ["GROUND"], 16, tmp_path)
    assert again == [] and list(issues2) == []


def test_placeholder_player_sheet_has_animations(tmp_path: Path) -> None:
    cat = _catalog("mixed")
    placeholders.add_placeholder_assets(cat, ["PLAYER"], 32, tmp_path)
    player = catalog.effective(cat.asset("debug_placeholders.player"))
    assert player["frame"] == [32, 48] and player["origin"] == [16, 47]
    assert sorted(player["animations"]) == sorted(
        f"{a}_{d}" for a in ("walk", "idle") for d in ("down", "left", "right", "up")
    )
    assert player["animations"]["walk_left"]["frames"] == [[0, 1], [1, 1], [2, 1], [3, 1]]
