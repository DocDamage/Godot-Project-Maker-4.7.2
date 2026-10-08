from __future__ import annotations

import json

import pytest

from rpggen.core import profile_registry, update_check


@pytest.mark.parametrize(
    ("tag", "current", "newer"),
    [
        ("v1.0.1", "1.0.0", True),
        ("v1.0.0", "1.0.0", False),
        ("v0.9.9", "1.0.0", False),
        ("v1.1", "1.0.9", True),
        ("v2.0.0", "1.9.9", True),
        ("v1.0.0-rc1", "0.9.0", False),  # pre-releases are ignored
        ("nightly", "1.0.0", False),
        ("1.0.0.1", "1.0.0", True),
    ],
)
def test_version_comparison(tag: str, current: str, newer: bool) -> None:
    assert update_check.is_newer(tag, current) is newer


def _body(**over) -> bytes:
    data = {"tag_name": "v1.2.0", "html_url": "https://github.com/x/y/releases/tag/v1.2.0"}
    data.update(over)
    return json.dumps(data).encode()


def test_latest_release_outcomes() -> None:
    release = update_check.latest_release(lambda url, limit: _body())
    assert release and release.tag == "v1.2.0" and release.version == (1, 2, 0)
    assert update_check.latest_release(lambda u, n: _body(prerelease=True)) is None
    assert update_check.latest_release(lambda u, n: _body(html_url="http://evil")) is None
    assert update_check.latest_release(lambda u, n: b"not json") is None
    assert update_check.latest_release(lambda u, n: b"[]") is None

    def offline(url: str, limit: int) -> bytes:
        raise profile_registry.RegistryOffline("no route")

    with pytest.raises(profile_registry.RegistryError):
        update_check.latest_release(offline)


def test_the_request_goes_to_the_project_repository() -> None:
    seen: list[str] = []
    update_check.latest_release(lambda url, limit: seen.append(url) or _body())
    assert seen == [
        "https://api.github.com/repos/DocDamage/Godot-Project-Maker-4.7.2/releases/latest"
    ]


# ------------------------------------------------------------------------ no shared timeout (T12.13)


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, limit: int) -> bytes:
        return self._body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def test_each_caller_uses_its_own_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, float] = {}

    def urlopen(request, timeout):
        seen[request.full_url] = timeout
        return _Response(_body())

    monkeypatch.setattr(profile_registry.urllib.request, "urlopen", urlopen)
    update_check._fetch(update_check.API_URL, 1000)
    profile_registry.default_fetcher("https://example.org/index.json", 1000)
    assert seen[update_check.API_URL] == 10 == update_check.TIMEOUT_S
    assert seen["https://example.org/index.json"] == 15 == profile_registry.TIMEOUT_S
    assert profile_registry.TIMEOUT_S == 15  # the module's constant was never touched


def test_two_threads_at_once_each_see_their_own_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    both_inside = threading.Barrier(2, timeout=5)
    seen: dict[str, float] = {}

    def urlopen(request, timeout):
        both_inside.wait()  # the other request is in flight now: the old code swapped a global
        seen[request.full_url] = timeout
        return _Response(_body())

    monkeypatch.setattr(profile_registry.urllib.request, "urlopen", urlopen)
    threads = [
        threading.Thread(target=update_check._fetch, args=(update_check.API_URL, 1000)),
        threading.Thread(
            target=profile_registry.default_fetcher, args=("https://example.org/index.json", 1000)
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert seen == {update_check.API_URL: 10, "https://example.org/index.json": 15}


def test_no_module_assigns_a_constant_of_another_module() -> None:
    import re
    from pathlib import Path as P

    root = P(__file__).resolve().parents[2] / "rpggen"
    pattern = re.compile(r"^\s*[a-z_][a-z_0-9]*\.[A-Z][A-Z_0-9]* = ", re.M)
    found = [
        f"{path.relative_to(root)}: {match.group().strip()}"
        for path in root.rglob("*.py")
        for match in pattern.finditer(path.read_text(encoding="utf-8"))
    ]
    assert found == []
