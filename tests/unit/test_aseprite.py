"""T16.21: the binary ``.aseprite`` file, and what it says about the frames exported from it."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, inventory
from rpggen.core.adapters import AdapterContext, sequences
from rpggen.core.adapters import aseprite_file as ase
from rpggen.core.adapters.aseprite_file import Tag
from rpggen.core.adapters.sequences import SequencesAdapter


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


TAGS = [
    Tag("Idle", 0, 3, "forward", 0),
    Tag("walk", 4, 9, "pingpong", 0),
    Tag("Attack", 10, 11, "reverse", 1),
    Tag("Séance ✨", 12, 12, "pingpong_reverse", 3),
]


def test_frames_and_tags_are_read_back() -> None:
    durations = [100, 100, 80, 80, *([60] * 9)]
    data = ase.write(142, 96, durations, TAGS)
    assert struct.unpack_from("<IH", data, 0) == (len(data), ase.FILE_MAGIC)
    read = ase.parse(data)
    assert (read.width, read.height, read.frame_count) == (142, 96, 13)
    assert read.durations_ms == durations and read.tags == TAGS
    idle, walk, attack, last = read.tags
    assert idle.looped and idle.frames() == [0, 1, 2, 3]
    assert walk.frames() == [4, 5, 6, 7, 8, 9, 8, 7, 6, 5]
    assert not attack.looped and attack.frames() == [11, 10]
    assert last.name == "Séance ✨" and last.frames() == [12]


def test_a_file_without_tags_and_a_frame_of_no_duration() -> None:
    read = ase.parse(ase.write(16, 16, [0, 40], []))
    assert read.tags == [] and read.durations_ms == [100, 40]  # 0 is Aseprite's default


def test_chunks_the_reader_does_not_know_are_stepped_over() -> None:
    """A real file has layers, cels and a palette before and after its tags."""
    plain = ase.write(8, 8, [100, 100], [Tag("run", 0, 1, "forward", 0)])
    frame = ase.HEADER_BYTES
    size, magic, _old, duration = struct.unpack_from("<IHHH", plain, frame)
    tags_chunk = plain[frame + ase.FRAME_HEADER_BYTES : frame + size]
    layer = struct.pack("<IH", 6 + 5, 0x2004) + b"layer"
    palette = struct.pack("<IH", 6 + 3, 0x2019) + b"rgb"
    body = layer + tags_chunk + palette
    first = struct.pack("<IHHH2xI", ase.FRAME_HEADER_BYTES + len(body), magic, 3, duration, 3)
    data = bytearray(plain[:frame] + first + body + plain[frame + size :])
    struct.pack_into("<I", data, 0, len(data))
    read = ase.parse(bytes(data))
    assert read.frame_count == 2 and [t.name for t in read.tags] == ["run"]


@pytest.mark.parametrize(
    ("damage", "words"),
    [
        (lambda d: d[:60], "ends at byte"),  # cut in the header
        (lambda d: d[: len(d) - 9], "ends at byte"),  # cut in the last frame
        (lambda d: d[:4] + b"\x00\x00" + d[6:], "not an Aseprite file"),
        (lambda d: d[:6] + b"\x00\x00" + d[8:], "0 frames"),
        (lambda d: d[:132] + b"\x00\x00" + d[134:], "does not start as a frame"),
        (lambda d: b"", "ends at byte"),
        (lambda d: b"\x89PNG\r\n\x1a\n" + bytes(200), "not an Aseprite file"),
    ],
)
def test_a_damaged_file_is_an_error_not_a_crash(damage, words: str) -> None:
    data = ase.write(16, 16, [100, 100, 100], [Tag("walk", 0, 2, "forward", 0)])
    with pytest.raises(ase.AsepriteError, match=words):
        ase.parse(damage(data))


def test_a_tag_over_frames_the_file_does_not_have_is_an_error(tmp_path: Path) -> None:
    data = ase.write(16, 16, [100, 100], [Tag("walk", 0, 5, "forward", 0)])
    with pytest.raises(ase.AsepriteError, match="frames the file does not have"):
        ase.parse(data)
    with pytest.raises(ase.AsepriteError):
        ase.read(tmp_path / "no_such.aseprite")


# ----------------------------------------------------------------- beside a frame export


def _frame(path: Path, shade: int, blank: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    if not blank:
        img.paste(Image.new("RGBA", (4, 6), (shade, 0, 0, 255)), (2, 1))
    img.save(path)


def _pack(tmp: Path, stem: str, count: int, blanks: tuple[int, ...] = ()) -> Path:
    pack = tmp / "pack"
    for n in range(1, count + 1):
        _frame(pack / stem / f"{stem}{n}.png", 10 + n, blank=n in blanks)
    return pack


def _inventory(pack: Path):
    return inventory.build_inventory(archive.open_pack(pack, set()))


def _extract(pack: Path, work: Path):
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    ctx = AdapterContext(pack_id=inv.pack_id, work_dir=work)
    return SequencesAdapter().extract(inv, opened.root, ctx)


def _lengths(asset) -> dict[str, int]:
    return {k: len(v["frames"]) for k, v in asset.facets["animations"].items()}


def test_tags_with_names_name_the_animations(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "HERO", 12, blanks=(5,))
    tags = [
        Tag("Idle", 0, 3, "forward", 0),
        Tag("Run right", 5, 8, "forward", 0),  # frame 4 (file 5) is the blank one
        Tag("attack", 9, 11, "forward", 1),
    ]
    durations = [200] * 5 + [50] * 7
    (pack / "HERO" / "HERO.aseprite").write_bytes(ase.write(8, 8, durations, tags))
    res = _extract(pack, tmp_path / "work")
    (hero,) = res.assets
    assert _lengths(hero) == {"idle_down": 4, "walk_right": 4, "attack_down": 3}
    anims = hero.facets["animations"]
    assert (anims["idle_down"]["fps"], anims["walk_right"]["fps"]) == (5.0, 20.0)
    assert anims["idle_down"]["loop"] and not anims["attack_down"]["loop"]
    assert hero.confidence == 0.9 and res.issues == [], "named: nothing to review"
    assert len(res.consumed) == 11


def test_tags_without_a_name_still_say_where_the_animations_are(tmp_path: Path) -> None:
    """Aseprite calls a new tag "Tag", and some artists leave it: the ranges are the artist's
    all the same, and they cut two animations that no blank frame separates."""
    pack = _pack(tmp_path, "CHARACTER", 10, blanks=(4,))
    tags = [Tag("Tag", 0, 2, "forward", 0), Tag("Tag", 4, 6, "forward", 0), Tag("Tag", 7, 9, "forward", 0)]  # fmt: skip
    (pack / "CHARACTER" / "CHARACTER.aseprite").write_bytes(ase.write(8, 8, [100] * 10, tags))
    res = _extract(pack, tmp_path / "work")
    (hero,) = res.assets
    assert _lengths(hero) == {"anim_1": 3, "anim_2": 3, "anim_3": 3}
    assert hero.confidence == sequences.UNNAMED_CONFIDENCE
    (note,) = res.issues
    assert note.code == "ADAPT-005" and "3 animations" in note.message


def test_a_source_makes_frames_of_pictures_no_blank_separates(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "FLAME", 6)
    assert _extract(pack, tmp_path / "work").assets == []  # six numbered pictures
    (pack / "FLAME" / "FLAME.aseprite").write_bytes(ase.write(8, 8, [125] * 6, []))
    res = _extract(pack, tmp_path / "work")
    (flame,) = res.assets
    assert _lengths(flame) == {"idle_down": 6}, "one animation: what the prop always does"
    assert flame.facets["animations"]["idle_down"]["fps"] == 8.0 and res.issues == []


def test_a_source_of_another_shape_says_nothing(tmp_path: Path) -> None:
    """Four background layers beside the one-frame file they were drawn in are four pictures."""
    pack = _pack(tmp_path, "BACKGROUND", 4)
    (pack / "BACKGROUND" / "BACKGROUND.aseprite").write_bytes(ase.write(8, 8, [100], []))
    res = _extract(pack, tmp_path / "work")
    assert res.assets == [] and res.issues == []


def test_a_source_that_cannot_be_read_is_a_note_and_the_pictures_are_used(tmp_path: Path) -> None:
    pack = _pack(tmp_path, "BOX", 7, blanks=(4,))
    whole = ase.write(8, 8, [100] * 7, [Tag("open", 0, 2, "forward", 0)])
    (pack / "BOX" / "BOX.aseprite").write_bytes(whole[: len(whole) - 20])
    res = _extract(pack, tmp_path / "work")
    (box,) = res.assets
    assert _lengths(box) == {"anim_1": 3, "anim_2": 3}  # cut at the blank frame, as without it
    assert [i.code for i in res.issues] == ["ADAPT-006", "ADAPT-005"]
    assert "BOX/BOX.aseprite" in res.issues[0].message and res.issues[0].severity.value == "info"


# ----------------------------------------------------------------- the pictures of a source

RED, BLUE, GREEN, CLEAR = (255, 0, 0, 255), (0, 0, 255, 255), (0, 255, 0, 255), (0, 0, 0, 0)


def _fill(colour: tuple[int, ...], width: int, height: int) -> bytes:
    return bytes(colour) * (width * height)


def _px(picture: ase.Picture, frame: int, x: int, y: int) -> tuple[int, ...]:
    return picture.frames[frame].getpixel((x, y))


def test_cels_are_drawn_where_they_lie_raw_packed_and_linked() -> None:
    layers = [ase.Layer("body"), ase.Layer("hat")]
    cels = [
        ase.Cel(0, 0, 1, 1, 2, 2, _fill(RED, 2, 2), compressed=False),
        ase.Cel(0, 1, 2, 2, 2, 2, _fill(BLUE, 2, 2)),  # over the body's corner, zlib
        ase.Cel(1, 0, link=0),  # frame 2 shows the body of frame 1 again
        ase.Cel(2, 0, -1, 3, 2, 2, _fill(GREEN, 2, 2)),  # half off the sprite
    ]
    picture = ase.render(ase.write(4, 4, [100, 100, 100], [], layers=layers, cels=cels))
    assert [im.size for im in picture.frames] == [(4, 4)] * 3 and picture.inexact == []
    assert _px(picture, 0, 0, 0) == CLEAR and _px(picture, 0, 1, 1) == RED
    assert _px(picture, 0, 2, 2) == BLUE and _px(picture, 0, 3, 3) == BLUE
    assert _px(picture, 1, 1, 1) == RED and _px(picture, 1, 3, 3) == CLEAR, "the link, no hat"
    assert _px(picture, 2, 0, 3) == GREEN and _px(picture, 2, 1, 3) == CLEAR
    assert picture.file.frame_count == 3


def test_opacity_of_a_layer_and_of_a_cel_and_layers_that_are_hidden() -> None:
    layers = [
        ase.Layer("under"),
        ase.Layer("half", opacity=128),
        ase.Layer("hidden", visible=False),
        ase.Layer("group", visible=False, kind=ase.LAYER_GROUP),
        ase.Layer("in the hidden group", level=1),
        ase.Layer("to draw from", reference=True),
        ase.Layer("after the group"),
    ]
    cels = [
        ase.Cel(0, 0, 0, 0, 3, 1, _fill(RED, 3, 1)),
        ase.Cel(0, 1, 0, 0, 1, 1, _fill(BLUE, 1, 1)),
        ase.Cel(0, 2, 0, 0, 3, 1, _fill(GREEN, 3, 1)),
        ase.Cel(0, 4, 0, 0, 3, 1, _fill(GREEN, 3, 1)),
        ase.Cel(0, 5, 0, 0, 3, 1, _fill(GREEN, 3, 1)),
        ase.Cel(0, 6, 2, 0, 1, 1, _fill((0, 0, 255, 128), 1, 1), opacity=128),
    ]
    picture = ase.render(ase.write(3, 1, [100], [], layers=layers, cels=cels))
    # Aseprite's own arithmetic: 255 * 128 is 128, and red gives way by 128 of 255
    assert _px(picture, 0, 0, 0) == (127, 0, 128, 255)
    assert _px(picture, 0, 1, 0) == RED, "nothing of the three layers that are not shown"
    assert _px(picture, 0, 2, 0) == (191, 0, 64, 255), "alpha 128 of a cel at 128: a quarter"


def test_a_cel_alone_keeps_its_own_alpha() -> None:
    cels = [ase.Cel(0, 0, 0, 0, 1, 1, bytes((10, 20, 30, 200)), opacity=128)]
    picture = ase.render(ase.write(2, 1, [100], [], layers=[ase.Layer("a")], cels=cels))
    assert _px(picture, 0, 0, 0) == (10, 20, 30, 100) and _px(picture, 0, 1, 0) == CLEAR


def test_grayscale_and_indexed_colour() -> None:
    gray = [ase.Cel(0, 0, 0, 0, 2, 1, bytes((200, 255, 90, 0)))]
    picture = ase.render(ase.write(2, 1, [100], [], depth=16, layers=[ase.Layer("g")], cels=gray))
    assert _px(picture, 0, 0, 0) == (200, 200, 200, 255) and _px(picture, 0, 1, 0) == CLEAR

    palette = [(9, 9, 9, 255), RED, (0, 0, 255, 128)]
    layers = [ase.Layer("Background", background=True), ase.Layer("ink")]
    cels = [
        ase.Cel(0, 0, 0, 0, 3, 1, bytes((1, 1, 0))),  # index 0 is a colour on the background
        ase.Cel(0, 1, 0, 0, 3, 1, bytes((0, 2, 9))),  # ... see-through elsewhere; 9: no colour
    ]
    data = ase.write(3, 1, [100], [], depth=8, layers=layers, cels=cels, palette=palette)
    picture = ase.render(data)
    assert _px(picture, 0, 0, 0) == RED, "the ink's index 0 shows the background"
    assert _px(picture, 0, 1, 0) == (127, 0, 128, 255), "a palette colour with alpha"
    assert _px(picture, 0, 2, 0) == (9, 9, 9, 255)
    other = ase.write(3, 1, [100], [], depth=8, layers=layers, cels=cels, palette=palette,
                      transparent=2)  # fmt: skip
    assert _px(ase.render(other), 0, 1, 0) == RED, "index 2 is see-through"


def test_the_backdrop_an_artist_draws_against_is_left_out() -> None:
    """A full layer named as a background behind an animation: the artist switches it off to
    export, and with it the sprite has no see-through pixel."""
    two_tone = _fill((110, 139, 153, 255), 4, 3) + _fill((90, 110, 120, 255), 4, 1)

    def source(name: str, frames: int = 2, **layer: bool) -> bytes:
        layers = [ase.Layer(name, **layer), ase.Layer("body")]
        cels = [c for n in range(frames) for c in (
            ase.Cel(n, 0, 0, 0, 4, 4, two_tone),
            ase.Cel(n, 1, 1 + n, 1, 1, 1, _fill(RED, 1, 1)),
        )]  # fmt: skip
        return ase.write(4, 4, [100] * frames, [], layers=layers, cels=cels)

    for name in ("BG", "gif bg", "Background 2"):
        picture = ase.render(source(name))
        assert picture.backdrop == name and picture.inexact == []
        assert _px(picture, 0, 0, 0) == CLEAR and _px(picture, 0, 1, 1) == RED
        kept = ase.render(source(name), keep_backdrop=True)
        assert kept.backdrop is None and _px(kept, 0, 0, 0) == (110, 139, 153, 255)
    # not left out: a layer with another name, a still picture, Aseprite's own Background layer
    assert ase.render(source("Layer 1")).backdrop is None
    assert ase.render(source("BG", frames=1)).backdrop is None
    assert ase.render(source("Background", background=True)).backdrop is None
    # ... a layer with a hole in it, and one with nothing over it
    layers = [ase.Layer("BG"), ase.Layer("body")]
    holed = two_tone[:-1] + bytes([0])
    cels = [ase.Cel(n, 0, 0, 0, 4, 4, holed) for n in (0, 1)]
    cels.append(ase.Cel(0, 1, 1, 1, 1, 1, _fill(RED, 1, 1)))
    assert ase.render(ase.write(4, 4, [100, 100], [], layers=layers, cels=cels)).backdrop is None
    alone = ase.write(4, 4, [100, 100], [], layers=layers[:1], cels=cels[:2])
    assert ase.render(alone).backdrop is None


def test_what_is_not_drawn_as_aseprite_draws_it_is_said() -> None:
    layers = [
        ase.Layer("multiply", blend=1),
        ase.Layer("tiles", kind=ase.LAYER_TILEMAP),
        ase.Layer("group", kind=ase.LAYER_GROUP, opacity=100),
    ]
    cels = [ase.Cel(0, 0, 0, 0, 1, 1, _fill(RED, 1, 1))]
    picture = ase.render(ase.write(1, 1, [100], [], layers=layers, cels=cels))
    assert len(picture.inexact) == 3 and _px(picture, 0, 0, 0) == RED


@pytest.mark.parametrize(
    ("kwargs", "words"),
    [
        ({"cels": [ase.Cel(0, 0, 0, 0, 2, 2, _fill(RED, 1, 1))]}, "bytes for 2 x 2 pixels"),
        ({"cels": [ase.Cel(0, 0, link=1)]}, "links to nothing"),
        ({"cels": [ase.Cel(0, 3, 0, 0, 1, 1, _fill(RED, 1, 1))]}, "a layer the file lacks"),
        ({"depth": 24}, "colour depth of 24"),
        ({"depth": 8, "cels": [ase.Cel(0, 0, 0, 0, 1, 1, bytes([1]))]}, "no palette"),
    ],
)
def test_a_source_that_cannot_be_drawn_is_an_error(kwargs: dict, words: str) -> None:
    data = ase.write(2, 2, [100, 100], [], **{"layers": [ase.Layer("a")], **kwargs})
    with pytest.raises(ase.AsepriteError, match=words):
        ase.render(data)


def test_a_cel_whose_zlib_data_is_damaged_is_an_error() -> None:
    cels = [ase.Cel(0, 0, 0, 0, 8, 8, _fill(RED, 8, 8))]
    data = bytearray(ase.write(8, 8, [100], [], layers=[ase.Layer("a")], cels=cels))
    data[-6:] = bytes([255]) * 6
    with pytest.raises(ase.AsepriteError, match="cannot be unpacked|bytes for 8 x 8"):
        ase.render(bytes(data))
    assert ase.parse(bytes(data)).frame_count == 1, "the tags reader does not look at pixels"


# ----------------------------------------------------------------- a source with no export


def _slime(frames: int = 4, tags: list[Tag] | None = None) -> bytes:
    """A slime of two layers that hops one pixel a frame, on the artist's grey backdrop."""
    layers = [ase.Layer("BG"), ase.Layer("body"), ase.Layer("eyes")]
    cels = []
    for n in range(frames):
        cels.append(ase.Cel(n, 0, 0, 0, 8, 8, _fill((60, 60, 60, 255), 8, 8)))
        cels.append(ase.Cel(n, 1, 1, 3 - n % 2, 6, 4, _fill((40, 200, 90, 255), 6, 4)))
        cels.append(ase.Cel(n, 2, 2, 4 - n % 2, 4, 1, _fill((0, 0, 0, 255), 4, 1)))
    return ase.write(8, 8, [120] * frames, tags or [], layers=layers, cels=cels)


