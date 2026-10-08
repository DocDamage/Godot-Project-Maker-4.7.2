from __future__ import annotations

import copy
from pathlib import Path

import pytest

from rpggen import paths, schema
from rpggen.core import archive, catalog, inventory, profiles
from rpggen.core.adapters import profile as profile_adapter
from rpggen.core.catalog import FolderRule
from rpggen.gui import edits

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path / "cache"


def _pack(name: str):
    opened = archive.open_pack(SYNTH / name, set())
    return opened, inventory.build_inventory(opened)


def _assemble(name: str, previous=None):
    opened, inv = _pack(name)
    cat, issues, _gen = catalog.assemble([(opened, inv)], previous, [])
    return cat, inv, issues


def _facets(asset: catalog.Asset) -> dict:
    return {k: v for k, v in catalog.effective(asset).items() if k != "roles_alt"}


def _edited_basic16():
    cat, inv, _ = _assemble("basic16")
    hero = next(a for a in cat.assets if a.id.endswith("hero"))
    cat = edits.set_override(cat, hero.id, "role", "NPC")
    cat = edits.set_override(cat, hero.id, "tags", ["guard"])
    return cat, inv, hero.id


META = {"title": "Basic 16 test", "author": "me", "license": "CC0-1.0"}


def test_export_includes_only_overridden_or_confirmed_assets_and_validates() -> None:
    cat, inv, hero = _edited_basic16()
    data = profiles.export_profile(cat, "basic16", inv, META)
    schema.validate("profile", data)
    assert data["profile_id"] == "basic_16_test"
    assert data["license"] == "CC0-1.0"
    assert "roles_alt" not in str(data["assets"])
    keys = set(data["assets"])
    assert any(k.endswith("hero.png") for k in keys)
    for asset in cat.assets:
        key = profiles.asset_key(asset, "basic16")
        assert (key in keys) == bool(asset.overrides or asset.status == "CONFIRMED")
    assert all(not k.startswith("assets/") for k in keys)  # relative to the pack


def test_license_defaults_to_cc0() -> None:
    cat, inv, _ = _edited_basic16()
    data = profiles.export_profile(cat, "basic16", inv, {"title": "T"})
    assert data["license"] == "CC0-1.0"


def test_fingerprint_is_the_largest_images_ties_by_path() -> None:
    _cat, inv = _assemble("mixed")[:2]
    fp = profiles.fingerprint(inv)
    sizes = {f.path: f.image["w"] * f.image["h"] for f in inv.files if f.kind == "image"}
    listed = list(fp["required_files"])
    assert len(listed) == min(20, len(sizes))
    assert listed == sorted(listed, key=lambda p: (-sizes[p], p))[: len(listed)]
    assert fp["min_match"] == 0.8


def test_match_ratio() -> None:
    cat, inv, _ = _edited_basic16()
    data = profiles.export_profile(cat, "basic16", inv, META)
    assert profiles.match_profile(data, inv) == 1.0
    changed = copy.deepcopy(data)
    first = next(iter(changed["fingerprint"]["required_files"]))
    changed["fingerprint"]["required_files"][first] = "0" * 64
    n = len(changed["fingerprint"]["required_files"])
    assert profiles.match_profile(changed, inv) == pytest.approx((n - 1) / n)
    assert profiles.match_profile(data, _pack("mixed")[1]) == 0.0


def test_round_trip_into_a_fresh_catalog(tmp_path: Path) -> None:
    cat, inv, hero = _edited_basic16()
    data = profiles.export_profile(cat, "basic16", inv, META)
    path = tmp_path / "x.rpgprofile.json"
    profiles.write_profile(data, path)
    profiles.install_profile(path)

    fresh, _inv, issues = _assemble("basic16")  # no previous: nothing but the profile remembers
    for key in data["assets"]:
        asset = next(a for a in fresh.assets if profiles.asset_key(a, "basic16") == key)
        original = next(a for a in cat.assets if a.id == asset.id)
        assert _facets(asset) == _facets(original)
    assert catalog.effective(fresh.asset(hero))["role"] == "NPC"
    assert fresh.packs[0].profile_id == "basic_16_test"
    assert any(i.code == "ADAPT-003" for i in issues)
    assert fresh.asset(hero).detected_by == "profile"
    assert fresh.asset(hero).status == "CONFIRMED"


