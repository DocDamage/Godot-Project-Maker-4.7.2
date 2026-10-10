"""M16, at the wish of the owner: LPC characters are recognized in the shapes they are shipped
in: the whole universal sheet, and the picture or folder per animation of the collection."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, catalog, explain, inventory, pack_sniff
from rpggen.core.adapters import lpc

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
DIRECTIONS = ("down", "left", "right", "up")


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _catalog(source: Path) -> catalog.Catalog:
    opened = archive.open_pack(source, set())
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, [], use_cache=False
    )
    return cat


def _by_path(cat: catalog.Catalog) -> dict[str, catalog.Asset]:
    return {a.path.split("/", 3)[-1]: a for a in cat.assets}


def test_the_layout_is_that_of_the_generator() -> None:
    """Rows, frames and order as the Universal LPC generator lays its sheet out."""
    rows = {a.lpc: (a.row, a.rows, a.frames) for a in lpc.ACTIONS}
    assert rows == {
        "spellcast": (0, 4, 7), "thrust": (4, 4, 8), "walk": (8, 4, 9), "slash": (12, 4, 6),
        "shoot": (16, 4, 13), "hurt": (20, 1, 6), "climb": (21, 1, 6), "idle": (22, 4, 2),
        "jump": (26, 4, 5), "sit": (30, 4, 3), "emote": (34, 4, 3), "run": (38, 4, 8),
        "combat_idle": (42, 4, 2), "backslash": (46, 4, 13), "halfslash": (50, 4, 6),
    }  # fmt: skip
    last = lpc.ACTIONS[-1]
    assert (last.row + last.rows) * lpc.FRAME == 3456 and lpc.LPC_DIRECTIONS[2] == "down"


def test_the_classic_sheet_has_every_animation_that_is_drawn_on_it() -> None:
    cat = _catalog(SYNTH / "lpc_like")
    body = catalog.effective(_by_path(cat)["characters/body.png"])
    anims = body["animations"]
    for action in ("walk", "idle", "attack", "cast", "thrust", "shoot"):
        assert all(f"{action}_{d}" in anims for d in DIRECTIONS), action
    assert anims["cast_down"]["frames"] == [[c, 2] for c in range(7)]
    assert anims["thrust_left"]["frames"] == [[c, 5] for c in range(8)]
    assert anims["shoot_right"]["frames"] == [[c, 19] for c in range(13)]
    assert not anims["shoot_right"]["loop"] and "source" not in anims["shoot_right"]
    # what it had before M16 is what it was
    assert anims["walk_down"]["frames"] == [[c, 10] for c in range(1, 9)]
    assert anims["idle_right"] == {"frames": [[0, 11]], "fps": 1.0, "loop": True}
    assert anims["attack_left"]["active_frames"] == [3, 4]
    assert "climb_up" not in anims and "run_down" not in anims, "21 rows: nothing below"


def test_the_sheet_of_the_generator_goes_on_under_the_classic_rows() -> None:
    cat = _catalog(SYNTH / "lpc_parts")
    guard = catalog.effective(_by_path(cat)["characters/guard.png"])
    anims = guard["animations"]
    assert anims["climb_up"]["frames"] == [[c, 21] for c in range(6)] and anims["climb_up"]["loop"]
    assert anims["idle_down"]["frames"] == [[0, 24], [0, 24], [1, 24]], "its own idle rows"
    assert "cast_down" not in anims and "shoot_down" not in anims, "rows with nothing drawn"
    assert "jump_down" not in anims, "rows the sheet does not have"


def test_the_files_of_one_thing_of_the_collection_are_one_sprite() -> None:
    cat = _catalog(SYNTH / "lpc_parts")
    assets = _by_path(cat)
    body_files = [p for p in assets if p.startswith("spritesheets/body/")]
    assert body_files == ["spritesheets/body/bodies/male/walk.png"], "the walk stands for all"
    body = assets[body_files[0]]
    eff = catalog.effective(body)
    assert body.detected_by == "lpc" and eff["frame"] == [64, 64] and eff["origin"] == [32, 60]
    assert eff["tags"] == ["lpc_body"] and body.status != "UNUSED"
    anims = eff["animations"]
    root = "assets/packs/lpc_parts/spritesheets/body/bodies/male"
    assert anims["walk_down"] == {
        "frames": [[c, 2] for c in range(1, 9)],
        "fps": 10.0,
        "loop": True,
        "source": f"{root}/walk.png",
    }
    assert anims["run_up"]["source"] == f"{root}/run.png" and anims["run_up"]["frames"][0] == [0, 0]
    assert anims["jump_right"]["frames"] == [[c, 3] for c in (0, 1, 2, 3, 4, 1)]
    assert anims["idle_left"]["source"] == f"{root}/idle.png"
    assert anims["hurt"]["source"] == f"{root}/hurt.png" and anims["death"]["fps"] == 8.0
    assert anims["climb_up"]["source"] == f"{root}/climb.png"
    assert anims["cast_down"]["source"] == f"{root}/spellcast.png"
    assert anims["attack_down"]["source"] == f"{root}/slash.png"


def test_a_layer_is_read_and_left_unused_with_its_reason() -> None:
    cat = _catalog(SYNTH / "lpc_parts")
    assets = _by_path(cat)
    hair = assets["spritesheets/hair/afro/adult/walk.png"]
    eff = catalog.effective(hair)
    assert hair.status == "UNUSED" and eff["role"] == "NONE"
    assert {"lpc_layer", "lpc_part:hair"} <= set(eff["tags"])
    assert "a layer of an LPC character" in explain.why(hair)
    assert "attack_down" in eff["animations"] and "death" in eff["animations"]
    assert "idle_down" in eff["animations"], "no idle file: it stands on its walk"
    # a folder per animation, a picture per colour: one layer per colour
    shirts = sorted(p for p in assets if "/shirt/" in p)
    assert shirts == [
        "spritesheets/torso/clothes/shirt/male/walk/blue.png",
        "spritesheets/torso/clothes/shirt/male/walk/red.png",
    ]
    red = catalog.effective(assets[shirts[1]])
    assert "lpc_part:torso" in red["tags"]
    assert red["animations"]["attack_up"]["source"].endswith("/male/slash/red.png")
    assert red["animations"]["walk_up"]["source"].endswith("/male/walk/red.png")
    # a role given in the audit brings a layer back
    hair.overrides["role"] = "NPC"
    assert catalog.recompute_status(hair) == "CONFIRMED"


def test_a_picture_of_another_size_is_no_animation_of_the_collection(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    for name, size in {
        "hero/walk.png": (576, 256),
        "big/walk.png": (1152, 768),  # 192 px frames: the oversize sheet of a weapon
        "wide/walk.png": (640, 256),  # ten frames: a walk has nine
        "icons/hurt.png": (32, 32),
        "notes/idle.jpg": (128, 256),
    }.items():
        (pack / name).parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA" if name.endswith("png") else "RGB", size, (90, 60, 30)).save(pack / name)
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    found = {f.path: lpc.action_of(f) for f in inv.files}
    assert found["hero/walk.png"] is not None and found["hero/walk.png"][0].lpc == "walk"
    assert [p for p, a in found.items() if a is not None] == ["hero/walk.png"]


@pytest.mark.parametrize(
    ("path", "part"),
    [
        ("spritesheets/body/bodies/male/walk.png", "body"),
        ("spritesheets/hair/afro/adult/walk.png", "hair"),
        ("spritesheets/torso/clothes/shirt/male/walk/red.png", "torso"),
        ("Weapon/blunt/mace/walk/mace.png", "weapon"),
        ("my_hero/walk.png", None),
        ("walk.png", None),
    ],
)
def test_the_part_of_a_character_is_its_folder(path: str, part: str | None) -> None:
    assert lpc.part_of(path) == part


def test_the_collection_is_told_from_its_listing() -> None:
    assert pack_sniff.sniff(SYNTH / "lpc_parts").format == "lpc"
    assert pack_sniff.sniff(SYNTH / "lpc_like").format == "lpc"
    assert lpc.looks_like_collection(["a/walk.png", "a/slash.png", "a/hurt.png"])
    assert lpc.looks_like_collection(["a\\walk\\red.png", "a/slash/red.png", "a/idle/red.png"])
    assert not lpc.looks_like_collection(["a/walk.png", "a/slash.png", "tiles/grass.png"])
    assert not lpc.looks_like_collection(["walk.txt", "slash.txt", "hurt.txt"])
    for name in ("basic16", "strips", "platformer", "racer"):
        assert pack_sniff.sniff(SYNTH / name).format != "lpc", name
