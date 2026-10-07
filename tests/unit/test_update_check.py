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
