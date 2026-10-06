from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath

# Path constants for generated projects (POSIX, relative, without "res://").
# Keep in sync with godot_templates/builder/lib/paths.gd (checked by tests).
META_DIR = "rpggen/"
CATALOG = "rpggen/asset_catalog.json"
CONFIG = "rpggen/generator_config.json"
LEDGER = "rpggen/ownership_ledger.json"
BUILD_STATE = "rpggen/build_state.json"
RESULTS_BUILD = "rpggen/results/build_results.json"
RESULTS_VALIDATE = "rpggen/results/validation_results.json"
RESULTS_SMOKE = "rpggen/results/smoke_results.json"
PACKS_DIR = "assets/packs/"
GEN_DIR = "generated/"
TILESETS_DIR = "generated/tilesets/"
SPRITE_FRAMES_DIR = "generated/sprite_frames/"
GEN_SCENES_DIR = "generated/scenes/"
PLACEHOLDER_DIR = "generated/debug_placeholders/"
BUILDER_DIR = "generated/builder/"
GAME_DIR = "game/"
RUNTIME_ADDON = "addons/rpg_runtime/"
TOOLS_ADDON = "addons/rpg_project_tools/"


def to_posix_rel(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` as a POSIX string. ValueError if outside."""
    try:
        rel = Path(path).relative_to(Path(root))
    except ValueError as exc:
        raise ValueError(f"{path} is not inside {root}") from exc
    return rel.as_posix()


def from_posix_rel(rel: str, root: Path) -> Path:
    """Resolve a POSIX relative path under ``root``. Rejects absolute paths and ``..``."""
    if not rel or rel.startswith("/") or "\\" in rel or re.match(r"^[A-Za-z]:", rel):
        raise ValueError(f"not a safe relative path: {rel!r}")
    parts = PurePosixPath(rel).parts
    if ".." in parts:
        raise ValueError(f"'..' is not allowed in {rel!r}")
    return Path(root).joinpath(*parts)


@lru_cache(maxsize=256)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern.startswith("**", i):
                i += 2
                if pattern.startswith("/", i):
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("".join(out), re.IGNORECASE | re.DOTALL)


def glob_match(rel: str, pattern: str) -> bool:
    """Case-insensitive glob: ``*`` (no "/"), ``**`` (any depth, incl. zero), ``?``."""
    return _glob_regex(pattern).fullmatch(rel) is not None


def local_cache_dir() -> Path:
    """Per-user cache dir. The only place in the codebase that checks the platform."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "rpggen" / "cache"
    return Path.home() / ".cache" / "rpggen"
