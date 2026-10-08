"""Opt-in update check (T11.06).

Runs only when the user chooses Help > Check for updates. It reads the latest GitHub release of
the project and compares version numbers; it never downloads or installs anything.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

import rpggen
from rpggen.core import profile_registry

API_URL = (
    "https://api.github.com/repos/" + rpggen.REPO_URL.split("github.com/")[1] + "/releases/latest"
)
TIMEOUT_S = 10
LIMIT = 256 * 1024

Fetcher = Callable[[str, int], bytes]
_VERSION = re.compile(r"^v?(\d+(?:\.\d+){0,3})$")


@dataclass(frozen=True)
class Release:
    tag: str
    url: str
    version: tuple[int, ...]


def parse_version(text: str) -> tuple[int, ...] | None:
    """``v1.2.3`` or ``1.2`` as a tuple of ints; None for pre-releases and anything else."""
    match = _VERSION.match(text.strip())
    if not match:
        return None
    return tuple(int(p) for p in match.group(1).split("."))


def is_newer(tag: str, current: str) -> bool:
    """True when ``tag`` is a newer final release than ``current``; pre-releases never are."""
    latest, mine = parse_version(tag), parse_version(current)
    if latest is None or mine is None:
        return False
    width = max(len(latest), len(mine))
    pad = lambda v: v + (0,) * (width - len(v))  # noqa: E731
    return pad(latest) > pad(mine)


def _fetch(url: str, limit: int) -> bytes:
    return profile_registry.default_fetcher(url, limit, timeout=TIMEOUT_S)


def latest_release(fetcher: Fetcher | None = None) -> Release | None:
    """The newest final release, or None when there is none or the answer is unusable.

    Raises ``profile_registry.RegistryError`` when the network request fails."""
    data = (fetcher or _fetch)(API_URL, LIMIT)
    try:
        body = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(body, dict) or body.get("prerelease") or body.get("draft"):
        return None
    tag, url = body.get("tag_name"), body.get("html_url")
    if not isinstance(tag, str) or not isinstance(url, str):
        return None
    version = parse_version(tag)
    if version is None or not url.lower().startswith("https://"):
        return None
    return Release(tag, url, version)
