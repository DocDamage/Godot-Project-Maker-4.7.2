from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import adapters, archive, inventory
from rpggen.core.adapters import AdapterContext, naming, sequences
from rpggen.core.adapters.sequences import SequencesAdapter
from rpggen.core.adapters.strips import STRIP_NAME, StripsAdapter

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _open(pack_dir: Path, work: Path | None = None):
    pack = archive.open_pack(pack_dir, set())
    inv = inventory.build_inventory(pack)
    return inv, pack.root, AdapterContext(pack_id=inv.pack_id, work_dir=work)


def _frame(path: Path, shade: int, size: tuple[int, int] = (8, 8)) -> None:
    """A frame whose red channel tells which one it is."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (4, 6), (shade, 0, 0, 255)), (2, 1))
    img.save(path)


def _by_path(res, path: str):
    return next(f for f in res.assets if f.path == path)


# ----------------------------------------------------------------------------- names


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("hero_walk_down_01", ("hero_walk_down", 1)),
        ("hero-walk-12", ("hero-walk", 12)),
        ("Walk 3", ("Walk", 3)),
        ("Walk (3)", ("Walk", 3)),
        ("Walk(10)", ("Walk", 10)),
        ("0001", ("", 1)),
        ("walk3", None),  # a number glued to the name belongs to the name
        ("tileset2", None),
        ("hero_walk", None),
    ],
)
def test_split_number(stem: str, expected: tuple[str, int] | None) -> None:
    assert sequences.split_number(stem) == expected


@pytest.mark.parametrize(
    ("raw", "name"),
    [
        ("walk_down_left", "walk_down_left"),
        ("walk_left_down", "walk_down_left"),
        ("idle_sw", "idle_down_left"),
        ("idle_se", "idle_down_right"),
        ("idle_nw", "idle_up_left"),
        ("idle_ne", "idle_up_right"),
        ("run-up-right", "walk_up_right"),
        ("cast_upleft", "cast_up_left"),
        ("jump", "jump_down"),
        ("swim_w", "swim_left"),
    ],
)
def test_diagonal_directions_and_new_actions(raw: str, name: str) -> None:
    assert naming.normalize_name(raw).name == name


def test_new_actions_loop_only_when_they_are_held() -> None:
    for action in ("jump", "cast", "shoot", "slash", "thrust", "roll", "dash", "interact"):
        assert not naming.is_looping(action), action
    for action in ("fall", "block", "climb", "swim"):
        assert naming.is_looping(action), action
    assert naming.fps("slash_down") == 12.0 and naming.fps("unknown") == 8.0


@pytest.mark.parametrize(
    ("stem", "action", "direction"),
    [
        ("hero_cast", "cast", None),
        ("hero_shoot_up_right", "shoot", "up_right"),
        ("hero_thrust_ne", "thrust", "ne"),
        ("hero_interact_down-left", "interact", "down-left"),
        ("orc_roll_w", "roll", "w"),
    ],
)
def test_strip_names_know_the_new_actions(stem: str, action: str, direction: str | None) -> None:
    m = STRIP_NAME.match(stem)
    assert m is not None and (m.group("action"), m.group("dir")) == (action, direction)


def test_whole_strip_with_a_diagonal_name(tmp_path: Path) -> None:
    (tmp_path / "pk").mkdir()
    strip = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for i in range(4):
        strip.paste(Image.new("RGBA", (6, 10), (200, 0, 0, 255)), (i * 16 + 5, 3))
    strip.save(tmp_path / "pk" / "orc_dash_down_left.png")
    inv, root, ctx = _open(tmp_path / "pk")
    res = StripsAdapter().extract(inv, root, ctx)
    anims = res.assets[0].facets["animations"]
    assert list(anims) == ["dash_down_left"] and anims["dash_down_left"]["loop"] is False


# ----------------------------------------------------------------------------- the adapter


def test_registered_before_strips() -> None:
    adapters.register_defaults()
    names = [a.name for a in adapters.get_adapters()]
    assert names.index("lpc") < names.index("sequences") < names.index("strips")


def test_frames_play_in_numeric_order(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in range(1, 12):  # no zero padding: "hero_walk_10" sorts before "hero_walk_2" as text
        _frame(pk / f"hero_walk_{n}.png", n * 10)
    inv, root, ctx = _open(pk, tmp_path / "work")
    adapter = SequencesAdapter()
    assert adapter.match(inv, root) == 1.0
    res = adapter.extract(inv, root, ctx)
    frag = _by_path(res, "hero_walk_1.png")
    assert frag.claim == "full" and frag.facets["usage"] == "sprite"
    assert frag.facets["frame"] == [8, 8] and frag.facets["origin"] == [4, 6]
    assert "directions" not in frag.facets
    anim = frag.facets["animations"]["walk_down"]
    assert anim["frames"] == [[i, 0] for i in range(11)]
    assert anim["fps"] == 8.0 and anim["loop"] is True
    assert sorted(res.consumed) == sorted(f"hero_walk_{n}.png" for n in range(2, 12))
    assert res.issues == []
    assert res.pack_warnings == ["sequences_direction_assumed:hero_walk"]
    # one atlas for the animation, the frames in playing order
    assert list(res.generated) == [anim["source"]]
    assert anim["source"].startswith("generated/frame_strips/") and anim["source"].endswith(".png")
    assert Path(res.generated[anim["source"]]).parent == tmp_path / "work" / "frame_strips"
    with Image.open(res.generated[anim["source"]]) as strip:
        assert strip.size == (88, 8)
        assert [strip.getpixel((i * 8 + 3, 3))[0] for i in range(11)] == [
            n * 10 for n in range(1, 12)
        ]


def test_the_strip_is_named_after_its_frames(tmp_path: Path) -> None:
    for pack in ("a", "b"):
        for n in (1, 2, 3):
            _frame(tmp_path / pack / f"hero_walk_{n:02d}.png", n * 20)
    _frame(tmp_path / "b" / "hero_walk_03.png", 99)
    sources = []
    for pack in ("a", "a", "b"):
        inv, root, ctx = _open(tmp_path / pack, tmp_path / "work")
        res = SequencesAdapter().extract(inv, root, ctx)
        sources.append(res.assets[0].facets["animations"]["walk_down"]["source"])
    assert sources[0] == sources[1] != sources[2]


def test_parenthesised_numbers_and_a_folder_per_animation(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2, 3):
        _frame(pk / "Knight" / f"Walk ({n}).png", n)
        _frame(pk / "Knight" / f"Attack ({n}).png", 10 + n)
        _frame(pk / "mage" / "cast" / f"{n:04d}.png", 20 + n)
        _frame(pk / "mage" / "walk" / "up" / f"{n:04d}.png", 30 + n)
        _frame(pk / "mage" / "walk" / f"left_{n}.png", 40 + n)
    inv, root, ctx = _open(pk, tmp_path / "work")
    res = SequencesAdapter().extract(inv, root, ctx)
    assert sorted(f.path for f in res.assets) == ["Knight/Attack (1).png", "mage/cast/0001.png"]
    knight = _by_path(res, "Knight/Attack (1).png").facets["animations"]
    assert sorted(knight) == ["attack_down", "walk_down"]
    assert knight["attack_down"]["loop"] is False and knight["attack_down"]["fps"] == 12.0
    mage = _by_path(res, "mage/cast/0001.png").facets["animations"]
    assert sorted(mage) == ["cast_down", "walk_left", "walk_up"]
    assert len(res.consumed) == 15 - 2 and len(res.generated) == 5


def test_a_gap_is_reported_and_the_frames_are_still_used(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2, 4, 7):
        _frame(pk / f"slime_idle_{n:02d}.png", n)
    inv, root, ctx = _open(pk, tmp_path / "work")
    res = SequencesAdapter().extract(inv, root, ctx)
    assert len(res.assets[0].facets["animations"]["idle_down"]["frames"]) == 4
    assert [i.code for i in res.issues] == ["ADAPT-004"]
    assert res.issues[0].message == (
        "The frame numbers of slime_idle have a gap (missing 3, 5, 6)."
    )
    assert res.issues[0].file == "slime_idle_01.png"


def test_eight_directions(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for direction in ("s", "sw", "w", "nw", "n", "ne", "e", "se"):
        for n in (0, 1):
            _frame(pk / f"hero_walk_{direction}_{n}.png", n)
    inv, root, ctx = _open(pk, tmp_path / "work")
    frag = SequencesAdapter().extract(inv, root, ctx).assets[0]
    assert sorted(frag.facets["animations"]) == [
        "walk_down",
        "walk_down_left",
        "walk_down_right",
        "walk_left",
        "walk_right",
        "walk_up",
        "walk_up_left",
        "walk_up_right",
    ]
    assert frag.facets["directions"] == 8


def test_side_frames_get_a_mirrored_left(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2):
        _frame(pk / f"orc_walk_side_{n}.png", n)
    inv, root, ctx = _open(pk, tmp_path / "work")
    res = SequencesAdapter().extract(inv, root, ctx)
    anims = res.assets[0].facets["animations"]
    assert sorted(anims) == ["walk_left", "walk_right"]
    assert anims["walk_left"]["flip_h"] is True and "flip_h" not in anims["walk_right"]
    assert [i.code for i in res.issues] == ["ANIM-002"]


def test_what_is_not_a_sequence_is_left_alone(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2, 3):
        _frame(pk / f"item_{n:02d}.png", n)  # no action word: variants
    _frame(pk / "hero_walk_01.png", 1)  # a single frame
    _frame(pk / "orc_walk_1.png", 1)
    _frame(pk / "orc_walk_2.png", 2, (8, 12))  # frames of different sizes
    inv, root, ctx = _open(pk, tmp_path / "work")
    adapter = SequencesAdapter()
    assert adapter.match(inv, root) == 0.0
    res = adapter.extract(inv, root, ctx)
    assert res.assets == [] and res.consumed == [] and res.generated == {}


def test_frames_of_another_size_are_another_asset(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2):
        _frame(pk / f"hero_walk_{n}.png", n)
        _frame(pk / f"hero_attack_{n}.png", n, (16, 16))
    inv, root, ctx = _open(pk, tmp_path / "work")
    res = SequencesAdapter().extract(inv, root, ctx)
    assert {f.path: f.facets["frame"] for f in res.assets} == {
        "hero_walk_1.png": [8, 8],
        "hero_attack_1.png": [16, 16],
    }


def test_claimed_frames_are_skipped(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2, 3):
        _frame(pk / f"hero_walk_{n}.png", n)
    inv, root, ctx = _open(pk, tmp_path / "work")
    ctx.claimed.update({"hero_walk_2.png", "hero_walk_3.png"})
    assert SequencesAdapter().extract(inv, root, ctx).assets == []


def test_a_long_sequence_wraps_into_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sequences, "MAX_STRIP_WIDTH", 32)
    pk = tmp_path / "pk"
    for n in range(1, 11):
        _frame(pk / f"hero_walk_{n:02d}.png", n * 10)
    inv, root, ctx = _open(pk, tmp_path / "work")
    res = SequencesAdapter().extract(inv, root, ctx)
    anim = res.assets[0].facets["animations"]["walk_down"]
    assert anim["frames"] == [[i % 4, i // 4] for i in range(10)]
    with Image.open(res.generated[anim["source"]]) as strip:
        assert strip.size == (32, 24)
        assert strip.getpixel((1 * 8 + 3, 2 * 8 + 3))[0] == 100  # the tenth frame


def test_an_unreadable_frame_is_an_adapter_warning(tmp_path: Path) -> None:
    pk = tmp_path / "pk"
    for n in (1, 2):
        _frame(pk / f"hero_walk_{n}.png", n)
    inv, root, ctx = _open(pk, tmp_path / "work")
    (root / "hero_walk_2.png").write_bytes(b"not a png")
    res = SequencesAdapter().extract(inv, root, ctx)
    assert res.assets == [] and [i.code for i in res.issues] == ["ADAPT-001"]


# ----------------------------------------------------------------------------- the pack


def test_sequences_pack() -> None:
    inv, root, ctx = _open(SYNTH / "sequences")
    adapter = SequencesAdapter()
    assert adapter.match(inv, root) == 1.0
    res = adapter.extract(inv, root, ctx)
    assert sorted(f.path for f in res.assets) == [
        "enemies/bat/attack/0001.png",
        "hero-cast-1.png",
        "skeleton_idle_01.png",
        "slime/Idle (1).png",
    ]
    hero = _by_path(res, "hero-cast-1.png").facets
    assert hero["directions"] == 8 and len(hero["animations"]["walk_down"]["frames"]) == 10
    assert hero["animations"]["walk_left"]["flip_h"] is True
    bat = _by_path(res, "enemies/bat/attack/0001.png").facets
    assert bat["frame"] == [24, 24] and sorted(bat["animations"]) == ["attack_down", "walk_down"]
    assert sorted(i.code for i in res.issues) == ["ADAPT-004", "ANIM-002"]
    assert not any(p.startswith("items/") for p in res.consumed)
    images = [f for f in inv.files if f.kind == "image"]
    assert len(res.consumed) + len(res.assets) == len(images) - 3  # the three gems


@pytest.mark.parametrize("pack", ["basic16", "mixed", "strips", "rpgmaker_like", "aseprite_meta"])
def test_other_packs_do_not_match(pack: str) -> None:
    inv, root, _ctx = _open(SYNTH / pack)
    assert SequencesAdapter().match(inv, root) == 0.0