def test_a_changed_file_is_left_to_normal_detection(tmp_path: Path) -> None:
    cat, inv, hero = _edited_basic16()
    data = profiles.export_profile(cat, "basic16", inv, META)
    hero_path = next(k for k in data["assets"] if k.endswith("hero.png"))
    data["fingerprint"]["required_files"][hero_path] = "f" * 64
    data["fingerprint"]["min_match"] = 0.0
    path = tmp_path / "y.rpgprofile.json"
    profiles.write_profile(data, path)
    profiles.install_profile(path)
    fresh, _inv, _issues = _assemble("basic16")
    assert fresh.asset(hero).detected_by != "profile"
    assert catalog.effective(fresh.asset(hero))["role"] != "NPC"


def test_below_min_match_the_adapter_does_not_apply(tmp_path: Path) -> None:
    cat, inv, _hero = _edited_basic16()
    data = profiles.export_profile(cat, "basic16", inv, META)
    data["fingerprint"]["required_files"] = {
        p: "0" * 64 for p in data["fingerprint"]["required_files"]
    }
    path = tmp_path / "z.rpgprofile.json"
    profiles.write_profile(data, path)
    profiles.install_profile(path)
    adapter = profile_adapter.ProfileAdapter()
    assert adapter.match(inv, Path(".")) == 0.0
    assert adapter.priority == 0


def test_no_installed_profiles_means_no_match() -> None:
    _cat, inv, _ = _assemble("basic16")
    assert profile_adapter.ProfileAdapter().match(inv, Path(".")) == 0.0
    assert profiles.installed() == []


def test_invalid_profile_files_are_ignored(_cache: Path) -> None:
    folder = paths.data_dir() / "profiles"
    folder.mkdir(parents=True)
    (folder / "bad.rpgprofile.json").write_text("{not json", encoding="utf-8")
    (folder / "wrong.rpgprofile.json").write_text('{"profile_version": 1}', encoding="utf-8")
    assert profiles.installed() == []


def test_folder_rules_tilesets_and_objects_round_trip(tmp_path: Path) -> None:
    cat, inv, _ = _assemble("objects_in_sheet")
    assert cat.objects
    sheet = cat.objects[0].sheet
    rejected = cat.objects[0].id
    cat = edits.reject_object(cat, rejected)
    cat = edits.add_folder_rule(cat, FolderRule("objects_in_sheet", "**/*.png", {"tags": ["pack"]}))
    cat = edits.confirm(cat, [sheet])
    data = profiles.export_profile(cat, "objects_in_sheet", inv, META)
    assert data["folder_rules"] and data["objects"]
    assert all("id" not in o and "sheet" not in o and "sheet_path" in o for o in data["objects"])
    path = tmp_path / "o.rpgprofile.json"
    profiles.write_profile(data, path)
    profiles.install_profile(path)

    fresh, _inv, _issues = _assemble("objects_in_sheet")
    assert [r.to_json() for r in fresh.folder_rules] == [
        r.to_json() for r in cat.folder_rules if r.pack_id == "objects_in_sheet"
    ]
    got = {o.id: o for o in fresh.objects}
    for obj in cat.objects:
        assert got[obj.id].to_json() == obj.to_json(), obj.id
    assert got[rejected].role == "NONE"
    assert len(fresh.objects) == len(cat.objects)  # detection did not add duplicates
    assert [t.to_json() for t in fresh.tilesets] == [t.to_json() for t in cat.tilesets]


def test_tileset_definitions_survive_without_source_ids(tmp_path: Path) -> None:
    cat, inv, _ = _assemble("basic16")
    cat.tilesets[0].navigation = True
    cat.tilesets[0].physics_layers[0]["name"] = "solid"
    sheet = next(s["asset"] for s in cat.tilesets[0].sources)
    cat = edits.confirm(cat, [sheet])
    data = profiles.export_profile(cat, "basic16", inv, META)
    assert all(set(s) == {"asset"} for s in data["tilesets"][0]["sources"])
    path = tmp_path / "t.rpgprofile.json"
    profiles.write_profile(data, path)
    profiles.install_profile(path)
    fresh, _inv, _issues = _assemble("basic16")
    assert fresh.tilesets[0].navigation is True
    assert fresh.tilesets[0].physics_layers[0]["name"] == "solid"
