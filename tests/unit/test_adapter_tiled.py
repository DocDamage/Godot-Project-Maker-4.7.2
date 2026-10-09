"""Tile data encodings of the Tiled reader (T13.14: Zstandard)."""

from __future__ import annotations

import base64
import importlib
import struct
import zlib

import pytest

from rpggen.core.adapters import tiled

GIDS = [0, 18, 0, 0, 0, 2, 0x80000001, 7]
RAW = struct.pack(f"<{len(GIDS)}I", *GIDS)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _stored_frame(raw: bytes) -> bytes:
    """A Zstandard frame of one raw block, as tools/make_synthetic_packs.py writes it."""
    return (
        bytes.fromhex("28b52ffd20")
        + bytes([len(raw)])
        + (len(raw) << 3 | 1).to_bytes(3, "little")
        + raw
    )


def _readers() -> list[str]:
    found = []
    for name in ("zstandard", "compression.zstd", "backports.zstd"):
        try:
            importlib.import_module(name)
        except ImportError:
            continue
        found.append(name)
    return found


def _only(monkeypatch: pytest.MonkeyPatch, name: str | None) -> None:
    module = importlib.import_module(name) if name else None
    monkeypatch.setattr(tiled, "_zstd_module", lambda: (name, module) if name else None)


def test_a_reader_is_installed() -> None:
    assert _readers(), "py7zr brings backports.zstd; the maps extra brings zstandard"


@pytest.mark.parametrize("name", _readers())
def test_a_zstd_layer_decodes_to_the_same_cells_as_its_zlib_twin(monkeypatch, name: str) -> None:
    _only(monkeypatch, name)
    twin = tiled._decode(_b64(zlib.compress(RAW)), "base64", "zlib")
    assert tiled._decode(_b64(_stored_frame(RAW)), "base64", "zstd") == twin == GIDS


def test_a_really_compressed_frame_is_read(monkeypatch) -> None:
    zstandard = pytest.importorskip("zstandard")
    gids = [3] * 4000
    raw = struct.pack(f"<{len(gids)}I", *gids)
    packed = zstandard.ZstdCompressor(level=9).compress(raw)
    assert len(packed) < len(raw) // 10
    for name in _readers():
        _only(monkeypatch, name)
        assert tiled._decode(_b64(packed), "base64", "zstd") == gids


def test_without_a_reader_the_layer_says_what_to_install(monkeypatch) -> None:
    _only(monkeypatch, None)
    with pytest.raises(tiled._Unsupported, match="install the zstandard package"):
        tiled._decode(_b64(_stored_frame(RAW)), "base64", "zstd")


@pytest.mark.parametrize("name", _readers())
def test_a_damaged_frame_and_a_bomb_are_refused(monkeypatch, name: str) -> None:
    _only(monkeypatch, name)
    with pytest.raises(tiled._Unsupported, match="damaged"):
        tiled._decode(_b64(bytes.fromhex("28b52ffd") + b" not a frame"), "base64", "zstd")
    with pytest.raises(tiled._Unsupported, match="damaged"):
        tiled._decode(_b64(_stored_frame(RAW)[:-3]), "base64", "zstd")
    monkeypatch.setattr(tiled, "MAX_TILE_BYTES", 16)
    with pytest.raises(tiled._Unsupported, match="too large"):
        tiled._decode(_b64(_stored_frame(RAW)), "base64", "zstd")


def test_an_unknown_compression_names_itself() -> None:
    with pytest.raises(tiled._Unsupported, match="unsupported compression .lz4."):
        tiled._decode("AAAAAA==", "base64", "lz4")
