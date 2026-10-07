"""Milestone M4 on the sample pack: placement scenes, the building round trip, Y-sort checks."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from rpggen import jsonio
from rpggen.core import archive, catalog, config, godot, inventory, mapping, orchestrator, profiles

pytestmark = pytest.mark.integration

SAMPLE = Path(__file__).resolve().parents[2] / "sample_pack"


def _generate(godot_exe: Path, target: Path, layers: list[str] | None = None):
    opened = archive.open_pack(SAMPLE, set(), pack_id="sample_pack")
    inv = inventory.build_inventory(opened)
    cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
    cfg = config.default_for("Sample RPG", [config.pack_ref_from_source(SAMPLE, "sample_pack")])
    cfg.starter = mapping.default_starter(cat, "turn_based")
    if layers is not None:
        cfg.map_layers = layers
    return orchestrator.run_in_memory(cfg, None, target, godot_exe)


@pytest.fixture(scope="module")
def sample(godot_exe: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    cache = tmp_path_factory.mktemp("cache")
    old = os.environ.get("RPGGEN_CACHE_DIR")
    os.environ["RPGGEN_CACHE_DIR"] = str(cache)
    try:
        profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
        target = tmp_path_factory.mktemp("m4") / "out"
        result = _generate(godot_exe, target)
        assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
        yield target
    finally:
        if old is None:
            os.environ.pop("RPGGEN_CACHE_DIR", None)
        else:
            os.environ["RPGGEN_CACHE_DIR"] = old


def _nodes(tscn: Path) -> list[str]:
    return re.findall(r'^\[node name="([^"]+)"', tscn.read_text(encoding="utf-8"), re.M)


def test_all_m1_and_m4_smoke_steps_pass_for_real(sample: Path) -> None:
    smoke = jsonio.read(sample / "rpggen/results/smoke_results.json")
    assert smoke["ok"] is True
    names = [i["name"] for i in smoke["items"]]
    i = names.index("enter_building")
    assert names[i : i + 3] == ["enter_building", "exit_building", "decor_blocks"]
    assert all(i["ok"] for i in smoke["items"])
    log = (sample / "rpggen/logs/godot_smoke.log").read_text(encoding="utf-8", errors="replace")
    assert "step passes" not in log, "a smoke step passed only because nothing was there to test"


def test_ysort_checks_report_nothing_on_the_sample(sample: Path) -> None:
    results = jsonio.read(sample / "rpggen/results/validation_results.json")
    codes = [i["code"] for i in results["issues"]]
    assert "VAL-014" not in codes and "VAL-015" not in codes, codes
    checks = {i["check"] for i in results["items"]}
    assert {"ysort_origin", "ysort_parent"} <= checks


def test_starter_map_has_every_config_layer_and_the_reserved_spots(sample: Path) -> None:
    names = _nodes(sample / "game/maps/starter_map.tscn")
    for expected in (
        "Ground", "GroundDetails", "Walls", "YSorted", "Props", "Entities", "Overhead",
        "Triggers", "SpawnPoints", "default", "npc_spot", "enemy_spot", "chest_spot", "Player",
    ):  # fmt: skip
        assert expected in names, expected
    assert names.index("Walls") < names.index("YSorted") < names.index("Overhead")


def test_building_entrance_is_overridden_on_the_instance(sample: Path) -> None:
    text = (sample / "game/maps/starter_map.tscn").read_text(encoding="utf-8")
    assert 'target_map = "res://game/maps/interior_1.tscn"' in text
    assert '[editable path="YSorted/Entities/house"]' in text
    interior = (sample / "game/maps/interior_1.tscn").read_text(encoding="utf-8")
    assert 'target_map = "res://game/maps/starter_map.tscn"' in interior
    assert "sample_pack__objects__town__house_exit" in interior


def test_object_scenes_and_index(sample: Path) -> None:
    index = jsonio.read(sample / "rpggen/object_index.json")
    assert list(index) == sorted(index)
    assert index["sample_pack.objects.town#house"].endswith(
        "sample_pack__objects__town__house.tscn"
    )
    for path in index.values():
        assert (sample / path.removeprefix("res://")).is_file(), path
    chest = (sample / "generated/scenes/objects/sample_pack__items__chest.tscn").read_text(
        encoding="utf-8"
    )
    assert "StaticBody2D" in chest  # a chest tag builds a solid object, not a prop


def test_tileset_has_a_pattern_for_each_object(sample: Path) -> None:
    text = (sample / "generated/tilesets/overworld.tres").read_text(encoding="utf-8")
    assert len(re.findall(r"^pattern_\d+ = ", text, re.M)) == 3  # house + two trees


def test_rebuilding_leaves_generated_files_and_maps_untouched(
    godot_exe: Path, sample: Path
) -> None:
    def snapshot() -> dict[str, str]:
        out = {}
        for folder in ("game", "generated", "rpggen/object_index.json"):
            root = sample / folder
            files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
            for p in files:
                out[p.relative_to(sample).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    before = snapshot()
    run = godot.run_godot(
        godot.find_console_exe(godot_exe),
        sample,
        ["--script", "res://generated/builder/build.gd"],
        timeout_s=godot.BUILD_TIMEOUT_S,
        log_name="rebuild",
        log_dir=sample / "rpggen" / "logs",
    )
    assert run.returncode == 0
    assert snapshot() == before


def test_custom_layers_are_honored(godot_exe: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    profiles.install_profile(SAMPLE / "sample.rpgprofile.json")
    result = _generate(godot_exe, tmp_path / "out", ["Ground", "Walls", "Fog", "Props"])
    assert result.ok, [f"{i.code}: {i.message}" for i in result.issues]
    names = _nodes(tmp_path / "out/game/maps/starter_map.tscn")
    assert {"Ground", "Walls", "Fog", "Props", "Entities"} <= set(names)
    assert not {"GroundDetails", "Overhead"} & set(names)
    assert names.index("Fog") < names.index("YSorted")
