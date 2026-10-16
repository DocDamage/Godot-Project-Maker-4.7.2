"""The isometric readers of T17.33: sets of two terrains joined at the corners of the diamond
(the synthetic pack ``iso_corners``, after Kenney's *Medieval Town* plates), plain grounds of
whole diamonds and their variants, and a see-through patch laid on a ground (*Lords Of Pain*)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from rpggen import schema
from rpggen.core import archive, catalog, inventory
from rpggen.core.adapters import iso_sheets
from rpggen.core.terrain import iso

REPO = Path(__file__).resolve().parents[2]
SYNTH = REPO / "test_packs" / "synthetic"
sys.path.insert(0, str(REPO / "tools"))
import make_synthetic_packs as synth  # noqa: E402

PREFIX = "iso_corners.isometric_plaza_kit.png."


@pytest.fixture(autouse=True)
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


@pytest.fixture(scope="module")
def facets() -> dict[str, dict]:
    opened = archive.open_pack(SYNTH / "iso_corners", set())
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=False)
    schema.validate("catalog", cat.to_json())
    out = {}
    for a in cat.assets:
        found = catalog.effective(a).get(iso.FACET)
        if isinstance(found, dict):
            out[a.id.removeprefix(PREFIX)] = found
    return out


def test_the_plates_are_one_set_of_two_terrains_joined_at_the_corners(
    facets: dict[str, dict],
) -> None:
    plates = {k: f for k, f in facets.items() if k.startswith("plate_") and k != "plate_wood"}
    assert len(plates) == len(synth.IC_WAYS)
    assert {f["set"] for f in plates.values()} == {"iso_plate_corners"}
    first = plates["plate_00"]
    assert (first["mode"], first["shape"]) == ("corners", "corners")
    assert len(first["terrains"]) == 2
    # each plate's corners are its way: pavement (the light tone, 1) where the way names it
    for k, way in enumerate(synth.IC_WAYS):
        peering = plates[f"plate_{k:02d}"]["peering"]
        for corner in synth.IC_CORNERS:
            assert peering[iso.PEERING[corner]] == (1 if corner in way else 0), (k, corner)
        assert all(peering[iso.PEERING[side]] == -1 for side in iso.SIDES)
    assert plates["plate_00"]["terrain"] == 0
    assert plates["plate_13"]["terrain"] == 1


def test_a_plate_of_another_colour_is_no_tone_of_the_set(facets: dict[str, dict]) -> None:
    wood = facets["plate_wood"]
    assert wood["set"] != "iso_plate_corners"
    assert wood["shape"] == "plain"


def test_a_flat_tone_drawn_often_is_not_taken_for_one_of_the_set() -> None:
    road, pave, wood = (np.asarray(c[:3], dtype=np.float32) / 255.0 for c in
                        (synth.IC_ROAD, synth.IC_PAVE, synth.IC_WOOD))  # fmt: skip
    rows = [[pave if c in way else road for c in synth.IC_CORNERS] for way in synth.IC_WAYS]
    # more corners of wood than of either tone, but never in a plate with the pavement
    rows += [[wood] * 4] * 10
    tones = iso._two_tones(rows)
    assert tones is not None
    dark, light = tones
    assert float(np.abs(dark - road).mean()) < 0.01
    assert float(np.abs(light - pave).mean()) < 0.01


def test_a_plain_ground_has_its_plainest_piece_for_its_middle(facets: dict[str, dict]) -> None:
    grass = {k: f for k, f in facets.items() if k.startswith("grass_")}
    assert len(grass) == 3
    assert len({f["set"] for f in grass.values()}) == 1
    assert grass["grass_02"]["shape"] == "plain"
    assert "probability" not in grass["grass_02"]  # no specks: the main one
    for k in ("grass_01", "grass_03"):
        assert 0 < grass[k]["probability"] <= iso.MIDDLE_VARIANTS


def _piece(asset_id: str, rgba: np.ndarray) -> iso.Piece:
    origin = (rgba.shape[1] / 2, rgba.shape[0] / 2)
    foot = (rgba.shape[1], rgba.shape[0])
    found = iso.read_piece(asset_id, rgba, origin, foot)
    assert found is not None
    sides, corners, middle, outside = found
    return iso.Piece(
        asset_id, ("pack",), sides, corners, middle, outside, rgba, origin, foot, set()
    )


def _asset(asset_id: str, tags: list[str]) -> catalog.Asset:
    detected = {"usage": "iso_tile", "role": "GROUND", "tags": tags}
    return catalog.Asset(asset_id, "pack", asset_id, "0" * 64, "image", "OK", detected)


def test_a_patch_laid_on_the_ground_is_a_variant_of_it() -> None:
    d = iso_sheets.Diamond(*synth.IT_FOOT)
    ground = np.asarray(synth._ic_grass(0))
    # a see-through stain larger than the diamond, opaque in its middle (Lords Of Pain)
    patch = np.zeros((d.height * 2, d.width * 2, 4), dtype=np.uint8)
    patch[..., :3] = (60, 110, 50)
    patch[d.height // 2 : d.height * 3 // 2, d.width // 2 : d.width * 3 // 2, 3] = 255
    laid = iso_sheets.patch_on(ground, patch, d)
    assert laid is not None
    assert laid.shape == ground.shape
    middle = (d.height // 2, d.width // 2)
    assert tuple(laid[middle][:3]) == (60, 110, 50)
    # toward its edges it fades into the ground, so it meets the ground's other diamonds
    near_edge = (d.height // 2, 0)
    gap = np.abs(laid[near_edge][:3].astype(int) - ground[near_edge][:3].astype(int))
    assert int(gap.max()) <= 2
    assert iso_sheets.patch_on(ground, patch[:4, :4], d) is None

    # the variant is of the ground's plain set, laid now and then, whatever its colour
    by_id = {
        "pack.ground": _asset("pack.ground", []),
        "pack.stain": _asset("pack.stain", ["variant_of:pack.ground"]),
    }
    pieces = [_piece("pack.ground", ground), _piece("pack.stain", laid)]
    assert iso.plain_sets(pieces, by_id, set()) == 1
    main = by_id["pack.ground"].detected[iso.FACET]
    stain = by_id["pack.stain"].detected[iso.FACET]
    assert main["set"] == stain["set"]
    assert "probability" not in main
    assert stain["probability"] == pytest.approx(
        iso.MIDDLE_VARIANTS / (1 - iso.MIDDLE_VARIANTS), abs=1e-4
    )


def test_a_variant_of_a_picture_outside_the_set_is_a_ground_of_its_own() -> None:
    # Kenney's Nature: the turns of a grass whose first turn is no plain ground
    plain = np.asarray(synth._ic_grass(0))
    specked = np.asarray(synth._ic_grass(3))
    by_id = {
        "pack.turn_1": _asset("pack.turn_1", ["variant_of:pack.turn_0"]),
        "pack.turn_2": _asset("pack.turn_2", ["variant_of:pack.turn_0"]),
    }
    pieces = [_piece("pack.turn_1", specked), _piece("pack.turn_2", plain)]
    assert iso.plain_sets(pieces, by_id, set()) == 1
    assert "probability" not in by_id["pack.turn_2"].detected[iso.FACET]
    assert 0 < by_id["pack.turn_1"].detected[iso.FACET]["probability"] < 1
