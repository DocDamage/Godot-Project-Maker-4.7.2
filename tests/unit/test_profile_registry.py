from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from rpggen.core import archive, catalog, inventory, profile_registry, profiles

SYNTH = Path(__file__).resolve().parents[2] / "test_packs" / "synthetic"
BASE = "https://example.test/reg/"


@pytest.fixture(autouse=True)
def _cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPGGEN_CACHE_DIR", str(tmp_path / "cache"))


def _inventory():
    opened = archive.open_pack(SYNTH / "basic16", set())
    return opened, inventory.build_inventory(opened)


def _profile(license_: str = "CC0-1.0", profile_id: str = "basic_16") -> dict:
    opened, inv = _inventory()
    cat, _issues, _gen = catalog.assemble([(opened, inv)], None, [])
    data = profiles.export_profile(
        cat, inv.pack_id, inv, {"title": "Basic 16", "profile_id": profile_id, "license": license_}
    )
    return copy.deepcopy(data)


def _fetcher(files: dict[str, object]):
    calls: list[str] = []

    def fetch(url: str, limit: int) -> bytes:
        calls.append(url)
        if url not in files:
            raise profile_registry.RegistryError("404")
        value = files[url]
        return value if isinstance(value, bytes) else json.dumps(value).encode()

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def test_candidates_need_half_the_fingerprint_hashes() -> None:
    _opened, inv = _inventory()
    local = sorted({f.sha256 for f in inv.files})
    other = "f" * 64
    index = profile_registry.parse_index(
        [
            {"profile_id": "all", "title": "All", "fingerprint_hashes": local[:2]},
            {"profile_id": "half", "title": "Half", "fingerprint_hashes": [local[0], other]},
            {"profile_id": "less", "title": "Less", "fingerprint_hashes": [local[0], other, other]},
            {"profile_id": "bad id!", "title": "x", "fingerprint_hashes": local[:1]},
            {"profile_id": "nohash", "title": "x", "fingerprint_hashes": []},
            "junk",
        ]
    )
    found = profile_registry.candidates(index, [inv])
    assert [c.profile_id for c in found] == ["all", "half"]
    assert found[0].overlap == 1.0 and found[1].overlap == 0.5


def test_download_installs_a_valid_profile(tmp_path: Path) -> None:
    data = _profile()
    fetch = _fetcher({f"{BASE}profiles/basic_16.rpgprofile.json": data})
    installed = profile_registry.download_profile("basic_16", fetch, BASE)
    assert installed["profile_id"] == "basic_16"
    assert [p["profile_id"] for p in profiles.installed()] == ["basic_16"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(license="MIT"),
        lambda d: d.update(profile_id="other"),
        lambda d: d.pop("fingerprint"),
        lambda d: d.update(unexpected=1),
    ],
)
def test_invalid_profiles_are_rejected(mutate) -> None:
    data = _profile()
    mutate(data)
    fetch = _fetcher({f"{BASE}profiles/basic_16.rpgprofile.json": data})
    with pytest.raises(profile_registry.RegistryError):
        profile_registry.download_profile("basic_16", fetch, BASE)
    assert profiles.installed() == []


def test_garbage_and_unsafe_ids_are_rejected() -> None:
    fetch = _fetcher({f"{BASE}profiles/basic_16.rpgprofile.json": b"not json"})
    with pytest.raises(profile_registry.RegistryError):
        profile_registry.download_profile("basic_16", fetch, BASE)
    for bad in ("../evil", "a/b", "A", ""):
        with pytest.raises(profile_registry.RegistryError):
            profile_registry.download_profile(bad, fetch, BASE)
    assert fetch.calls == [f"{BASE}profiles/basic_16.rpgprofile.json"]  # type: ignore[attr-defined]


def test_fetch_index_and_the_default_fetcher_refuses_plain_http() -> None:
    fetch = _fetcher({f"{BASE}index.json": {"not": "a list"}})
    with pytest.raises(profile_registry.RegistryError):
        profile_registry.fetch_index(fetch, BASE)
    with pytest.raises(profile_registry.RegistryError):
        profile_registry.default_fetcher("http://example.test/index.json", 10)


def test_registry_base_is_the_repository_folder_and_can_be_overridden(monkeypatch) -> None:
    import pytest

    from rpggen import REPO_URL

    monkeypatch.delenv(profile_registry.BASE_ENV, raising=False)
    base = profile_registry.registry_base()
    assert base.startswith("https://raw.githubusercontent.com/")
    assert base.endswith("/main/registry/")
    assert REPO_URL.split("github.com/")[1] in base
    monkeypatch.setenv(profile_registry.BASE_ENV, "https://example.org/reg")
    assert profile_registry.registry_base() == "https://example.org/reg/"
    monkeypatch.setenv(profile_registry.BASE_ENV, "http://example.org/reg/")
    with pytest.raises(profile_registry.RegistryError):
        profile_registry.registry_base()


def test_network_failures_are_reported_as_offline(monkeypatch) -> None:
    import pytest

    def boom(*a, **k):
        raise OSError("no route")

    monkeypatch.setattr(profile_registry.urllib.request, "urlopen", boom)
    with pytest.raises(profile_registry.RegistryOffline):
        profile_registry.default_fetcher("https://example.org/x", 10)
