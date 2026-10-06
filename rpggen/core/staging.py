from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rpggen import jsonio, paths, schema
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.errors import RpgGenError

log = logging.getLogger(__name__)

STAGING_NAME = ".rpggen_staging"
FAILED_NAME = ".rpggen_failed"
KEEP_FAILED = 3
JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}
JUNK_DIRS = {"__macosx"}

# Starter project.godot written before Godot first runs (same text as the template, T1.06).
# The builder's project_settings_recipe fills in everything else.
MINIMAL_PROJECT_GODOT = """; Engine configuration file.
; Template project for rpggen. Settings are applied by the builder.

config_version=5

[application]

config/name="{name}"
config/features=PackedStringArray("4.7")
"""


def minimal_project_godot(name: str) -> str:
    """MINIMAL_PROJECT_GODOT with ``config/name`` set (quotes and backslashes escaped)."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return MINIMAL_PROJECT_GODOT.replace("{name}", escaped)


@dataclass
class Staging:
    target: Path
    staging: Path  # target / ".rpggen_staging"


def create_staging(target: Path) -> Staging:
    """M1: ``target`` must be empty or not exist. Replaces any old staging with a fresh one."""
    target = Path(target)
    if target.exists():
        leftovers = [p for p in target.iterdir() if p.name not in (STAGING_NAME, FAILED_NAME)]
        if leftovers:
            raise RpgGenError("ENV-009", path=str(target))
    else:
        try:
            target.mkdir(parents=True)
        except OSError as exc:
            raise RpgGenError("ENV-004", path=str(target)) from exc
    staging = target / STAGING_NAME
    if staging.exists():
        shutil.rmtree(staging)
    try:
        staging.mkdir()
    except OSError as exc:
        raise RpgGenError("ENV-004", path=str(target)) from exc
    return Staging(target, staging)


def _is_junk(rel_parts: tuple[str, ...]) -> bool:
    return rel_parts[-1].lower() in JUNK_NAMES or any(p.lower() in JUNK_DIRS for p in rel_parts)


def _copy_tree(src: Path, dst: Path, root: Path) -> list[str]:
    written: list[str] = []
    for p in sorted(src.rglob("*"), key=lambda q: q.relative_to(src).as_posix().casefold()):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        out = dst / p.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out)
        written.append(paths.to_posix_rel(out, root))
    return written


def install_templates(stg: Staging, templates_root: Path) -> list[str]:
    """Copy the runtime addon and the builder into staging. Tests and probes are not copied."""
    templates_root = Path(templates_root)
    written: list[str] = []
    for src_rel, dst_rel in (
        ("addons/rpg_runtime", "addons/rpg_runtime"),
        ("builder", "generated/builder"),
    ):
        src = templates_root / src_rel
        if src.is_dir():
            written += _copy_tree(src, stg.staging / dst_rel, stg.staging)
    return sorted(written, key=lambda s: (s.casefold(), s))


def install_pack(stg: Staging, pack_dir: Path, pack_id: str) -> list[str]:
    """Copy every non-junk file of the pack to ``assets/packs/<pack_id>/``, bytes preserved."""
    pack_dir = Path(pack_dir)
    dst = stg.staging / "assets" / "packs" / pack_id
    written: list[str] = []
    for p in sorted(
        pack_dir.rglob("*"), key=lambda q: q.relative_to(pack_dir).as_posix().casefold()
    ):
        if not p.is_file() or _is_junk(p.relative_to(pack_dir).parts):
            continue
        out = dst / p.relative_to(pack_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out)
        written.append(paths.to_posix_rel(out, stg.staging))
    return sorted(written, key=lambda s: (s.casefold(), s))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_project_files(
    stg: Staging, cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog
) -> None:
    """Write project.godot, generator_config.json, asset_catalog.json and the VCS files."""
    root = stg.staging
    _write_text(root / "project.godot", minimal_project_godot(cfg.project_name))
    cfg_data = cfg.to_json()
    schema.validate("config", cfg_data)
    jsonio.write(root / paths.CONFIG, cfg_data)
    cat_data = catalog.to_json()
    schema.validate("catalog", cat_data)
    jsonio.write(root / paths.CATALOG, cat_data)
    files = paths.templates_root() / "project_files"
    _write_text(root / ".gitignore", (files / "gitignore.txt").read_text(encoding="utf-8"))
    _write_text(root / ".gitattributes", (files / "gitattributes.txt").read_text(encoding="utf-8"))


def promote(stg: Staging) -> None:
    """M1: move every top-level entry of staging into the (empty) target, then remove staging.

    M5 replaces this with ledger-aware promotion.
    """
    for entry in sorted(stg.staging.iterdir(), key=lambda p: p.name):
        dest = stg.target / entry.name
        if dest.exists():
            raise RpgGenError("REGEN-004", reason=f"{dest.name} already exists in the target")
        shutil.move(str(entry), str(dest))
    stg.staging.rmdir()


def discard(stg: Staging) -> Path:
    """Move staging to ``target/.rpggen_failed/<timestamp>/`` and keep the newest three."""
    failed_root = stg.target / FAILED_NAME
    failed_root.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = failed_root / stamp
    n = 1
    while dest.exists():
        n += 1
        dest = failed_root / f"{stamp}-{n}"
    shutil.move(str(stg.staging), str(dest))
    old = sorted((p for p in failed_root.iterdir() if p.is_dir()), key=lambda p: p.name)
    for p in old[:-KEEP_FAILED]:
        shutil.rmtree(p, ignore_errors=True)
    return dest
