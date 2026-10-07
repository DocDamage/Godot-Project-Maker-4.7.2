"""Runtime versioning (T6.17): the version of ``addons/rpg_runtime`` and its changelog.

``VERSION`` holds one semantic version. ``CHANGELOG.md`` has ``## <semver>`` headings followed by
bullet lines. A regeneration that moves the target to a new major version needs confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

RUNTIME_DIR = "addons/rpg_runtime"
VERSION_FILE = "VERSION"
CHANGELOG_FILE = "CHANGELOG.md"

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_HEADING = re.compile(r"^##\s+(\S+)\s*$")

Version = tuple[int, int, int]


def parse_version(text: str) -> Version:
    """``"1.2.3"`` -> ``(1, 2, 3)``. Raises ValueError for anything else."""
    m = _SEMVER.match(text.strip())
    if not m:
        raise ValueError(f"not a semantic version: {text.strip()!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def format_version(v: Version) -> str:
    return f"{v[0]}.{v[1]}.{v[2]}"


def compare(a: str, b: str) -> int:
    """-1, 0 or 1 as version ``a`` is lower than, equal to or higher than ``b``."""
    va, vb = parse_version(a), parse_version(b)
    return (va > vb) - (va < vb)


def major(text: str) -> int:
    return parse_version(text)[0]


def runtime_folder(project_or_templates: Path) -> Path:
    return Path(project_or_templates) / RUNTIME_DIR


def read_version(root: Path) -> str | None:
    """The runtime version below ``root`` (a templates root or a project), or None when the
    file is missing or malformed."""
    path = runtime_folder(root) / VERSION_FILE
    try:
        text = path.read_text(encoding="utf-8").strip()
        parse_version(text)
    except (OSError, ValueError):
        return None
    return text


def parse_changelog(text: str) -> dict[str, list[str]]:
    """Version -> bullet lines (without the bullet marker). Headings that are not versions are
    ignored; a version listed twice keeps its first entry."""
    entries: dict[str, list[str]] = {}
    current: list[str] | None = None
    for raw in text.splitlines():
        m = _HEADING.match(raw)
        if m:
            try:
                parse_version(m.group(1))
            except ValueError:
                current = None
                continue
            if m.group(1) in entries:
                current = None
            else:
                current = entries[m.group(1)] = []
            continue
        line = raw.strip()
        if current is not None and line[:1] in ("*", "-") and line[1:2] == " ":
            current.append(line[2:].strip())
        elif current is not None and line and raw[:1] in (" ", "\t") and current:
            current[-1] += " " + line  # wrapped bullet
    return entries


def read_changelog(root: Path) -> dict[str, list[str]]:
    try:
        text = (runtime_folder(root) / CHANGELOG_FILE).read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_changelog(text)


def changelog_between(
    old: str | None, new: str, changelog: dict[str, list[str]]
) -> list[tuple[str, list[str]]]:
    """Entries with ``old < version <= new``, newest first. ``old`` None means every entry up to
    ``new``."""
    out: list[tuple[str, list[str]]] = []
    for version, bullets in changelog.items():
        if old is not None and compare(version, old) <= 0:
            continue
        if compare(version, new) > 0:
            continue
        out.append((version, bullets))
    out.sort(key=lambda e: parse_version(e[0]), reverse=True)
    return out


def changelog_text(entries: list[tuple[str, list[str]]]) -> str:
    lines: list[str] = []
    for version, bullets in entries:
        lines.append(f"Version {version}")
        lines += [f"  - {b}" for b in bullets] or ["  - (no notes)"]
    return "\n".join(lines)


@dataclass
class UpgradeInfo:
    old: str | None  # version installed in the target (None: first generation or unknown)
    new: str  # version in the templates
    changelog: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def is_upgrade(self) -> bool:
        return self.old is not None and compare(self.new, self.old) > 0

    @property
    def is_downgrade(self) -> bool:
        return self.old is not None and compare(self.new, self.old) < 0

    @property
    def major_increase(self) -> bool:
        return self.old is not None and major(self.new) > major(self.old)

    @property
    def needs_confirmation(self) -> bool:
        return self.major_increase

    @property
    def changelog_text(self) -> str:
        return changelog_text(self.changelog)


def check_upgrade(templates_root: Path, target: Path | None) -> UpgradeInfo:
    """Compare the templates' runtime with the one installed in ``target`` (None or a folder
    without a runtime: nothing to upgrade)."""
    new = read_version(templates_root) or "0.0.0"
    old = read_version(target) if target is not None else None
    changelog = read_changelog(templates_root)
    return UpgradeInfo(old, new, changelog_between(old, new, changelog))
