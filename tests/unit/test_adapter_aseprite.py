from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, inventory
from rpggen.core.adapters import AdapterContext, naming
from rpggen.core.adapters.aseprite import AsepriteAdapter, _tag_indices

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _run(pack_dir: Path):
    pack = archive.open_pack(pack_dir, set())
    inv = inventory.build_inventory(pack)
    adapter = AsepriteAdapter()
    return (
        adapter,
        inv,
        pack.root,
        adapter.extract(inv, pack.root, AdapterContext(pack_id=inv.pack_id)),
    )


def test_aseprite_meta_pack() -> None:
    adapter, inv, root, res = _run(SYNTH / "aseprite_meta")
    assert adapter.match(inv, root) == 1.0
    assert [(f.path, f.claim, f.confidence) for f in res.assets] == [("knight.png", "full", 1.0)]
    facets = res.assets[0].facets
    assert facets["usage"] == "sprite" and facets["frame"] == [24, 32]
    anims = facets["animations"]
    assert sorted(anims) == ["idle_down", "walk_down", "walk_left", "walk_right"]

    src = json.loads((SYNTH / "aseprite_meta" / "knight.json").read_text(encoding="utf-8"))
    rects = [[f["frame"][k] for k in ("x", "y", "w", "h")] for f in src["frames"].values()]
    assert anims["idle_down"]["rects"] == rects[0:2]
    assert anims["walk_down"]["rects"] == rects[2:6]
    assert anims["walk_right"]["rects"] == rects[6:10]
    assert anims["walk_left"]["rects"] == rects[6:10]
    assert anims["walk_left"]["flip_h"] is True and "flip_h" not in anims["walk_right"]
    # idle: 200 ms -> 5 fps; walk: base 100 ms -> 10 fps; the 200 ms frame lasts twice as long
    assert anims["idle_down"]["fps"] == 5.0 and "durations" not in anims["idle_down"]
    assert anims["walk_down"]["fps"] == 10.0 and "durations" not in anims["walk_down"]
    assert anims["walk_right"]["durations"] == [1.0, 1.0, 2.0, 1.0]
    assert anims["walk_right"]["offsets"][0] == [3, 2]
    assert all(a["loop"] for a in anims.values())
    # origin: bottom-centre of the untrimmed 24x32 frame (art is bottom aligned)
    assert facets["origin"] == [12, 31]
    assert [i.code for i in res.issues] == ["ANIM-002"]
    assert res.issues[0].severity.value == "info"
    assert res.pack_warnings == []


def test_tag_directions() -> None:
    assert _tag_indices({"from": 1, "to": 4, "direction": "forward"}) == [1, 2, 3, 4]
    assert _tag_indices({"from": 1, "to": 4, "direction": "reverse"}) == [4, 3, 2, 1]
    assert _tag_indices({"from": 0, "to": 3, "direction": "pingpong"}) == [0, 1, 2, 3, 2, 1]
    assert _tag_indices({"from": 0, "to": 3, "direction": "pingpong_reverse"}) == [3, 2, 1, 0, 1, 2]
    assert _tag_indices({"from": 2, "to": 2, "direction": "pingpong"}) == [2]


def test_array_format_and_missing_direction(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    Image.new("RGBA", (32, 16), (255, 0, 0, 255)).save(tmp_path / "pk" / "s.png")
    doc = {
        "frames": [
            {
                "filename": "a",
                "frame": {"x": 0, "y": 0, "w": 16, "h": 16},
                "duration": 80,
                "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
                "sourceSize": {"w": 16, "h": 16},
            },
            {
                "filename": "b",
                "frame": {"x": 16, "y": 0, "w": 16, "h": 16},
                "duration": 80,
                "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
                "sourceSize": {"w": 16, "h": 16},
            },
        ],
        "meta": {
            "app": "https://www.aseprite.org/",
            "image": "s.png",
            "frameTags": [{"name": "Attack", "from": 0, "to": 1, "direction": "forward"}],
        },
    }
    (tmp_path / "pk" / "s.json").write_text(json.dumps(doc), encoding="utf-8")
    _, _, _, res = _run(tmp_path / "pk")
    anims = res.assets[0].facets["animations"]
    assert list(anims) == ["attack_down"]
    assert anims["attack_down"]["loop"] is False  # attack animations do not loop
    assert anims["attack_down"]["fps"] == 12.5
    assert res.pack_warnings == ["aseprite_direction_assumed:Attack"]


def test_non_aseprite_json_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    (tmp_path / "pk" / "data.json").write_text(
        '{"frames": {}, "meta": {"app": "other"}}', encoding="utf-8"
    )
    adapter, inv, root, _ = _run(tmp_path / "pk")
    assert adapter.match(inv, root) == 0.0


def test_missing_image_gives_adapt002(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    doc = {
        "frames": [{"frame": {"x": 0, "y": 0, "w": 1, "h": 1}}],
        "meta": {"app": "aseprite", "image": "gone.png"},
    }
    (tmp_path / "pk" / "x.json").write_text(json.dumps(doc), encoding="utf-8")
    _, _, _, res = _run(tmp_path / "pk")
    assert res.assets == [] and [i.code for i in res.issues] == ["ADAPT-002"]


@pytest.mark.parametrize(
    ("raw", "name", "side", "assumed"),
    [
        ("idle_down", "idle_down", False, False),
        ("Walk Side", "walk_right", True, False),
        ("run-left", "walk_left", False, False),
        ("atk_n", "attack_up", False, False),
        ("DIE", "death_down", False, True),
        ("south", "idle_down", False, False),
        ("custom_spin_e", "custom_spin_right", False, False),
        ("hit_front", "hurt_down", False, False),
    ],
)
def test_name_normalization(raw: str, name: str, side: bool, assumed: bool) -> None:
    n = naming.normalize_name(raw)
    assert (n.name, n.side, n.direction_assumed) == (name, side, assumed)


def test_looping_rules() -> None:
    assert naming.is_looping("walk") and naming.is_looping("idle")
    assert not naming.is_looping("attack") and not naming.is_looping("death")
