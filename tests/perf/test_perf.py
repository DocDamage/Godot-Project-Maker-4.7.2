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
REGENERATE_S = 60 * TOLERANCE  # section 45: a regeneration with every check, under a minute
# T15.20: nothing changed, so no check is repeated. 15 s on the development machine; a Windows
# runner of CI took 30 s for it on 2026-10-12 (and 20 s or less in the runs before), so the
# limit is what tells a repeat (a full regeneration takes 90 s there) from one that is slow
REGENERATE_UNCHANGED_S = 45.0
SIDE_SAMPLE_S = 90 * TOLERANCE  # T14.11: the side-view sample as a metroidvania, played through
ARCADE_SAMPLE_S = 60 * TOLERANCE  # T16.18: a sample of an arcade kind as that kind, played through
M17_SAMPLE_S = 120.0  # T17.17: the farm sample, and the isometric one, each played through


def _analyze(pack: Path) -> tuple[float, WizardState]:
    state = WizardState(pack_sources=[pack], target=None)
    started = time.perf_counter()
    workers.apply_analysis(state, workers.analyze_packs(state, callbacks=Callbacks()))
    return time.perf_counter() - started, state


def _errors(result) -> str:  # type: ignore[no-untyped-def]
    """Every error of a run, a line each: pytest shortens a list to its first and last entries,
    and the one in the middle is the one that says which step of the game failed."""
    return "\n".join(f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error")


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


def _regenerate(target: Path, godot_exe: Path, full_checks: bool) -> tuple[float, object]:
    started = time.perf_counter()
    result = orchestrator.run(
        target / paths.CONFIG,
        target,
        godot_exe,
        placeholders=["PLAYER", "GROUND"],  # as in the first run: the pack has neither
        force_while_open=True,
        full_checks=full_checks,
    )
    return time.perf_counter() - started, result


def test_a_regeneration_without_changes_repeats_no_check(generated, godot_exe: Path) -> None:
    target, _elapsed = generated
    elapsed, result = _regenerate(target, godot_exe, full_checks=False)
    print(f"\nregeneration of 1000 images, nothing changed: {elapsed:.1f}s")
    record("regeneration of 1000 images, nothing changed", elapsed)
    assert result.ok, _errors(result)
    assert elapsed < REGENERATE_UNCHANGED_S, (
        f"regeneration took {elapsed:.0f}s (limit {REGENERATE_UNCHANGED_S:.0f}s)"
    )


def test_a_full_regeneration_is_fast(generated, godot_exe: Path) -> None:
    target, _elapsed = generated
    elapsed, result = _regenerate(target, godot_exe, full_checks=True)
    print(f"\nregeneration of 1000 images, full: {elapsed:.1f}s")
    record("regeneration of 1000 images, full", elapsed)
    assert result.ok, _errors(result)
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

    # the best of a few timings each: on a shared 4-cpu CI runner one timing is noisy enough to
    # read 1.8x where the analysis is 2x or more (seen on three runs in a day, on code whose
    # speed-up measured the same as before on a 20-cpu machine)
    serial = min(timed(10**9) for _ in range(2))
    parallel = min(timed(32) for _ in range(3))
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
    # 2x where there are cores enough for it; a CI runner's 4 cpus are two cores with two threads
    # each, which gave 1.6x to 1.9x on 2026-10-14 for code that gives 3x on a 20-cpu machine
    wanted = 2.0 if cpus >= 8 else 1.5 if cpus >= 4 else 0.0
    assert serial / parallel >= wanted, f"only {serial / parallel:.1f}x faster on {cpus} cpus"


def test_the_side_view_sample_generates_as_a_metroidvania_in_time(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole run on the side-view sample pack (T14.11): analysis, the six rooms, validation
    and the sixteen smoke steps, from a cold cache."""
    from rpggen.core import archive, catalog, config, inventory, mapping, profiles

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    pack = paths.sample_pack_side_root()
    profiles.install_profile(pack / "sample_side.rpgprofile.json")
    started = time.perf_counter()
    opened = archive.open_pack(pack, set(), pack_id="sample_pack_side")
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        "Sample Cave",
        [config.pack_ref_from_source(pack, "sample_pack_side")],
        archetype="metroidvania",
    )
    cfg.starter = mapping.default_starter(cat, "metroidvania")
    result = orchestrator.run_in_memory(cfg, None, tmp_path / "game", godot_exe)
    elapsed = time.perf_counter() - started
    print(f"\nmetroidvania from the side-view sample: {elapsed:.1f}s")
    record("metroidvania from the side-view sample", elapsed)
    assert result.ok, _errors(result)
    assert elapsed < SIDE_SAMPLE_S, f"took {elapsed:.0f}s (limit {SIDE_SAMPLE_S:.0f}s)"


@pytest.mark.parametrize(
    ("key", "what"),
    [
        ("shmup", "shoot 'em up from the Star lane sample"),
        ("gun", "run and gun from the Jungle line sample"),
        ("race", "racing game from the Dirt cup sample"),
    ],
)
def test_an_arcade_sample_generates_as_its_kind_in_time(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, what: str
) -> None:
    """The whole run on the sample pack of each arcade kind (T16.18): analysis, the stages or
    tracks, validation and the kind's own smoke sequence to the credits, from a cold cache."""
    from rpggen.core import archive, catalog, config, inventory, mapping, profiles
    from rpggen.gui.models import project_model

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    sample = project_model.sample(key)
    assert sample.key == key
    pack = paths.sample_pack_dir(sample.folder)
    profiles.install_profile(pack / sample.profile)
    started = time.perf_counter()
    opened = archive.open_pack(pack, set(), pack_id=sample.folder)
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        sample.name,
        [config.pack_ref_from_source(pack, sample.folder)],
        archetype=sample.archetype,
    )
    cfg.starter = mapping.default_starter(cat, sample.archetype)
    result = orchestrator.run_in_memory(cfg, None, tmp_path / "game", godot_exe)
    elapsed = time.perf_counter() - started
    print(f"\n{what}: {elapsed:.1f}s")
    record(what, elapsed)
    assert result.ok, _errors(result)
    assert elapsed < ARCADE_SAMPLE_S, f"took {elapsed:.0f}s (limit {ARCADE_SAMPLE_S:.0f}s)"


@pytest.mark.parametrize(
    ("key", "what"),
    [
        ("farm", "farm from the Green acre sample"),
        ("iso", "isometric turn-based game from the Stone isle sample"),
    ],
)
def test_a_sample_of_m17_generates_as_its_kind_in_time(
    godot_exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, what: str
) -> None:
    """The whole run on each of the two sample packs of M17 (T17.17): analysis, the plans, the
    maps, validation and the kind's own smoke sequence, from a cold cache. The farm in the view
    from above, the isle as a turn-based game in the isometric view."""
    from rpggen.core import archive, catalog, config, inventory, mapping, profiles
    from rpggen.gui.models import project_model

    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    sample = project_model.sample(key)
    assert sample.key == key
    pack = paths.sample_pack_dir(sample.folder)
    profiles.install_profile(pack / sample.profile)
    started = time.perf_counter()
    opened = archive.open_pack(pack, set(), pack_id=sample.folder)
    cat, _issues, _generated = catalog.assemble(
        [(opened, inventory.build_inventory(opened))], None, []
    )
    cfg = config.default_for(
        sample.name,
        [config.pack_ref_from_source(pack, sample.folder)],
        archetype=sample.archetype,
    )
    cfg.projection = sample.projection
    cfg.starter = mapping.default_starter(cat, sample.archetype, sample.projection)
    result = orchestrator.run_in_memory(cfg, None, tmp_path / "game", godot_exe)
    elapsed = time.perf_counter() - started
    print(f"\n{what}: {elapsed:.1f}s")
    record(what, elapsed)
    assert result.ok, _errors(result)
    assert elapsed < M17_SAMPLE_S, f"took {elapsed:.0f}s (limit {M17_SAMPLE_S:.0f}s)"