def test_a_source_with_no_export_is_drawn_to_a_strip(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    (pack / "enemies").mkdir(parents=True)
    tags = [Tag("Idle", 0, 1, "forward", 0), Tag("attack", 2, 3, "forward", 1)]
    (pack / "enemies" / "slime.aseprite").write_bytes(_slime(4, tags))
    _frame(pack / "tree.png", 30)
    res = _extract(pack, tmp_path / "work")
    (slime,) = res.assets
    assert slime.path == "enemies/slime.aseprite" and slime.claim == "full"
    assert slime.confidence == sequences.RENDERED_CONFIDENCE and res.issues == []
    facets = slime.facets
    assert (facets["frame"], facets["size"], facets["origin"]) == ([8, 8], [32, 8], [4, 5])
    assert facets["animations"] == {
        "idle_down": {"frames": [[0, 0], [1, 0]], "fps": round(1000 / 120, 6), "loop": True},
        "attack_down": {"frames": [[2, 0], [3, 0]], "fps": round(1000 / 120, 6), "loop": False},
    }
    ((project_path, file),) = res.generated.items()
    assert res.rendered == {"enemies/slime.aseprite": project_path}
    assert project_path.startswith(sequences.FRAME_STRIP_DIR + "/")
    with Image.open(file) as strip:
        assert strip.size == (32, 8) and strip.mode == "RGBA"
        assert strip.getpixel((0, 0)) == CLEAR, "the backdrop is not in the sprite"
        assert strip.getpixel((1, 3)) == (40, 200, 90, 255) and strip.getpixel((9, 2))[3] == 255
        assert strip.getpixel((2, 4)) == (0, 0, 0, 255)
    first = Path(file).read_bytes()
    again = _extract(pack, tmp_path / "other")
    assert Path(next(iter(again.generated.values()))).read_bytes() == first, "the same bytes"
    assert list(again.generated) == [project_path]


def test_a_source_without_tags_takes_its_name_or_is_what_a_prop_does(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "bat fly 8x8.aseprite").write_bytes(_slime(3))
    (pack / "torch.ase").write_bytes(_slime(2))
    (pack / "rock.aseprite").write_bytes(_slime(1))
    res = _extract(pack, tmp_path / "work")
    by_path = {a.path: a.facets for a in res.assets}
    assert list(by_path["bat fly 8x8.aseprite"]["animations"]) == ["fly_down"]
    assert list(by_path["torch.ase"]["animations"]) == ["idle_down"]
    assert "animations" not in by_path["rock.aseprite"], "one frame: a picture"
    assert by_path["rock.aseprite"]["size"] == [8, 8]


def test_tags_without_names_of_a_drawn_source_need_review(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    tags = [Tag("Tag", 0, 1, "forward", 0), Tag("Tag", 2, 3, "forward", 0)]
    (pack / "ghost.aseprite").write_bytes(_slime(4, tags))
    res = _extract(pack, tmp_path / "work")
    (ghost,) = res.assets
    assert _lengths(ghost) == {"anim_1": 2, "anim_2": 2}
    assert ghost.confidence == sequences.UNNAMED_CONFIDENCE
    assert [i.code for i in res.issues] == ["ADAPT-005"]


def test_a_source_that_has_an_export_is_not_drawn(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    for name in ("hero.png", "art/Player Jump Left 8x8-sheet.png", "boss/boss1.png"):
        _frame(pack / name, 40)
    (pack / "src").mkdir()
    (pack / "src" / "Hero.aseprite").write_bytes(_slime())  # hero.png, somewhere in the pack
    (pack / "art" / "player jump 8x8.aseprite").write_bytes(_slime())  # its words, beside it
    (pack / "src" / "boss.aseprite").write_bytes(_slime())  # boss1.png: a frame of it
    assert sequences.lone_sources(_inventory(pack)) == []
    assert _extract(pack, tmp_path / "work").assets == []
    (pack / "src" / "player jump 8x8.aseprite").write_bytes(_slime())  # not beside that sheet
    assert [f.path for f in sequences.lone_sources(_inventory(pack))] == [
        "src/player jump 8x8.aseprite"
    ]


def test_a_source_nothing_is_drawn_in_is_no_sprite_and_a_damaged_one_a_note(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "empty.aseprite").write_bytes(ase.write(8, 8, [100, 100], []))  # no layer, no cel
    whole = _slime()
    (pack / "broken.aseprite").write_bytes(whole[: len(whole) - 30])
    res = _extract(pack, tmp_path / "work")
    assert res.assets == [] and res.generated == {}
    (note,) = res.issues
    assert note.code == "ADAPT-006" and "broken.aseprite" in note.message
    assert note.severity.value == "info"


def test_the_drawn_source_is_an_asset_of_the_catalog(tmp_path: Path) -> None:
    from rpggen.core import catalog

    pack = tmp_path / "pack"
    (pack / "enemies").mkdir(parents=True)
    (pack / "enemies" / "slime.aseprite").write_bytes(_slime(4, [Tag("walk", 0, 3, "forward", 0)]))
    _frame(pack / "enemies" / "bat.png", 30)
    (pack / "LICENSE.txt").write_text("CC0", encoding="utf-8")
    opened = archive.open_pack(pack, set())
    inv = inventory.build_inventory(opened)
    cat, issues, generated = catalog.assemble(
        [(opened, inv)], None, [], use_cache=False, work_dir=tmp_path / "work"
    )
    slime = cat.asset(f"{inv.pack_id}.enemies.slime")
    assert slime is not None and slime.kind == "image" and slime.detected_by == "sequences"
    assert slime.path.startswith("generated/frame_strips/") and slime.path in generated
    assert Path(generated[slime.path]).is_file()
    assert slime.sha256 == next(f.sha256 for f in inv.files if f.ext == ".aseprite")
    assert slime.detected["role"] == "ENEMY" and list(slime.detected["animations"]) == ["walk_down"]
    assert not [i for i in issues if i.code.startswith("ADAPT")]
    again, _issues, _generated = catalog.assemble(
        [(opened, inv)], cat, [], use_cache=False, work_dir=tmp_path / "work"
    )
    assert again.to_json() == cat.to_json(), "the same catalog from the same pack"
