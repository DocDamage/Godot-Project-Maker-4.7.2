"""Community profile registry client (T10.04).

The registry is the ``registry/`` folder of the project repository, with ``index.json`` and
``profiles/<id>.rpgprofile.json``. This module talks to it only when the user asks (the "Find
profile online" button). Everything it downloads is data: it is parsed as JSON, validated against
the profile schema and must carry the CC0-1.0 license. Nothing from a profile is ever executed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen import REPO_URL, schema
from rpggen.core import profiles
from rpggen.core.inventory import Inventory
from rpggen.errors import RpgGenError

log = logging.getLogger(__name__)

REGISTRY_BASE = (
    REPO_URL.replace("https://github.com/", "https://raw.githubusercontent.com/")
    + "/main/registry/"
)
BASE_ENV = "RPGGEN_REGISTRY_BASE"
INDEX_NAME = "index.json"
REQUIRED_LICENSE = "CC0-1.0"
MIN_OVERLAP = 0.5
INDEX_LIMIT = 4 * 1024 * 1024
PROFILE_LIMIT = 8 * 1024 * 1024
TIMEOUT_S = 15
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_]{0,99}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")

Fetcher = Callable[[str, int], bytes]


def registry_base() -> str:
    """The registry base URL: ``RPGGEN_REGISTRY_BASE`` (https only) or the project repository."""
    override = os.environ.get(BASE_ENV, "").strip()
    if not override:
        return REGISTRY_BASE
    if not override.lower().startswith("https://"):
        raise RegistryError(f"{BASE_ENV} must be an https URL")
    return override if override.endswith("/") else override + "/"


class RegistryError(Exception):
    """The registry could not be reached or returned something unusable."""


class RegistryOffline(RegistryError):
    """The network request itself failed (no connection, timeout, DNS)."""


@dataclass(frozen=True)
class Candidate:
    profile_id: str
    title: str
    author: str
    license: str
    overlap: float  # fraction of the entry's fingerprint hashes found in the local packs


def default_fetcher(url: str, limit: int) -> bytes:
    """GET ``url`` (https only) and return at most ``limit`` bytes; more is an error."""
    if not url.lower().startswith("https://"):
        raise RegistryError(f"refusing a non-https URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "rpggen"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
            data: bytes = response.read(limit + 1)
    except OSError as exc:
        raise RegistryOffline(str(exc)) from exc
    if len(data) > limit:
        raise RegistryError("the response is too large")
    return data


def _json(data: bytes, what: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RegistryError(f"{what} is not valid JSON") from exc


def parse_index(data: Any) -> list[dict[str, Any]]:
    """Keep the well-formed entries of an index; malformed ones are dropped, not fatal."""
    if not isinstance(data, list):
        raise RegistryError("index.json must be a list")
    out: list[dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("profile_id")
        hashes = entry.get("fingerprint_hashes")
        if not isinstance(pid, str) or not _SAFE_ID.match(pid):
            continue
        if not isinstance(hashes, list) or not hashes:
            continue
        if not all(isinstance(h, str) and _SHA.match(h) for h in hashes):
            continue
        out.append(
            {
                "profile_id": pid,
                "title": str(entry.get("title", pid)),
                "fingerprint_hashes": hashes,
                "author": str(entry.get("author", "")),
                "license": str(entry.get("license", "")),
            }
        )
    return out


def fetch_index(
    fetcher: Fetcher = default_fetcher, base: str | None = None
) -> list[dict[str, Any]]:
    base = base or registry_base()
    return parse_index(_json(fetcher(base + INDEX_NAME, INDEX_LIMIT), "index.json"))


def candidates(index: list[dict[str, Any]], inventories: list[Inventory]) -> list[Candidate]:
    """Entries whose fingerprint has at least 50% overlap with the local files' hashes,
    best match first (ties by title)."""
    local = {f.sha256 for inv in inventories for f in inv.files}
    found: list[Candidate] = []
    for entry in index:
        hashes = entry["fingerprint_hashes"]
        overlap = sum(1 for h in hashes if h in local) / len(hashes)
        if overlap >= MIN_OVERLAP:
            found.append(
                Candidate(
                    entry["profile_id"], entry["title"], entry["author"], entry["license"], overlap
                )
            )
    found.sort(key=lambda c: (-c.overlap, c.title.lower(), c.profile_id))
    return found


def download_profile(
    profile_id: str, fetcher: Fetcher = default_fetcher, base: str | None = None
) -> dict[str, Any]:
    """Download, validate and install one profile; returns it. Anything that does not validate
    (schema, id, license) is rejected and nothing is installed."""
    if not _SAFE_ID.match(profile_id):
        raise RegistryError(f"not a valid profile id: {profile_id!r}")
    base = base or registry_base()
    url = f"{base}profiles/{profile_id}{profiles.PROFILE_SUFFIX}"
    data = _json(fetcher(url, PROFILE_LIMIT), "the profile")
    try:
        schema.validate("profile", data)
    except RpgGenError as exc:
        raise RegistryError(f"the profile does not validate: {exc}") from exc
    if data.get("profile_id") != profile_id:
        raise RegistryError("the profile's id does not match its file name")
    if data.get("license") != REQUIRED_LICENSE:
        raise RegistryError(f"profiles must be licensed {REQUIRED_LICENSE}")
    with tempfile.TemporaryDirectory(prefix="rpggen_profile_") as tmp:
        path = Path(tmp) / f"{profile_id}{profiles.PROFILE_SUFFIX}"
        profiles.write_profile(data, path)
        return profiles.install_profile(path)
