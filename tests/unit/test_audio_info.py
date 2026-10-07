from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from rpggen.core import audio_info, classifier

REPO = Path(__file__).resolve().parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "make_synthetic_packs", REPO / "tools" / "make_synthetic_packs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tool = _tool()


CASES = {
    "a.wav": (lambda: tool.wav_bytes(1.0), 1.0),
    "b.wav": (lambda: tool.wav_bytes(30.0, rate=4000), 30.0),
    "a.ogg": (lambda: tool.ogg_vorbis_bytes(1.0), 1.0),
    "b.ogg": (lambda: tool.ogg_vorbis_bytes(30.0), 30.0),
    "a.opus": (lambda: tool.ogg_opus_bytes(25.0), 25.0),
    "a.mp3": (lambda: tool.mp3_bytes(1.0), 1.0),
    "b.mp3": (lambda: tool.mp3_bytes(30.0), 30.0),
    "c.mp3": (lambda: tool.mp3_bytes(30.0, id3=True), 30.0),
    "d.mp3": (lambda: tool.mp3_bytes(30.0, xing=True, id3=True), 30.0),
    "a.flac": (lambda: tool.flac_bytes(30.0), 30.0),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_durations_are_read_within_a_tenth_of_a_second(tmp_path: Path, name: str) -> None:
    make, expected = CASES[name]
    path = tmp_path / name
    path.write_bytes(make())
    got = audio_info.duration_seconds(path)
    assert got is not None
    assert abs(got - expected) < 0.1


@pytest.mark.parametrize("name", ["x.ogg", "x.mp3", "x.flac", "x.wav", "x.opus"])
def test_garbage_and_truncated_files_give_none(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"this is not audio at all" * 20)
    assert audio_info.duration_seconds(path) is None
    path.write_bytes(b"")
    assert audio_info.duration_seconds(path) is None
    path.write_bytes(tool.ogg_vorbis_bytes(5.0)[:20])
    assert audio_info.duration_seconds(path) is None
    assert audio_info.duration_seconds(tmp_path / "missing.mp3") is None


def test_a_truncated_ogg_without_a_last_page_is_none(tmp_path: Path) -> None:
    data = tool.ogg_vorbis_bytes(5.0)
    first_page = data[: data.index(b"OggS", 4)]
    path = tmp_path / "t.ogg"
    path.write_bytes(first_page)
    assert audio_info.duration_seconds(path) is None


def test_long_files_are_music_and_short_ones_are_sfx(tmp_path: Path) -> None:
    long_, short = tmp_path / "long.ogg", tmp_path / "blip.ogg"
    long_.write_bytes(tool.ogg_vorbis_bytes(30.0))
    short.write_bytes(tool.ogg_vorbis_bytes(1.0))
    for path, role in ((long_, "AUDIO_MUSIC"), (short, "AUDIO_SFX")):
        duration = classifier.audio_duration(path)
        got, _conf, _alt = classifier.classify(
            {}, path.name, {"kind": "audio", "duration_s": duration}
        )
        assert got == role


def test_no_dependency_is_on_the_deny_list() -> None:
    import re

    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    deps = re.search(r"dependencies = \[(.*?)\]", text, re.S).group(1).lower()
    assert "mutagen" not in deps
    assert "mutagen" not in (REPO / "packaging" / "rpggen.spec").read_text(encoding="utf-8")
