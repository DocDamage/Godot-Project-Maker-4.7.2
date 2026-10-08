"""Export presets and the optional export check (T10.05, T12.52).

``export_presets.cfg`` is the one engine config file rpggen writes as text. Its presets come from
the verified template ``godot_templates/project_files/export_presets.template.cfg``, which holds
one section per target (Windows, Web, Linux, macOS) after a ``; target: <key>`` line. The
config's ``export_targets`` choose which presets are written. The check runs
``godot --headless --export-release`` once per selected target whose export templates for the
running Godot version are installed; a target without them is skipped with ENV-010.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from rpggen import ids, paths
from rpggen.core import godot
from rpggen.errors import Issue, IssueList

log = logging.getLogger(__name__)

PRESETS_FILE = "export_presets.cfg"
TEMPLATE_FILE = "export_presets.template.cfg"
EXPORT_TIMEOUT_S = 600


@dataclass(frozen=True, slots=True)
class Target:
    key: str  # the value in the config's ``export_targets``
    preset: str  # the preset name, which is what ``--export-release`` takes
    path: str  # export path inside the project; ``{slug}`` is the project slug
    template_glob: str  # the release template in the export templates folder
    test_file: str  # what the check exports to, inside a temporary folder


TARGETS: dict[str, Target] = {
    t.key: t
    for t in (
        Target(
            "windows",
            "Windows Desktop",
            "export/windows/{slug}.exe",
            "windows_release_x86_64*",
            "test.exe",
        ),
        # thread support is off in the preset (itch.io), so Godot uses the nothreads template
        Target(
            "web", "Web", "export/web/index.html", "web_nothreads_release.zip", "web/index.html"
        ),
        Target(
            "linux", "Linux", "export/linux/{slug}.x86_64", "linux_release.x86_64", "test.x86_64"
        ),
        Target("macos", "macOS", "export/macos/{slug}.zip", "macos.zip", "test.zip"),
    )
}
DEFAULT_TARGETS: tuple[str, ...] = ("windows",)
PRESET_NAME = TARGETS["windows"].preset

_TARGET_LINE = re.compile(r"^; target: (\w+)\n", re.MULTILINE)
_NAME_LINE = re.compile(r'^name="(.*)"$', re.MULTILINE)
_INDEX_LINE = re.compile(r"^\[preset\.(\d+)\]$", re.MULTILINE)


def ordered_targets(keys: Sequence[str]) -> list[str]:
    """The known targets among ``keys``, in the fixed order (unknown keys are dropped)."""
    chosen = set(keys)
    return [k for k in TARGETS if k in chosen]


def export_path(project_name: str, target: str = "windows") -> str:
    return TARGETS[target].path.format(slug=ids.slug(project_name))


def bundle_identifier(project_name: str) -> str:
    """``com.example.<name>`` for the macOS preset: letters, digits and hyphens, and the last
    part does not start with a digit."""
    part = ids.slug(project_name).replace("_", "-").strip("-") or "game"
    if part[0].isdigit():
        part = "game-" + part
    return f"com.example.{part}"


def _cfg_string(text: str) -> str:
    """Escape ``text`` for the inside of a double-quoted ConfigFile string."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _sections(template: str) -> dict[str, str]:
    """The template split at its ``; target:`` lines (the marker lines are dropped)."""
    marks = list(_TARGET_LINE.finditer(template))
    out: dict[str, str] = {}
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(template)
        out[mark.group(1)] = template[mark.end() : end].strip("\n") + "\n"
    return out


def _read_template() -> str:
    return (paths.templates_root() / "project_files" / TEMPLATE_FILE).read_text(encoding="utf-8")


def render_preset(project_name: str, target: str, index: int, template: str | None = None) -> str:
    """One preset (its ``[preset.N]`` and ``[preset.N.options]`` sections) as text."""
    section = _sections(template if template is not None else _read_template())[target]
    return section.format(
        index=index,
        export_path=export_path(project_name, target),
        product_name=_cfg_string(project_name),
        bundle_identifier=bundle_identifier(project_name),
    )


