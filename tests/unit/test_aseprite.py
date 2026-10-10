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
