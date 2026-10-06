from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from rpggen.core.analyzer import grid, image_facts

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


def _detect(pack: str, rel: str, **kw):
    a = image_facts.load_rgba(SYNTH / pack / rel)
    return grid.detect_grid(a, image_facts.occupancy(a), **kw)


def _expected_tile_sheets() -> list[tuple[str, str, dict]]:
    cases = []
    for exp_file in sorted(SYNTH.glob("*.expected.json")):
        pack = exp_file.name.removesuffix(".expected.json")
        for rel, facts in json.loads(exp_file.read_text(encoding="utf-8")).items():
            if facts.get("usage") == "tiles" and "#" not in rel and "cell" in facts:
                cases.append((pack, rel, facts))
    return cases


@pytest.mark.parametrize(("pack", "rel", "facts"), _expected_tile_sheets())
def test_top_candidate_matches_expected(pack: str, rel: str, facts: dict) -> None:
    pack_dir = pack
    top = _detect(pack_dir, rel)[0]
    assert list(top.cell) == facts["cell"], (rel, top)
    assert list(top.margin) == facts["margin"], (rel, top)
    assert list(top.separation) == facts["separation"], (rel, top)


def test_gutterless48_beats_24() -> None:
    cands = _detect("gutterless48", "Tilesets/ground.png")
    assert cands[0].cell == (48, 48)
    sizes = [c.cell[0] for c in cands]
    if 24 in sizes:
        assert cands[sizes.index(24)].score < cands[0].score


def test_gutter32_has_margin_and_separation() -> None:
    top = _detect("gutter32", "tiles/world.png")[0]
    assert top.margin == (1, 1) and top.separation == (1, 1)
    assert top.total_cells == 30 and top.nonempty_cells == 30


def test_candidates_are_sorted_and_limited() -> None:
    cands = _detect("mixed", "tiles/ground16.png")
    assert 1 <= len(cands) <= 5
    scores = [c.score for c in cands]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= c.score <= 1.0 for c in cands)


def test_opaque_noise_scores_low() -> None:
    rng = np.random.default_rng(1234)
    a = np.zeros((64, 64, 4), dtype=np.uint8)
    a[..., :3] = rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8)
    a[..., 3] = 255
    cands = grid.detect_grid(a, image_facts.occupancy(a))
    assert cands
    assert all(c.score < 0.5 for c in cands)


def test_blank_image_gives_low_scores_or_none() -> None:
    a = np.zeros((32, 32, 4), dtype=np.uint8)
    cands = grid.detect_grid(a, image_facts.occupancy(a))
    assert all(c.score < 0.6 for c in cands)


def test_non_square_mode_returns_rectangular_cells() -> None:
    # Directional character sheets are located by frames.py (gap analysis); here we only
    # require the non-square mode to be well-formed.
    cands = _detect("basic16", "characters/hero.png", square=False)
    assert 1 <= len(cands) <= 5
    assert any(c.cell[0] != c.cell[1] for c in cands)


def test_pack_prior_boosts_a_size() -> None:
    base = _detect("mixed", "items/item_01.png")
    boosted = _detect("mixed", "items/item_01.png", pack_prior={16: 1.0})
    by_cell = {c.cell: c.score for c in base}
    for c in boosted:
        if c.cell[0] == 16 and c.cell in by_cell:
            assert c.score >= by_cell[c.cell]


def test_confidence_formula() -> None:
    top = grid.GridCandidate((16, 16), (0, 0), (0, 0), 0.9, 10, 10)
    second = grid.GridCandidate((8, 8), (0, 0), (0, 0), 0.5, 10, 40)
    assert grid.confidence([top, second]) == pytest.approx(0.9 * min(1.0, 0.5 + 0.8))
    assert grid.confidence([top]) == pytest.approx(0.9)
    assert grid.confidence([]) == 0.0