def render_presets(
    project_name: str,
    targets: Sequence[str] = DEFAULT_TARGETS,
    template: str | None = None,
) -> str:
    """``export_presets.cfg`` with one preset per target, in the fixed target order."""
    if template is None:
        template = _read_template()
    chosen = ordered_targets(targets) or list(DEFAULT_TARGETS)
    return "\n".join(render_preset(project_name, key, i, template) for i, key in enumerate(chosen))


def write_presets(
    project: Path, project_name: str, targets: Sequence[str] = DEFAULT_TARGETS
) -> bool:
    """Write ``export_presets.cfg``. An existing file is the user's: every line of it stays, and
    each selected target whose preset name it lacks is appended. True when the file changed."""
    dst = Path(project) / PRESETS_FILE
    if not dst.is_file():
        dst.write_text(render_presets(project_name, targets), encoding="utf-8", newline="\n")
        return True
    text = dst.read_text(encoding="utf-8")
    names = {m.group(1) for m in _NAME_LINE.finditer(text)}
    missing = [k for k in ordered_targets(targets) if TARGETS[k].preset not in names]
    if not missing:
        return False
    first = max((int(m.group(1)) for m in _INDEX_LINE.finditer(text)), default=-1) + 1
    template = _read_template()
    added = [render_preset(project_name, k, first + i, template) for i, k in enumerate(missing)]
    head = text.rstrip("\n") + "\n\n" if text.strip() else ""
    dst.write_text(head + "\n".join(added), encoding="utf-8", newline="\n")
    return True


def templates_base() -> Path:
    """Folder that holds one sub folder per installed export template version."""
    override = os.environ.get("RPGGEN_EXPORT_TEMPLATES_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Godot" / "export_templates"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Godot" / "export_templates"
    data = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data) / "godot" / "export_templates"


def version_folder(version: tuple[int, int, int, str]) -> str:
    """``4.7.2.stable`` for Godot 4.7.2."""
    major, minor, patch, status = version
    return f"{major}.{minor}.{patch}.{status or 'stable'}"


def templates_installed(version: tuple[int, int, int, str], target: str = "windows") -> bool:
    folder = templates_base() / version_folder(version)
    return folder.is_dir() and any(folder.glob(TARGETS[target].template_glob))


def run_check(
    exe: Path,
    project: Path,
    project_name: str,
    log_dir: Path,
    is_cancelled: Callable[[], bool] | None = None,
    targets: Sequence[str] = DEFAULT_TARGETS,
) -> tuple[list[Issue], list[str]]:
    """Export the project once per selected target and delete the results.

    Returns (issues, the targets that were exported). A target without export templates gives an
    ENV-010 info that names it. A failed export is a BUILD-002 error (recipe ``export_check``).
    """
    issues = IssueList()
    version = godot.detect_version(exe)
    ran: list[str] = []
    for key in ordered_targets(targets) or list(DEFAULT_TARGETS):
        target = TARGETS[key]
        if not templates_installed(version, key):
            issues.add("ENV-010", target=target.preset)
            continue
        if is_cancelled is not None and is_cancelled():
            break
        ran.append(key)
        with tempfile.TemporaryDirectory(prefix="rpggen_export_") as tmp:
            out = Path(tmp) / target.test_file
            out.parent.mkdir(parents=True, exist_ok=True)
            run = godot.run_godot(
                exe,
                project,
                ["--export-release", target.preset, str(out)],
                timeout_s=EXPORT_TIMEOUT_S,
                log_name="export" if key == "windows" else f"export_{key}",
                log_dir=log_dir,
                is_cancelled=is_cancelled,
            )
            if run.cancelled:
                break
            if run.timed_out:
                issues.add("BUILD-003", phase=f"export ({target.preset})", seconds=EXPORT_TIMEOUT_S)
            elif run.returncode != 0:
                issues.add(
                    "BUILD-002",
                    recipe="export_check",
                    reason=f"{target.preset}: exit code {run.returncode}",
                )
            elif not out.is_file() or out.stat().st_size == 0:
                issues.add(
                    "BUILD-002",
                    recipe="export_check",
                    reason=f"{target.preset}: the exported file is empty",
                )
    return list(issues), ran
