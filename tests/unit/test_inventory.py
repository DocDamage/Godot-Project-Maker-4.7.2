from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from rpggen.core import archive, inventory
from rpggen.errors import Severity

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "cache"
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(cache))
    return cache


def _inv(source: Path) -> inventory.Inventory:
    return inventory.build_inventory(archive.open_pack(source, set()))


def test_classify_kind() -> None:
    k = inventory.classify_kind
    assert k("tiles/a.png") == "image"
    assert k("a/B.PNG") == "image"
    assert k("music/theme.ogg") == "audio"
    assert k("fonts/x.ttf") == "font"
    assert k("LICENSE.txt") == "license"
    assert k("docs/Credits.md") == "license"
    assert k("README") == "license"
    assert k("notes.txt") == "doc"
    assert k("tiles.tsx") == "metadata"
    assert k("knight.json") == "metadata"
    assert k("weird.bin") == "other"


def test_mixed_inventory_is_sorted_with_kinds() -> None:
    inv = _inv(SYNTH / "mixed")
    paths = [f.path for f in inv.files]
    assert paths == sorted(paths, key=lambda s: (s.casefold(), s))
    assert len(paths) == 1 + 2 + 1 + 12  # license, two tile sheets, background, 12 icons
    by = {f.path: f for f in inv.files}
    assert by["LICENSE.txt"].kind == "license" and by["LICENSE.txt"].image is None
    sky = by["backgrounds/sky.png"]
    assert sky.kind == "image" and sky.image == {
        "w": 512,
        "h": 288,
        "mode": "RGBA",
        "has_alpha": True,
        "frames": 1,
    }
    assert by["tiles/ground32.png"].image["w"] == 128
    assert all(by[f"items/item_{i:02d}.png"].image["w"] == 16 for i in range(1, 13))
    assert all(len(f.sha256) == 64 for f in inv.files)
    assert len(inv.source_sha256) == 64
    assert inv.issues == []


def test_zipped_and_basic16_inventories_match() -> None:
    a = _inv(SYNTH / "basic16")
    b = _inv(SYNTH / "zipped.zip")
    assert [(f.path, f.sha256, f.size, f.kind) for f in a.files] == [
        (f.path, f.sha256, f.size, f.kind) for f in b.files
    ]
    assert a.pack_id == "basic16" and b.pack_id == "zipped"


def test_folder_hash_is_content_based(tmp_path: Path) -> None:
    a = _inv(SYNTH / "basic16")
    copy = tmp_path / "other_name"
    copy.mkdir()
    for f in (SYNTH / "basic16").rglob("*"):
        if f.is_file():
            dst = copy / f.relative_to(SYNTH / "basic16")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(f.read_bytes())
    assert _inv(copy).source_sha256 == a.source_sha256


def test_junk_files_are_skipped(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    (pack / "__MACOSX").mkdir(parents=True)
    (pack / "__MACOSX" / "._a.png").write_bytes(b"x")
    (pack / ".DS_Store").write_bytes(b"x")
    Image.new("RGBA", (4, 4)).save(pack / "a.png")
    inv = _inv(pack)
    assert [f.path for f in inv.files] == ["a.png"]
    assert [s["path"] for s in inv.skipped] == [".DS_Store", "__MACOSX/._a.png"]
    assert {s["reason"] for s in inv.skipped} == {"os_junk"}


def test_undecodable_image_gives_asset002(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    pack.mkdir()
    (pack / "broken.png").write_bytes(b"this is not a png")
    inv = _inv(pack)
    f = inv.files[0]
    assert f.kind == "image" and f.image is None
    assert [i.code for i in inv.issues] == ["ASSET-002"]
    assert inv.issues[0].severity is Severity.WARNING


def test_alpha_detection(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    pack.mkdir()
    Image.new("RGB", (4, 4)).save(pack / "rgb.png")
    Image.new("LA", (4, 4)).save(pack / "la.png")
    pal = Image.new("P", (4, 4))
    pal.save(pack / "pal_opaque.png")
    pal.save(pack / "pal_trans.png", transparency=0)
    by = {f.path: f for f in _inv(pack).files}
    assert by["rgb.png"].image["has_alpha"] is False
    assert by["la.png"].image["has_alpha"] is True
    assert by["pal_opaque.png"].image["has_alpha"] is False
    assert by["pal_trans.png"].image["has_alpha"] is True


def test_gif_frame_count(tmp_path: Path) -> None:
    pack = tmp_path / "p"
    pack.mkdir()
    frames = []
    for i in range(3):
        frame = Image.new("P", (4, 4), 0)
        frame.putpixel((i, i), 1)
        frames.append(frame)
    frames[0].save(pack / "anim.gif", save_all=True, append_images=frames[1:], duration=100)
    assert _inv(pack).files[0].image["frames"] == 3


def test_archive_inventory_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _inv(SYNTH / "zipped.zip")

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("files must not be re-scanned")

    monkeypatch.setattr(inventory, "_scan_file", boom)
    second = _inv(SYNTH / "zipped.zip")
    assert [f.to_json() for f in second.files] == [f.to_json() for f in first.files]


def test_process_pool_path_matches_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    serial = _inv(SYNTH / "mixed")
    monkeypatch.setattr(inventory, "POOL_THRESHOLD", 1)
    pooled = _inv(SYNTH / "mixed")
    assert [f.to_json() for f in pooled.files] == [f.to_json() for f in serial.files]


def test_inventory_json_roundtrip() -> None:
    inv = _inv(SYNTH / "basic16")
    again = inventory.Inventory.from_json(inv.to_json())
    assert again.to_json() == inv.to_json()
