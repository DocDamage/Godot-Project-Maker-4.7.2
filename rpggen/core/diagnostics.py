"""Diagnostic bundles (T10.01): a zip a user can attach to a bug report.

The bundle holds configuration, catalog, ledger, build state, results and redacted logs of a
project (or of a failed generation folder), plus a manifest of the asset files. It never holds
image or audio bytes, so a bundle is safe to share even for a commercial pack.
"""

from __future__ import annotations

import json
import locale
import logging
import platform
import re
import zipfile
from pathlib import Path
from typing import Any

from rpggen import __version__, jsonio, paths

log = logging.getLogger(__name__)

LOG_TAIL_BYTES = 5 * 1024 * 1024
HOME_TOKEN = "<home>"
USER_TOKEN = "<user>"
README_TEXT = """rpggen diagnostic bundle
========================

This zip helps the rpggen maintainers understand a problem. It contains:

  system.json            operating system, Python, rpggen and Godot versions, locale
  config.json            the generator configuration of the project
  asset_catalog.json     what rpggen detected and what you changed in the audit
  ownership_ledger.json  which files rpggen owns
  build_state.json       state of the last build
  results/               build, validation and smoke test results
  logs/                  log files (your user name and home folder are replaced by
                         <user> and <home>; each log is cut to its last 5 MB)
  assets_manifest.json   for every asset: id, path, sha256, width, height and byte size

NO ART IS INCLUDED. There are no images and no audio files in this bundle, only their names,
sizes and hashes. Please look through the files before you send them if you are unsure.
"""
# Files copied as they are, relative to the project's rpggen/ folder -> name in the bundle.
_COPIED = {
    "generator_config.json": "config.json",
    "asset_catalog.json": "asset_catalog.json",
    "ownership_ledger.json": "ownership_ledger.json",
    "build_state.json": "build_state.json",
}
FORBIDDEN_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tga", ".ico",
    ".wav", ".ogg", ".mp3", ".flac", ".mid", ".midi", ".opus", ".m4a",
}  # fmt: skip


def meta_root(folder: Path) -> Path:
    """The folder that holds the ``rpggen/`` metadata: a project, or a failed run (which is a
    moved staging folder and so has the same layout)."""
    folder = Path(folder)
    inner = folder / "rpggen"
    return inner if inner.is_dir() else folder


def _user_name() -> str:
    try:
        return Path.home().name
    except (RuntimeError, OSError):
        return ""


def redactor(home: Path | None = None, user: str | None = None):  # type: ignore[no-untyped-def]
    """A function that replaces the home folder (both slash styles) and then the user name."""
    home = Path.home() if home is None else Path(home)
    user = _user_name() if user is None else user
    pairs: list[tuple[re.Pattern[str], str]] = []
    home_text = str(home)
    if home_text and home_text not in ("/", "\\", "."):
        for variant in {
            home_text,
            home_text.replace("\\", "/"),
            home_text.replace("/", "\\"),
            home_text.replace("/", "\\").replace("\\", "\\\\"),  # inside JSON strings
        }:
            pairs.append((re.compile(re.escape(variant), re.IGNORECASE), HOME_TOKEN))
    if len(user) >= 2:  # a one-letter name would mangle every log line
        pairs.append(
            (
                re.compile(rf"(?<![A-Za-z0-9]){re.escape(user)}(?![A-Za-z0-9])", re.IGNORECASE),
                USER_TOKEN,
            )
        )

    def redact(text: str) -> str:
        for pattern, token in pairs:
            text = pattern.sub(token, text)
        return text

    return redact


def redact_log(path: Path, redact) -> str:  # type: ignore[no-untyped-def]
    """The last 5 MB of a log file, redacted. A cut starts at a line boundary."""
    size = path.stat().st_size
    with open(path, "rb") as fh:
        if size > LOG_TAIL_BYTES:
            fh.seek(size - LOG_TAIL_BYTES)
            raw = fh.read()
            newline = raw.find(b"\n")
            raw = raw[newline + 1 :] if newline >= 0 else raw
        else:
            raw = fh.read()
    return redact(raw.decode("utf-8", errors="replace"))


