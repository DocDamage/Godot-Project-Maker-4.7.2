from __future__ import annotations

from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import cache

SHA = "ab" + "0" * 62


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return paths.cache_dir()


def test_miss_then_hit() -> None:
    assert cache.get(SHA, 1) is None
    cache.put(SHA, 1, {"w": 16, "grid_candidates": []})
    got = cache.get(SHA, 1)
    assert got == {"w": 16, "grid_candidates": [], "analyzer_version": 1, "sha256": SHA}


def test_layout_follows_schema(cache_dir: Path) -> None:
    cache.put(SHA, 1, {"w": 1})
    assert (cache_dir / "analysis" / "ab" / f"{SHA}.json").exists()


def test_version_mismatch_is_a_miss() -> None:
    cache.put(SHA, 1, {"w": 1})
    assert cache.get(SHA, 2) is None
    # the stale entry is kept until overwritten
    cache.put(SHA, 2, {"w": 2})
    assert cache.get(SHA, 2)["w"] == 2
    assert cache.get(SHA, 1) is None


def test_corrupt_entry_is_deleted(cache_dir: Path) -> None:
    path = cache_dir / "analysis" / "ab" / f"{SHA}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert cache.get(SHA, 1) is None
    assert not path.exists()


def test_non_object_entry_is_a_miss(cache_dir: Path) -> None:
    path = cache_dir / "analysis" / "ab" / f"{SHA}.json"
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2]", encoding="utf-8")
    assert cache.get(SHA, 1) is None


def test_clear() -> None:
    cache.put(SHA, 1, {"w": 1})
    cache.clear()
    assert cache.get(SHA, 1) is None
    cache.clear()  # clearing an empty cache is fine
