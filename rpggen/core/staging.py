from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rpggen import jsonio, paths, schema
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import ledger as ledger_mod
from rpggen.core import runtime_version
from rpggen.core.inventory import Inventory
from rpggen.errors import Issue, IssueList, RpgGenError

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


BACKUPS_NAME = ".rpggen_backups"
# Top-level target entries the regeneration copy leaves out: our own working folders, the user's
# git history and the export output.
COPY_SKIP_TOP = {".git", "export"}
COPY_SKIP_REL = {"rpggen/logs", "rpggen/results"}


@dataclass
class Staging:
    target: Path
    staging: Path  # target / ".rpggen_staging"
    mode: str = "new"  # "new" | "regenerate"

    @property
    def regenerate(self) -> bool:
        return self.mode == "regenerate"


def _copy_ignore(root: Path):  # type: ignore[no-untyped-def]
    def ignore(folder: str, names: list[str]) -> set[str]:
        rel = Path(folder).relative_to(root).as_posix()
        skipped: set[str] = set()
        for name in names:
            child = name if rel == "." else f"{rel}/{name}"
            top_skip = rel == "." and (name.startswith(".rpggen_") or name in COPY_SKIP_TOP)
            if top_skip or child in COPY_SKIP_REL:
                skipped.add(name)
        return skipped

    return ignore


def _make_copy_function(staging: Path):  # type: ignore[no-untyped-def]
    """``copy2`` that hard-links binary pack files (they are replaced, never edited in place)."""
    packs = staging / "assets" / "packs"

    def copy(src: str, dst: str) -> str:
        d = Path(dst)
        if packs in d.parents and d.suffix.lower() not in ledger_mod.TEXT_EXTS:
            try:
                os.link(src, dst)
                return dst
            except OSError:
                pass  # another volume or a file system without hard links: copy
        return shutil.copy2(src, dst)

    return copy


def create_staging(target: Path) -> Staging:
    """Make a fresh staging folder inside ``target``.

    * Missing or empty target: mode ``new`` (an empty staging folder).
    * Target with ``rpggen/generator_config.json``: mode ``regenerate`` (staging is a copy of the
      project, including ``.godot/``).
    * Anything else: ENV-009.
    """
    target = Path(target)
    regenerate = False
    if target.exists():
        leftovers = [p for p in target.iterdir() if p.name not in (STAGING_NAME, FAILED_NAME)]
        if leftovers:
            if not (target / paths.CONFIG).is_file():
                raise RpgGenError("ENV-009", path=str(target))
            regenerate = True
    else:
        try:
            target.mkdir(parents=True)
        except OSError as exc:
            raise RpgGenError("ENV-004", path=str(target)) from exc
    staging = target / STAGING_NAME
    if staging.exists():
        shutil.rmtree(staging)
    try:
        if regenerate:
            shutil.copytree(
                target,
                staging,
                ignore=_copy_ignore(target),
                copy_function=_make_copy_function(staging),
                dirs_exist_ok=False,
            )
        else:
            staging.mkdir()
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise RpgGenError("ENV-004", path=str(target)) from exc
    return Staging(target, staging, "regenerate" if regenerate else "new")


def _is_junk(rel_parts: tuple[str, ...]) -> bool:
    return rel_parts[-1].lower() in JUNK_NAMES or any(p.lower() in JUNK_DIRS for p in rel_parts)


def _place(src: Path, dst: Path) -> bool:
    """Copy ``src`` to ``dst`` unless ``dst`` already has the same content (ledger hash).

    A changed file is replaced, never written in place: the old one may be a hard link to a file
    of the target project.
    """
    if dst.is_file():
        if ledger_mod.file_hash(dst) == ledger_mod.file_hash(src):
            return False
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _copy_tree(src: Path, dst: Path, root: Path) -> list[str]:
    written: list[str] = []
    for p in sorted(src.rglob("*"), key=lambda q: q.relative_to(src).as_posix().casefold()):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        out = dst / p.relative_to(src)
        _place(p, out)
        written.append(paths.to_posix_rel(out, root))
    return written


def install_templates(stg: Staging, templates_root: Path) -> list[str]:
    """Copy the runtime addon and the builder into staging. Tests and probes are not copied.

    Files whose content is unchanged are left alone (they keep their modification time).
    """
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


