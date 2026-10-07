from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from rpggen import paths
from rpggen.core import archive, inventory, profile_registry

REGISTRY = Path(__file__).resolve().parents[2] / "registry"
SCHEMA = Path(__file__).resolve().parents[2] / "rpggen" / "schema" / "profile.schema.json"


def _build_index_module():
    spec = importlib.util.spec_from_file_location(
        "registry_build_index", REGISTRY / "scripts/build_index.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_copy_is_in_step_with_the_app() -> None:
    assert (REGISTRY / "scripts/profile.schema.json").read_bytes() == SCHEMA.read_bytes()


def test_committed_index_is_current_and_the_client_reads_it() -> None:
    module = _build_index_module()
    index, failed = module.build(REGISTRY)
    assert not failed
    committed = json.loads((REGISTRY / "index.json").read_text(encoding="utf-8"))
    assert committed == index
    assert profile_registry.parse_index(committed) == committed or all(
        e["profile_id"] for e in profile_registry.parse_index(committed)
    )


def test_sample_pack_matches_its_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    opened = archive.open_pack(paths.sample_pack_root(), set())
    inv = inventory.build_inventory(opened)
    index = profile_registry.parse_index(
        json.loads((REGISTRY / "index.json").read_text(encoding="utf-8"))
    )
    found = profile_registry.candidates(index, [inv])
    assert [c.profile_id for c in found] == ["rpggen_sample_pack"]
    assert found[0].overlap >= 0.5


def test_validator_rejects_bad_profiles(tmp_path: Path) -> None:
    module = _build_index_module()
    good = json.loads((REGISTRY / "profiles/rpggen_sample_pack.rpgprofile.json").read_text("utf-8"))
    root = tmp_path / "reg"
    (root / "profiles").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "scripts/profile.schema.json").write_bytes(SCHEMA.read_bytes())
    cases = {
        "wrong_license": {**good, "profile_id": "wrong_license", "license": "MIT"},
        "id_mismatch": {**good, "profile_id": "something_else"},
        "extra_key": {**good, "profile_id": "extra_key", "run": "calc.exe"},
    }
    for name, data in cases.items():
        (root / "profiles" / f"{name}.rpgprofile.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
    (root / "profiles/garbage.rpgprofile.json").write_text("{", encoding="utf-8")
    index, failed = module.build(root)
    assert index == []
    assert set(failed) == {f"{n}.rpgprofile.json" for n in [*cases, "garbage"]}
