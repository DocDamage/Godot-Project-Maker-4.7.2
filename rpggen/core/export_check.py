"""Windows export preset and the optional export check (T10.05).

``export_presets.cfg`` is the one engine config file rpggen writes as text. It comes from the
verified template ``godot_templates/project_files/export_presets.template.cfg``. The check runs
``godot --headless --export-release`` on the staged project when the export templates for the
running Godot version are installed, and is skipped with ENV-010 otherwise.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

from rpggen import ids, paths
from rpggen.core import godot
from rpggen.errors import Issue, IssueList

log = logging.getLogger(__name__)

PRESET_NAME = "Windows Desktop"
PRESETS_FILE = "export_presets.cfg"
TEMPLATE_FILE = "export_presets.template.cfg"
EXPORT_TIMEOUT_S = 600


def export_path(project_name: str) -> str:
    return f"export/windows/{ids.slug(project_name)}.exe"


def _cfg_string(text: str) -> str:
    """Escape ``text`` for the inside of a double-quoted ConfigFile string."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render_presets(project_name: str, template: str | None = None) -> str:
    if template is None:
        template = (paths.templates_root() / "project_files" / TEMPLATE_FILE).read_text(
            encoding="utf-8"
        )
    return template.format(
        export_path=export_path(project_name), product_name=_cfg_string(project_name)
    )


def write_presets(project: Path, project_name: str) -> bool:
    """Write ``export_presets.cfg`` unless the project has one (the user's edits win)."""
    dst = Path(project) / PRESETS_FILE
    if dst.is_file():
        return False
    dst.write_text(render_presets(project_name), encoding="utf-8", newline="\n")
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


def templates_installed(version: tuple[int, int, int, str]) -> bool:
    folder = templates_base() / version_folder(version)
    return folder.is_dir() and any(folder.glob("windows_release_x86_64*"))


def run_check(
    exe: Path, project: Path, project_name: str, log_dir: Path
) -> tuple[list[Issue], bool]:
    """Export the project once and delete the result. Returns (issues, ran).

    Missing export templates give an ENV-010 info and ``ran=False``. A failed export is a
    BUILD-002 error (recipe ``export_check``).
    """
    issues = IssueList()
    version = godot.detect_version(exe)
    if not templates_installed(version):
        issues.add("ENV-010")
        return list(issues), False
    with tempfile.TemporaryDirectory(prefix="rpggen_export_") as tmp:
        out = Path(tmp) / "test.exe"
        run = godot.run_godot(
            exe,
            project,
            ["--export-release", PRESET_NAME, str(out)],
            timeout_s=EXPORT_TIMEOUT_S,
            log_name="export",
            log_dir=log_dir,
        )
        if run.timed_out:
            issues.add("BUILD-003", phase="export", seconds=EXPORT_TIMEOUT_S)
        elif run.returncode != 0:
            issues.add("BUILD-002", recipe="export_check", reason=f"exit code {run.returncode}")
        elif not out.is_file() or out.stat().st_size == 0:
            issues.add("BUILD-002", recipe="export_check", reason="the exported file is empty")
    return list(issues), True
