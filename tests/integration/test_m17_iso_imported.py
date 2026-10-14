"""T17.28: imported maps in the isometric view. The pack drawn by ``tests/iso_tiled_pack.py`` (in
the manner of Kenney's miniature packs, with a Tiled sample of two isometric maps in a zip of
samples) is generated as an isometric turn-based game whose starter map is the sample and which
imports the cellar: the maps are painted on the diamonds of ``iso.tres`` with the sample's own
pictures, the walls block, the objects stand on the middle of their diamonds, the doors join the
two maps, and the game passes its smoke sequence. The same pack seen from above imports neither
map and says so (TILE-013)."""

from __future__ import annotations

import importlib.util
import os
import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, inventory, iso_math, orchestrator, requirements

pytestmark = [pytest.mark.integration, pytest.mark.isometric]

REPO = Path(__file__).resolve().parents[2]
BASE = "iso_tiled.samples.tiled_sample_extracted."
SAMPLE, CELLAR = BASE + "sample", BASE + "cellar"
CELLAR_SCENE = "game/maps/imported/iso_tiled/samples_tiled_sample_extracted_cellar.tscn"
SELECTION = {"include": [SAMPLE, CELLAR], "starter": SAMPLE}


def _drawn() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "iso_tiled_pack", REPO / "tests" / "iso_tiled_pack.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DRAWN = _drawn()


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(folder)
    try:
        yield folder
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


@pytest.fixture(scope="module")
def pack(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return DRAWN.draw(tmp_path_factory.mktemp("iso_tiled_pack"))


def _config(pack: Path, projection: str) -> config.GeneratorConfig:
    cfg = config.default_for(
        "Cellar Door", [config.pack_ref_from_source(pack, "iso_tiled")], archetype="turn_based"
    )
    cfg.projection = projection
    cfg.imported_maps = dict(SELECTION)
    return cfg


def _errors(result) -> list[str]:  # noqa: ANN001
    return [f"{i.code}: {i.message}" for i in result.issues if i.severity.value == "error"]


@pytest.fixture(scope="module")
def isometric(godot_exe: Path, cache: Path, pack: Path, tmp_path_factory: pytest.TempPathFactory):  # noqa: ANN201
    target = tmp_path_factory.mktemp("iso_imported") / "out"
    result = orchestrator.run_in_memory(_config(pack, "isometric"), None, target, godot_exe)
    assert result.ok, _errors(result)
    return target, result


def _nodes(scene: str) -> dict[str, dict[str, str]]:
    """The nodes of a saved scene by their path (``parent/name``), with their properties."""
    out: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in scene.splitlines():
        head = re.match(r'\[node name="([^"]+)"(?: type="([^"]+)")?(?: parent="([^"]*)")?', line)
        if head:
            name, kind, parent = head.group(1), head.group(2) or "", head.group(3)
            path = name if parent in (None, ".") else f"{parent}/{name}"
            current = out.setdefault(path if parent is not None else ".", {"type": kind})
            continue
        if current is not None and " = " in line and not line.startswith("["):
            key, _, value = line.partition(" = ")
            current[key.strip()] = value.strip()
    return out


def _at(cell: tuple[int, int]) -> str:
    x, y = iso_math.cell_to_screen(cell[0], cell[1], *DRAWN.FOOT)
    return f"Vector2({x:g}, {y:g})"


def test_the_sample_is_the_starter_map_on_diamonds_and_the_game_plays(isometric) -> None:  # noqa: ANN001
    target, result = isometric
    assert not [i for i in result.issues if i.code == "TILE-013"]
    smoke = jsonio.read(target / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True and all(i["ok"] for i in smoke["items"]), smoke["issues"]
    validation = jsonio.read(target / "rpggen/results/validation_results.json")
    round_trip = {
        i["target"]: i["ok"] for i in validation["items"] if i.get("check") == "map_round_trip"
    }
    assert round_trip["game/maps/starter_map.tscn"] is True
    assert round_trip[CELLAR_SCENE] is True
    nodes = _nodes((target / "game/maps/starter_map.tscn").read_text(encoding="utf-8"))
    assert nodes["Ground"]["type"] == "TileMapLayer" and "tile_map_data" in nodes["Ground"]
    # the layers that are not the ground sort with who walks there; the second floor is higher
    assert nodes["YSorted/Walls"]["type"] == "TileMapLayer"
    assert nodes["YSorted/Upper"]["position"] == f"Vector2(0, {DRAWN.UPPER_OFFSET})"
    assert nodes["YSorted/Walls"]["y_sort_enabled"] == "true"
    # the wall pieces block their diamonds; the crate does not
    walls = sorted(k for k in nodes if k.startswith("ImportedWalls/"))
    assert len(walls) == len(DRAWN.WALL_CELLS)
    assert nodes["ImportedWalls/Wall_0_0"]["position"] == _at((0, 0))
    assert f"ImportedWalls/Wall_{DRAWN.CRATE[0]}_{DRAWN.CRATE[1]}" not in nodes
    # objects stand on the middle of their diamonds
    assert nodes["SpawnPoints/default"]["position"] == _at(DRAWN.SPAWN)
    assert nodes["SpawnPoints/Sign_notice"]["position"] == _at(DRAWN.SIGN)
    door = nodes["Triggers/Door_to_cellar"]
    assert door["position"] == _at(DRAWN.DOOR)
    assert CELLAR_SCENE in door["target_map"] and door["target_spawn"] == '&"from_sample"'
    cellar = _nodes((target / CELLAR_SCENE).read_text(encoding="utf-8"))
    assert cellar["SpawnPoints/from_sample"]["position"] == _at(DRAWN.CELLAR_SPAWN)
    assert "starter_map.tscn" in cellar["Triggers/Door_back"]["target_map"]


def test_the_tile_set_holds_the_sample_pictures_for_the_maps_alone(isometric) -> None:  # noqa: ANN001
    target, _result = isometric
    cat = catalog.Catalog.from_json(jsonio.read(target / "rpggen/asset_catalog.json"))
    tdef = next(t for t in cat.tilesets if t.projection == "isometric")
    only = sorted(k for k, v in tdef.tiles.items() if v.get("maps_only"))
    assert only == sorted(BASE + "sprites." + n.lower() for n in DRAWN.TILES.values())
    sprites = [a for a in cat.assets if a.id.startswith(BASE + "sprites.")]
    assert sprites and all(a.status == "UNUSED" for a in sprites)


def test_seen_from_above_the_isometric_maps_are_not_imported(
    godot_exe: Path, cache: Path, pack: Path, tmp_path: Path
) -> None:
    opened = archive.open_pack(pack, set())
    cat, _issues, _made = catalog.assemble([(opened, inventory.build_inventory(opened))], None, [])
    cfg = _config(pack, "top_down")
    missing = [
        i.detail["role"] for i in requirements.check(cat, cfg) if i.severity.value == "error"
    ]
    result = orchestrator.run_in_memory(
        cfg, None, tmp_path / "out", godot_exe, placeholders=missing
    )
    assert result.ok, _errors(result)
    said = sorted(i.detail["map"] for i in result.issues if i.code == "TILE-013")
    assert said == [CELLAR, SAMPLE]
    assert not (tmp_path / "out/game/maps/imported").exists()
    starter = (tmp_path / "out/game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert "ImportedWalls" not in starter and "Door_to_cellar" not in starter