def install_pack(
    stg: Staging, pack_dir: Path, pack_id: str, inv: Inventory | None = None
) -> list[str]:
    """Copy the pack's files to ``assets/packs/<pack_id>/``, bytes preserved.

    With an inventory only its files are copied (junk is already excluded there); without one
    every non-junk file is. Returns every pack file now in staging for this pack.
    """
    pack_dir = Path(pack_dir)
    dst = stg.staging / "assets" / "packs" / pack_id
    if inv is not None:
        sources = [pack_dir / f.path for f in inv.files]
    else:
        sources = [
            p
            for p in sorted(
                pack_dir.rglob("*"), key=lambda q: q.relative_to(pack_dir).as_posix().casefold()
            )
            if p.is_file() and not _is_junk(p.relative_to(pack_dir).parts)
        ]
    written: list[str] = []
    for p in sources:
        out = dst / p.relative_to(pack_dir)
        _place(p, out)
        written.append(paths.to_posix_rel(out, stg.staging))
    return sorted(written, key=lambda s: (s.casefold(), s))


def prune_packs(stg: Staging, old: ledger_mod.Ledger, keep: set[str]) -> list[Issue]:
    """Regeneration: drop pack files that no pack inventory lists any more.

    A file goes only when the ledger says the generator wrote it and the target copy is
    untouched; otherwise it stays and REGEN-003 is reported. Files the ledger does not know
    (added by the user) are left alone without a message. Godot's ``.import`` / ``.uid``
    sidecars go with their file.
    """
    issues = IssueList()
    packs = stg.staging / "assets" / "packs"
    if not stg.regenerate or not packs.is_dir():
        return list(issues)
    sidecars = (".import", ".uid")
    for p in sorted(packs.rglob("*")):
        if not p.is_file():
            continue
        rel = paths.to_posix_rel(p, stg.staging)
        if rel in keep or p.suffix in sidecars and rel.rsplit(".", 1)[0] in keep:
            continue
        entry = old.files.get(rel)
        if entry is None:
            continue
        state = ledger_mod.classify(stg.target, rel, old)
        if entry.owner == "generated" and state is ledger_mod.FileState.UNTOUCHED:
            p.unlink()
        elif state in (ledger_mod.FileState.MODIFIED, ledger_mod.FileState.UNTOUCHED):
            issues.add(
                "REGEN-003",
                f"File {rel} is no longer in the pack but was kept because it was changed.",
                file=rel,
            )
    return list(issues)


def install_generated(stg: Staging, generated: dict[str, str]) -> list[str]:
    """Copy adapter-generated files (GIF strips) to their project-relative targets."""
    written: list[str] = []
    for rel in sorted(generated):
        target = paths.from_posix_rel(rel, stg.staging)
        _place(Path(generated[rel]), target)
        written.append(rel)
    return written


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


README_TEMPLATE = "README.template.md"


def render_readme(template: str, cfg: config_mod.GeneratorConfig, runtime: str) -> str:
    """Fill the README template (``str.format`` placeholders; values are never re-interpreted,
    so braces in a project name are safe)."""
    packs = "\n".join(f"- {p.pack_id}" for p in cfg.packs) or "- (none)"
    return template.format(
        project_name=cfg.project_name,
        archetype=cfg.archetype,
        runtime_version=runtime,
        godot_version=cfg.godot_version,
        packs_list=packs,
    )


def write_project_files(
    stg: Staging, cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog
) -> None:
    """Write project.godot, generator_config.json, asset_catalog.json, the VCS files and README.md.

    When regenerating, project.godot is the user's own (the builder applies the keys it owns on
    top of it) and the VCS files are only rewritten if the template text changed.
    """
    root = stg.staging
    if not stg.regenerate or not (root / "project.godot").is_file():
        _write_text(root / "project.godot", minimal_project_godot(cfg.project_name))
    cfg_data = cfg.to_json()
    schema.validate("config", cfg_data)
    jsonio.write(root / paths.CONFIG, cfg_data)
    cat_data = catalog.to_json()
    schema.validate("catalog", cat_data)
    jsonio.write(root / paths.CATALOG, cat_data)
    files = paths.templates_root() / "project_files"
    for name, template in (
        (".gitignore", "gitignore.txt"),
        (".gitattributes", "gitattributes.txt"),
    ):
        text = (files / template).read_text(encoding="utf-8")
        dst = root / name
        if not dst.is_file() or dst.read_bytes().replace(b"\r\n", b"\n") != text.encode("utf-8"):
            _write_text(dst, text)
    readme = render_readme(
        (files / README_TEMPLATE).read_text(encoding="utf-8"),
        cfg,
        runtime_version.read_version(paths.templates_root()) or "unknown",
    )
    dst = root / "README.md"
    if not dst.is_file() or dst.read_bytes().replace(b"\r\n", b"\n") != readme.encode("utf-8"):
        _write_text(dst, readme)


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
