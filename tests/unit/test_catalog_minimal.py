from __future__ import annotations

import json
from pathlib import Path

import pytest

from rpggen import jsonio, schema
from rpggen.core import catalog
from rpggen.errors import RpgGenError

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "test_packs" / "synthetic" / "basic16"
GOLDEN = REPO / "tests" / "golden" / "basic16.catalog.json"


def _build() -> catalog.Catalog:
    return catalog.build_minimal_catalog(PACK, "basic16", "assets/packs/basic16", 16)


def test_minimal_catalog_matches_golden() -> None:
    assert jsonio.dumps(_build().to_json()) == GOLDEN.read_text(encoding="utf-8")


def test_minimal_catalog_is_schema_valid_and_structured() -> None:
    cat = _build()
    schema.validate("catalog", cat.to_json())
    assert sorted(a.id for a in cat.assets) == [
        "basic16.characters.hero",
        "basic16.tiles.terrain",
    ]
    terrain = cat.asset("basic16.tiles.terrain")
    assert terrain is not None
    eff = catalog.effective(terrain)
    assert eff["role"] == "GROUND"
    assert set(eff["tile_overrides"]) == {f"{x},1" for x in range(8)}
    hero = catalog.effective(cat.asset("basic16.characters.hero"))
    assert hero["frame"] == [16, 24] and hero["origin"] == [8, 23]
    assert hero["animations"]["walk_left"]["frames"] == [[0, 1], [1, 1], [2, 1], [3, 1]]
    assert hero["animations"]["idle_up"]["frames"] == [[0, 3]]
    assert [t.name for t in cat.tilesets] == ["overworld"]
    assert cat.tilesets[0].sources == [{"asset": "basic16.tiles.terrain", "source_id": 0}]
    assert cat.id_allocations["tilesets"]["overworld"] == {"next_source_id": 1, "retired": []}


def test_allocate_source_id_never_reuses() -> None:
    cat = catalog.Catalog()
    assert [cat.allocate_source_id("t") for _ in range(3)] == [0, 1, 2]
    assert cat.id_allocations["tilesets"]["t"]["next_source_id"] == 3


def test_save_load_roundtrip(tmp_path: Path) -> None:
    cat = _build()
    path = tmp_path / "asset_catalog.json"
    catalog.save(cat, path)
    loaded = catalog.load(path)
    assert loaded.to_json() == cat.to_json()
    assert path.read_text(encoding="utf-8") == GOLDEN.read_text(encoding="utf-8")


def test_load_rejects_newer_catalog(tmp_path: Path) -> None:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    data["catalog_version"] = 99
    path = tmp_path / "c.json"
    jsonio.write(path, data)
    with pytest.raises(RpgGenError) as ei:
        catalog.load(path)
    assert ei.value.code == "CAT-003"


def test_sorting_is_deterministic() -> None:
    cat = _build()
    cat.assets.reverse()
    assert [a["id"] for a in cat.to_json()["assets"]] == sorted(a.id for a in cat.assets)