def system_info(godot_exe: Path | None, redact) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    from rpggen.core import godot

    godot_version = ""
    godot_path = ""
    if godot_exe is not None:
        godot_path = redact(str(godot_exe))
        try:
            v = godot.detect_version(Path(godot_exe))
            godot_version = f"{v[0]}.{v[1]}.{v[2]}.{v[3]}"
        except Exception as exc:  # a broken Godot is itself useful to know about
            godot_version = f"unknown ({type(exc).__name__})"
    lang = locale.getlocale()[0] or ""
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "rpggen": __version__,
        "godot_version": godot_version,
        "godot_path": godot_path,
        "locale": lang,
    }


def assets_manifest(catalog_path: Path, project_root: Path | None) -> list[dict[str, Any]]:
    """``{id, path, sha256, w, h, size}`` for every catalog asset; no image bytes."""
    if not catalog_path.is_file():
        return []
    data = jsonio.read(catalog_path)
    out: list[dict[str, Any]] = []
    for asset in data.get("assets", []):
        facets = {**asset.get("detected", {}), **asset.get("overrides", {})}
        size = facets.get("size") or [None, None]
        file_size = None
        if project_root is not None:
            try:
                file_size = (paths.from_posix_rel(asset["path"], project_root)).stat().st_size
            except (ValueError, OSError):
                file_size = None
        out.append(
            {
                "id": asset["id"],
                "path": asset["path"],
                "sha256": asset.get("sha256", ""),
                "w": size[0],
                "h": size[1],
                "size": file_size,
            }
        )
    return sorted(out, key=lambda a: a["id"])


def _dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def make_bundle(
    target_or_failed_dir: Path,
    out_zip: Path,
    godot_exe: Path | None = None,
    extra_logs: list[Path] | None = None,
    *,
    home: Path | None = None,
    user: str | None = None,
) -> Path:
    """Write the diagnostic bundle for a project or a failed-generation folder to ``out_zip``.

    ``extra_logs`` are additional log files (for example the application log). ``home`` and
    ``user`` exist for tests; they default to the current user's.
    """
    folder = Path(target_or_failed_dir)
    meta = meta_root(folder)
    redact = redactor(home, user)
    out_zip = Path(out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:

        def add_text(name: str, text: str) -> None:
            zf.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), text.encode("utf-8"))

        add_text("README.txt", README_TEXT)
        add_text("system.json", _dumps(system_info(godot_exe, redact)))
        for source, name in _COPIED.items():
            src = meta / source
            if src.is_file():
                add_text(name, redact(src.read_text(encoding="utf-8", errors="replace")))
        report = folder / "generation_report.json"
        if not report.is_file():
            report = meta / "generation_report.json"
        if report.is_file():
            add_text("generation_report.json", redact(report.read_text(encoding="utf-8")))
        results = meta / "results"
        if results.is_dir():
            for path in sorted(results.glob("*.json")):
                add_text(f"results/{path.name}", redact(path.read_text(encoding="utf-8")))
        logs = list((meta / "logs").glob("*.log")) if (meta / "logs").is_dir() else []
        for path in sorted(logs) + [Path(p) for p in (extra_logs or []) if Path(p).is_file()]:
            add_text(f"logs/{path.name}", redact_log(path, redact))
        from rpggen.core import app_settings

        saved = app_settings.settings_path()
        if saved.is_file():
            add_text("settings.json", redact(saved.read_text(encoding="utf-8", errors="replace")))
        manifest = assets_manifest(meta / "asset_catalog.json", folder)
        add_text("assets_manifest.json", _dumps(manifest))
    return out_zip


def default_bundle_name(folder: Path) -> str:
    return f"rpggen-diagnostics-{Path(folder).name or 'project'}.zip"
