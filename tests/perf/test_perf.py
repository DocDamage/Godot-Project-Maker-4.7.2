"""Performance targets of ARCHITECTURE section 45 on a 1,000-image pack (T10.08).

The targets are doubled for CI hardware: analysis under 120 s cold and 10 s warm, full generation
under 10 minutes. Run with ``pytest -m slow tests/perf``; the timings are printed with ``-s``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from rpggen.core import orchestrator
from rpggen.core.orchestrator import Callbacks
from rpggen.gui import workers
from rpggen.gui.state import WizardState

pytestmark = pytest.mark.slow

TOLERANCE = 2.0  # CI hardware allowance over the section 45 targets
COLD_S = 60 * TOLERANCE
WARM_S = 5 * TOLERANCE
GENERATE_S = 10 * 60


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
    assert cold < COLD_S, f"cold analysis took {cold:.1f}s (limit {COLD_S:.0f}s)"
    assert warm < WARM_S, f"warm analysis took {warm:.1f}s (limit {WARM_S:.0f}s)"


def test_full_generation_of_a_big_pack(
    big_pack: Path, tmp_path: Path, godot_exe: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    cfg = orchestrator.default_config_for_pack(big_pack, "Big Pack")
    target = tmp_path / "game"
    started = time.perf_counter()
    result = orchestrator.run_in_memory(
        cfg, None, target, godot_exe, placeholders=["PLAYER", "GROUND"]
    )
    elapsed = time.perf_counter() - started
    print(f"\nfull generation of 1000 images: {elapsed:.1f}s")
    assert result.ok, [(i.code, i.message) for i in result.issues if i.severity.value == "error"]
    assert elapsed < GENERATE_S, f"generation took {elapsed:.0f}s (limit {GENERATE_S}s)"
    assert (target / "project.godot").is_file()
    assert os.path.getsize(target / "rpggen/asset_catalog.json") > 0
