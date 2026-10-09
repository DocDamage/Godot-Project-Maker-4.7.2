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


# ------------------------------------------------------------------------ decoded audio (T13.17)


def _sine(seconds: float, rate: int = 8000, hz: float = 220.0, level: float = 0.8):
    import numpy

    t = numpy.arange(int(seconds * rate)) / rate
    return (level * numpy.sin(2 * numpy.pi * hz * t)).astype("float32")


def _section(seconds: float, seed: int, rate: int = 8000):
    """A tone whose loudness changes every 50 ms: no two stretches of it sound alike."""
    import numpy

    levels = numpy.random.default_rng(seed).uniform(0.1, 0.9, int(seconds * 20))
    return (numpy.repeat(levels, rate // 20) * _sine(seconds, rate, level=1.0)).astype("float32")


@pytest.mark.parametrize("ext", ["wav", "ogg", "flac"])
def test_peaks_of_a_sine_follow_its_level(tmp_path: Path, ext: str) -> None:
    import numpy
    import soundfile

    # loud for the first half, quiet for the second, in stereo
    mono = numpy.concatenate([_sine(1.0, level=0.8), _sine(1.0, level=0.2)])
    path = tmp_path / f"tone.{ext}"
    soundfile.write(str(path), numpy.stack([mono, mono], axis=1), 8000)
    found = audio_info.peaks(path, columns=8)
    assert found is not None and len(found) == 8
    for low, high in found[:4]:
        assert high == pytest.approx(0.8, abs=0.06) and low == pytest.approx(-0.8, abs=0.06)
    for low, high in found[4:]:
        assert high == pytest.approx(0.2, abs=0.06) and low == pytest.approx(-0.2, abs=0.06)
    assert len(audio_info.peaks(path) or []) == 96, "96 columns unless asked otherwise"
    assert all(-1.0 <= low <= 0.0 <= high <= 1.0 for low, high in found)


def test_peaks_read_a_long_file_in_blocks(tmp_path: Path, monkeypatch) -> None:
    import soundfile

    path = tmp_path / "long.wav"
    soundfile.write(str(path), _sine(3.0), 8000)
    whole = audio_info.peaks(path, columns=12)
    monkeypatch.setattr(audio_info, "PEAK_BLOCK_FRAMES", 1000)  # 24 blocks instead of one
    assert audio_info.peaks(path, columns=12) == whole
    monkeypatch.setattr(audio_info, "PEAK_BLOCK_FRAMES", 7)  # blocks smaller than a column
    assert audio_info.peaks(path, columns=12) == whole
    # more columns than samples: the empty ones are flat, nothing raises
    soundfile.write(str(tmp_path / "tiny.wav"), _sine(0.001), 8000)
    tiny = audio_info.peaks(tmp_path / "tiny.wav", columns=96)
    assert tiny is not None and len(tiny) == 96


def test_an_unreadable_file_has_no_peaks_and_no_loop(tmp_path: Path, monkeypatch) -> None:
    garbage = tmp_path / "noise.ogg"
    garbage.write_bytes(b"OggS" + bytes(range(200)))
    for path in (garbage, tmp_path / "missing.wav", REPO / "pyproject.toml"):
        assert audio_info.peaks(path) is None
        assert audio_info.guess_loop(path) is None
    good = tmp_path / "ok.wav"
    import soundfile

    soundfile.write(str(good), _sine(0.5), 8000)
    assert audio_info.peaks(good, columns=0) is None
    # without libsndfile everything is a flat bar, and nothing is an error
    monkeypatch.setattr(audio_info, "soundfile_module", lambda: None)
    assert audio_info.peaks(good) is None and audio_info.guess_loop(good) is None


@pytest.mark.parametrize("ext", ["wav", "ogg"])
def test_the_loop_guess_finds_a_repeated_section(tmp_path: Path, ext: str) -> None:
    import numpy
    import soundfile

    # 1.5 s of intro, a 4 s section twice, a short tail
    section = _section(4.0, seed=2)
    signal = numpy.concatenate([_section(1.5, seed=1), section, section, _section(0.3, seed=3)])
    path = tmp_path / f"track.{ext}"
    soundfile.write(str(path), signal, 8000)
    found = audio_info.guess_loop(path)
    assert found is not None
    start, end = found
    assert end - start == 4000, "the loop is as long as the section"
    assert 1500 <= start <= 1600, "it starts where the section starts, after the first second"


def test_the_loop_guess_needs_three_seconds_and_starts_after_the_first(tmp_path: Path) -> None:
    import soundfile

    short = tmp_path / "short.wav"
    soundfile.write(str(short), _sine(2.5), 8000)
    assert audio_info.guess_loop(short) is None
    steady = tmp_path / "steady.wav"
    soundfile.write(str(steady), _sine(6.0), 8000)
    start, end = audio_info.guess_loop(steady) or (0, 0)
    assert start >= 1000 and end - start >= 2000 and end <= 6000
    # a steady tone loops anywhere: the guess takes the longest stretch
    assert end - start >= 4500


def test_soundfile_is_a_dependency_and_in_the_frozen_build() -> None:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert '"soundfile>=' in text
    spec = (REPO / "packaging" / "rpggen.spec").read_text(encoding="utf-8")
    assert "_soundfile_data" in spec and "binaries=binaries" in spec
    for name in ("release.txt", "release-linux.txt", "release-macos.txt"):
        assert "soundfile==" in (REPO / "requirements" / name).read_text(encoding="utf-8"), name
    notices = (REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "libsndfile" in notices and "LGPL-2.1-or-later" in notices
    assert "tools" and "audio-check" in (REPO / "tools" / "package.py").read_text(encoding="utf-8")


def test_the_cli_audio_check_decodes_an_ogg(tmp_path: Path, capsys) -> None:
    from rpggen import cli

    assert cli.main(["audio-check"]) == 0
    assert "tone.ogg decoded" in capsys.readouterr().out
    silent = tmp_path / "silent.txt"
    silent.write_text("not a sound", encoding="utf-8")
    assert cli.main(["audio-check", str(silent)]) == 1
