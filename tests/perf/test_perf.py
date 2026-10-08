"""Performance targets of ARCHITECTURE section 45 on a 1,000-image pack (T10.08).

The targets are doubled for CI hardware: analysis under 120 s cold and 10 s warm, full generation
under 10 minutes. Run with ``pytest -m slow tests/perf``; the timings are printed with ``-s``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import orchestrator
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.state import WizardState

from .conftest import record

pytestmark = pytest.mark.slow

TOLERANCE = 2.0  # CI hardware allowance over the section 45 targets
COLD_S = 60 * TOLERANCE
WARM_S = 5 * TOLERANCE
GENERATE_S = 10 * 60
REGENERATE_S = 60 * TOLERANCE  # section 45: a regeneration without changes, under a minute


def _analyze(pack: Path) -> tuple[float, WizardState]:
    state = WizardState(pack_sources=[pack], target=None)
    started = time.perf_counter()
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return time.perf_counter() - started, state


def test_inventory_and_analysis_cold_then_warm(
    big_pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    cold, state = _analyze(big_pack)
    assert state.catalog is not None and len(state.catalog.assets) >= 900
    warm, _ = _analyze(big_pack)
    print(f"\nanalysis of 1000 images: cold {cold:.1f}s, warm {warm:.1f}s")
    record("analysis of 1000 images, cold", cold)
    record("analysis of 1000 images, warm", warm)
    assert cold < COLD_S, f"cold analysis took {cold:.1f}s (limit {COLD_S:.0f}s)"
    assert warm < WARM_S, f"warm analysis took {warm:.1f}s (limit {WARM_S:.0f}s)"


@pytest.fixture(scope="module")
def generated(big_pack: Path, tmp_path_factory: pytest.TempPathFactory, godot_exe: Path):
    """One full generation of the big pack: ``(target, seconds)``, shared by the tests below
    (the cache folder is private to them for as long as they run)."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("RPGGEN_CACHE_DIR", str(tmp_path_factory.mktemp("perf_cache")))
        target = tmp_path_factory.mktemp("perf_game") / "game"
        cfg = orchestrator.default_config_for_pack(big_pack, "Big Pack")
        started = time.perf_counter()
        result = orchestrator.run_in_memory(
            cfg, None, target, godot_exe, placeholders=["PLAYER", "GROUND"]
        )
        elapsed = time.perf_counter() - started
        assert result.ok, [
            (i.code, i.message) for i in result.issues if i.severity.value == "error"
        ]
        yield target, elapsed


def test_full_generation_of_a_big_pack(generated) -> None:
    _target, elapsed = generated
    print(f"\nfull generation of 1000 images: {elapsed:.1f}s")
    record("full generation of 1000 images", elapsed)
    assert elapsed < GENERATE_S, f"generation took {elapsed:.0f}s (limit {GENERATE_S}s)"


def test_a_regeneration_without_changes_is_fast(generated, godot_exe: Path) -> None:
    target, _elapsed = generated
    started = time.perf_counter()
    result = orchestrator.run(
        target / paths.CONFIG,
        target,
        godot_exe,
        placeholders=["PLAYER", "GROUND"],  # as in the first run: the pack has neither
        force_while_open=True,
    )
    elapsed = time.perf_counter() - started
    print(f"\nregeneration of 1000 images, nothing changed: {elapsed:.1f}s")
    record("regeneration of 1000 images, nothing changed", elapsed)
    assert result.ok, [(i.code, i.message) for i in result.issues if i.severity.value == "error"]
    assert elapsed < REGENERATE_S, f"regeneration took {elapsed:.0f}s (limit {REGENERATE_S:.0f}s)"


def test_parallel_analysis_is_faster_than_the_serial_one(
    big_pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The image analysis of ``analyzer.prewarm`` with and without its process pool (T12.17), on
    the 1,000 images of the big pack; the whole analysis is timed too, for the trend."""
    from rpggen.core import analyzer, archive, inventory

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache_parallel"))
    parallel_total, _state = _analyze(big_pack)
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache_serial"))
    monkeypatch.setattr(analyzer, "prewarm", lambda *a, **k: {})
    serial_total, _state = _analyze(big_pack)
    monkeypatch.undo()
    opened = archive.open_pack(big_pack, set())
    inv = inventory.build_inventory(opened, use_cache=False)

    def timed(threshold: int) -> float:
        monkeypatch.setattr(analyzer, "POOL_THRESHOLD", threshold)
        started = time.perf_counter()
        found = analyzer.prewarm(inv, opened.root, use_cache=False)
        elapsed = time.perf_counter() - started
        assert len(found) >= 900
        return elapsed

    serial = timed(10**9)
    parallel = timed(32)
    cpus = os.cpu_count() or 1
    print(
        f"\nanalysis of 1000 images: whole {serial_total:.1f}s serial, {parallel_total:.1f}s "
        f"parallel; the image analysis alone {serial:.1f}s serial, {parallel:.1f}s parallel "
        f"({serial / parallel:.1f}x on {cpus} cpus)"
    )
    record("cold analysis, serial", serial_total)
    record("cold analysis, parallel", parallel_total)
    record("image analysis, serial", serial)
    record("image analysis, parallel", parallel)
    if cpus >= 4:
        assert serial / parallel >= 2.0, f"only {serial / parallel:.1f}x faster on {cpus} cpus"
