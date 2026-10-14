from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rpggen import godot_target, jsonio, paths, schema
from rpggen.core import app_settings, export_check, runtime_version, vcs
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core import ledger as ledger_mod
from rpggen.core.archive import sha256_file
from rpggen.core.archive import walk_files as archive_walk_files
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
config/features=PackedStringArray("{godot_major_minor}")
"""


def minimal_project_godot(name: str) -> str:
    """MINIMAL_PROJECT_GODOT with ``config/name`` set (quotes and backslashes escaped)."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return MINIMAL_PROJECT_GODOT.replace("{godot_major_minor}", godot_target.MAJOR_MINOR).replace(
        "{name}", escaped
    )


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


def _place(src: Path, dst: Path, src_hash: str | None = None) -> bool:
    """Copy ``src`` to ``dst`` unless ``dst`` already has the same content.

    Only an existing ``dst`` is hashed. With ``src_hash`` (the inventory's sha256 of a pack
    file) ``src`` is not read at all and the comparison is byte for byte; without it both files
    are compared by their ledger hash (text files with normalized line endings).

    A changed file is replaced, never written in place: the old one may be a hard link to a file
    of the target project.
    """
    if dst.is_file():
        if src_hash is not None:
            if sha256_file(dst) == src_hash:
                return False
        elif ledger_mod.file_hash(dst) == ledger_mod.file_hash(src):
            return False
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


ARCHETYPES = ("turn_based", "arpg", "metroidvania", "shmup", "run_and_gun", "racing", "farm")
# A folder several kinds share, and the kinds it is installed for: the arcade framework (T16.01)
# belongs to the three arcade kinds, and the projects of the older kinds never see it.
SHARED_FOLDERS: dict[str, tuple[str, ...]] = {"arcade": ("shmup", "run_and_gun", "racing")}
# The folders of another kind a kind is built on: a run and gun's soldier is the metroidvania's
# platform actor on the metroidvania's side-view tiles (T16.08), so it gets that kind's runtime
# folder and recipes (not its smoke steps).
BORROWED_FOLDERS: dict[str, tuple[str, ...]] = {"run_and_gun": ("metroidvania",)}
# The folders a kind borrows only when a choice of the project asks for them (``borrowed`` of
# ``install_templates``): a farm that fights (T17.24) has the action RPG's enemies in its cave,
# so it gets that kind's runtime folder and recipes; a farm that does not fight gets neither.
OPTIONAL_FOLDERS: dict[str, tuple[str, ...]] = {"farm": ("arpg",)}


def _other_archetype(rel: str, archetype: str | None, borrowed: tuple[str, ...] = ()) -> bool:
    """True for a template file that belongs to an archetype other than the chosen one.

    The runtime keeps each archetype in ``addons/rpg_runtime/archetypes/<name>/``, its recipes in
    ``builder/recipes/<name>/`` and its smoke steps in ``builder/smoke/smoke_steps_<name>.gd``.
    A shared folder (``SHARED_FOLDERS``) is kept in the same places under its own name.
    ``borrowed`` are folders of other kinds the project asks for (``OPTIONAL_FOLDERS``).
    """
    if archetype is None:
        return False
    parts = rel.split("/")
    for other in (*ARCHETYPES, *SHARED_FOLDERS):
        if other == archetype or archetype in SHARED_FOLDERS.get(other, ()):
            continue
        lent = other in BORROWED_FOLDERS.get(archetype, ()) or other in borrowed
        if parts[:4] == ["addons", "rpg_runtime", "archetypes", other] and not lent:
            return True
        if parts[:3] == ["builder", "recipes", other] and not lent:
            return True
        if (
            len(parts) == 3
            and parts[:2] == ["builder", "smoke"]
            and parts[2] in (f"smoke_steps_{other}.gd", f"smoke_steps_{other}.gd.uid")
        ):
            return True
    return False


def install_templates(
    stg: Staging,
    templates_root: Path,
    archetype: str | None = None,
    editor_tools: bool = True,
    borrowed: tuple[str, ...] = (),
) -> list[str]:
    """Copy the runtime addon, the editor tools addon and the builder into staging. Tests and
    probes are not copied. ``editor_tools=False`` (feature off) leaves the tools addon out; the
    builder then does not enable the plugin and validation skips the content checks.

    With an ``archetype`` only that archetype's runtime folder, recipes and smoke steps are
    copied (the template project holds all of them so each is tested). Files whose content is
    unchanged are left alone (they keep their modification time). ``borrowed`` are the folders
    of other kinds the project asks for (``OPTIONAL_FOLDERS``: a farm that fights).
    """
    borrowed = tuple(b for b in borrowed if b in OPTIONAL_FOLDERS.get(archetype or "", ()))
    templates_root = Path(templates_root)
    written: list[str] = []
    for src_rel, dst_rel in (
        ("addons/rpg_runtime", "addons/rpg_runtime"),
        *((("addons/rpg_project_tools", "addons/rpg_project_tools"),) if editor_tools else ()),
        ("builder", "generated/builder"),
    ):
        src = templates_root / src_rel
        if not src.is_dir():
            continue
        for p in sorted(src.rglob("*"), key=lambda q: q.relative_to(src).as_posix().casefold()):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            rel_in_templates = p.relative_to(templates_root).as_posix()
            if _other_archetype(rel_in_templates, archetype, borrowed):
                continue
            out = stg.staging / dst_rel / p.relative_to(src)
            _place(p, out)
            written.append(paths.to_posix_rel(out, stg.staging))
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
        sources: list[tuple[Path, str | None]] = [(pack_dir / f.path, f.sha256) for f in inv.files]
    else:
        files, _links = archive_walk_files(pack_dir)  # links are skipped, never followed
        sources = [(pack_dir / rel, None) for rel in files if not _is_junk(tuple(rel.split("/")))]
    written: list[str] = []
    for p, digest in sources:
        out = dst / p.relative_to(pack_dir)
        _place(p, out, digest)
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


def effective_pack_art(cfg: config_mod.GeneratorConfig) -> tuple[str, list[Issue]]:
    """How the pack art is handled by git: ``commit``, ``lfs`` or ``ignore``. Git LFS without
    git-lfs falls back to ``commit`` and says so (ENV-013)."""
    choice = cfg.pack_art
    if choice == "lfs" and not vcs.lfs_available():
        found = IssueList()
        found.add("ENV-013")
        return "commit", list(found)
    return choice, []


def gitignore_text(base: str, pack_art: str) -> str:
    if pack_art != "ignore":
        return base
    return (
        base.rstrip("\n")
        + "\n# Purchased art stays out of the repository (Options > Version control)\n"
        + "assets/packs/\n"
    )


def gitattributes_text(base: str, pack_art: str) -> str:
    if pack_art != "lfs":
        return base
    lines = [
        f"assets/packs/**/*.{ext} filter=lfs diff=lfs merge=lfs -text" for ext in vcs.LFS_EXTENSIONS
    ]
    return (
        base.rstrip("\n")
        + "\n# The pack art goes through Git LFS (Options > Version control)\n"
        + ("\n".join(lines) + "\n")
    )


def version_control_note(pack_art: str) -> str:
    """The README section that explains what git does with the purchased art."""
    if pack_art == "ignore":
        body = (
            "The pack art in `assets/packs/` is **not** committed: it is listed in "
            "`.gitignore`, so most pack licences (which do not allow the art to be public) are "
            "respected when you push. Keep your own copy of the packs: a fresh clone has to get "
            "them back into "
            "`assets/packs/`. Options > Version control in rpggen changes this."
        )
    elif pack_art == "lfs":
        body = (
            "The pack art in `assets/packs/` goes through **Git LFS** (see `.gitattributes`): the "
            "repository holds small pointers and the art itself lives on the LFS server. Run "
            "`git lfs install` once on every computer that uses the repository. A public host "
            "still makes the art public, which most pack licences do not allow."
        )
    else:
        body = (
            "The pack art in `assets/packs/` is committed with the rest, so the repository is "
            "complete. **Most pack licences do not allow the art to be public: do not push this "
            "repository to a public host** unless every licence in `GENERATION_REPORT.md` allows "
            "it. To keep the art out of git, add `assets/packs/` to `.gitignore`, or choose "
            '"Leave the pack art out" under Options > Version control and generate again.'
        )
    return f"## 9.1 Version control\n\n{body}"


# The README's first paragraph after its first sentence: what the project is and what is in it.
# The two RPGs have the text the template always had (their README is byte for byte what it
# was); the other kinds were called "a **racing** RPG starter" with "a talking NPC, a chest" by
# it, and have their own.
RPG_OPENING = (
    "It is a **{archetype}** RPG starter: a small"
    "\nmap, a player you can walk around with, a talking NPC, a chest, a title screen, a pause"
    " menu and\nsaving and loading. Everything is yours to change."
)
KIND_OPENINGS = {
    "metroidvania": (
        "It is a **metroidvania** starter: a small world"
        "\nof rooms seen from the side, a player you can run and jump with, a talking NPC, a"
        " chest,\nenemies, a title screen, a pause menu and saving and loading. Everything is"
        " yours to change."
    ),
    "shmup": (
        "It is a **shoot 'em up** starter: a run of stages"
        "\nwith waves of enemies and a boss each, a ship you fly and shoot with, power-ups, lives"
        " and a\nscore, a title screen with the high scores and a pause menu. Everything is"
        " yours to change."
    ),
    "run_and_gun": (
        "It is a **run and gun** starter: a run of stages"
        "\nseen from the side with a boss each, a soldier who runs, jumps and aims, weapons to"
        " pick up,\nlives and a score, a title screen with high scores and a pause menu."
        " Everything is yours to change."
    ),
    "racing": (
        "It is a **racing game** starter: a championship"
        "\nof races, a car you drive against rivals, pickups on the road, a title screen with"
        " the high\nscores and a pause menu. Everything is yours to change."
    ),
    "farm": (
        "It is a **farm** game starter: a farm with a"
        "\nhouse and a field, crops to grow and sell, a village with a shop, days and seasons,"
        " a title\nscreen, a pause menu and saving and loading. Everything is yours to change."
    ),
}


def opening(archetype: str) -> str:
    """What the README's first paragraph says the project is and has in it."""
    return KIND_OPENINGS.get(archetype) or RPG_OPENING.format(archetype=archetype)


# What the README's first paragraph adds for a kind of game the shared sections were not
# written for. Empty for the top-down archetypes, so their README is what it was.
KIND_NOTES = {
    "shmup": (
        "\n\n**This game is a shoot 'em up**: a run through stages with lives and a score, not a"
        "\nvillage to walk. Where this file speaks of the starter map, doors, shops or quests, it"
        "\nspeaks of the other kinds of game; start with section 22: the controls, the stages,"
        "\ntheir waves and bosses, and how to change them."
    ),
    "run_and_gun": (
        "\n\n**This game is a run and gun**, seen from the side: a run through stages with lives"
        "\nand a score, not a village to walk. Where this file speaks of the starter map, doors,"
        "\nshops or quests, it speaks of the other kinds of game; start with section 22: the"
        "\ncontrols, the stages, their enemies and bosses, the grapple arm, and how to change them."
    ),
    "racing": (
        "\n\n**This game is a racing game**: a championship of races on tracks seen from above"
        "\n(at an angle in an isometric project), not a village to walk. Where this file speaks"
        "\nof the starter map, doors, shops or quests, it speaks of the other kinds of game;"
        "\nstart with section 22: the controls, the races, the championship, and how to change"
        "\nthe tracks."
    ),
    "metroidvania": (
        "\n\n**This game is a metroidvania**, seen from the side: its world is the rooms in"
        "\n`game/maps/rooms/`, not one starter map. Where this file says *starter map*, read *a"
        "\nroom*, and start with section 22: the controls, the rooms, abilities, enemies and save"
        "\nstations."
    ),
    "farm": (
        "\n\n**This game is a farm**: a top-down game in which the days pass. What this file"
        "\nsays of maps, doors, shops and saving holds for it, except where section 22 says"
        "\notherwise (a farm saves when you sleep, its light follows its own clock, its shop"
        "\npays the full price). Section 22 has what is its own: the controls, a day and how it"
        "\nends, energy, crops, animals, the shipping bin and the shop, the weather, the seasons,"
        "\nfishing and foraging, the people, and the isometric view."
    ),
}


def render_readme(
    template: str, cfg: config_mod.GeneratorConfig, runtime: str, archetype_notes: str = ""
) -> str:
    """Fill the README template (``str.format`` placeholders; values are never re-interpreted,
    so braces in a project name are safe). ``archetype_notes`` (the archetype's own section,
    ``README.<archetype>.md``) is appended as it is."""
    packs = "\n".join(f"- {p.pack_id}" for p in cfg.packs) or "- (none)"
    from rpggen.core import sound_slots

    custom = sound_slots.custom_slots(cfg.sounds, cfg.archetype)
    custom_list = "\n".join(f"  - `{key}`" for key in custom) or "  - (none yet)"
    text = template.format(
        project_name=cfg.project_name,
        archetype=cfg.archetype,  # not in the template any more; a placeholder all the same
        opening=opening(cfg.archetype),
        runtime_version=runtime,
        godot_version=cfg.godot_version,
        packs_list=packs,
        version_control_note=version_control_note(effective_pack_art(cfg)[0]),
        custom_sound_slots=custom_list,
        kind_note=KIND_NOTES.get(cfg.archetype, ""),
    )
    return text + archetype_notes


def write_project_files(
    stg: Staging, cfg: config_mod.GeneratorConfig, catalog: catalog_mod.Catalog
) -> list[Issue]:
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
    pack_art, issues = effective_pack_art(cfg)
    for name, template, make in (
        (".gitignore", "gitignore.txt", gitignore_text),
        (".gitattributes", "gitattributes.txt", gitattributes_text),
    ):
        text = make((files / template).read_text(encoding="utf-8"), pack_art)
        dst = root / name
        if not dst.is_file() or dst.read_bytes().replace(b"\r\n", b"\n") != text.encode("utf-8"):
            _write_text(dst, text)
    export_check.write_presets(root, cfg.project_name, cfg.selected_export_targets())
    notes_file = files / f"README.{cfg.archetype}.md"
    readme = render_readme(
        (files / README_TEMPLATE).read_text(encoding="utf-8"),
        cfg,
        runtime_version.read_version(paths.templates_root()) or "unknown",
        notes_file.read_text(encoding="utf-8") if notes_file.is_file() else "",
    )
    dst = root / "README.md"
    if not dst.is_file() or dst.read_bytes().replace(b"\r\n", b"\n") != readme.encode("utf-8"):
        _write_text(dst, readme)
    return issues


# What a failed run leaves out unless the setting "keep_full_failed_runs" is on: the pack art
# (a copy of every purchased file) and Godot's import cache. Both come back with the next run.
FAILED_TRIMMED = ("assets/packs", ".godot/imported")
FAILED_NOTE = "FAILED_RUN.md"


def _trim_failed(folder: Path) -> list[str]:
    """Delete the bulky folders of a failed run; returns the ones that were removed."""
    removed: list[str] = []
    for rel in FAILED_TRIMMED:
        path = folder.joinpath(*rel.split("/"))
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            removed.append(rel + "/")
    return removed


def _write_failed_note(folder: Path, removed: list[str]) -> None:
    lines = [
        "# A failed run",
        "",
        "This is what generation had built when it stopped: the logs (`rpggen/logs/`), the results",
        "(`rpggen/results/`), the reports, `generated/`, `game/` and `project.godot`.",
        "",
    ]
    if removed:
        lines += ["To save disk space these folders were deleted from this copy:", ""]
        lines += [f"* `{rel}`" for rel in removed]
        lines += [
            "",
            "The art was never changed: it is still in the asset pack you chose, and the next",
            "run copies it again. To keep everything of a failed run, turn on **Keep the whole",
            "folder of a failed run** in Edit > Storage….",
        ]
    else:
        lines += ["Nothing was deleted from this copy (the setting to keep everything is on)."]
    (folder / FAILED_NOTE).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def discard(stg: Staging, keep_everything: bool | None = None) -> Path:
    """Move staging to ``target/.rpggen_failed/<timestamp>/`` and keep the newest three.

    Unless the setting ``keep_full_failed_runs`` is on (``keep_everything`` overrides it), the
    pack art and the import cache are deleted from the kept copy and ``FAILED_RUN.md`` says so: a
    2 GB pack would otherwise leave 6 GB in the output folder, three times over."""
    failed_root = stg.target / FAILED_NAME
    failed_root.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = failed_root / stamp
    n = 1
    while dest.exists():
        n += 1
        dest = failed_root / f"{stamp}-{n}"
    shutil.move(str(stg.staging), str(dest))
    if keep_everything is None:
        keep_everything = app_settings.get().keep_full_failed_runs
    _write_failed_note(dest, [] if keep_everything else _trim_failed(dest))
    old = sorted((p for p in failed_root.iterdir() if p.is_dir()), key=lambda p: p.name)
    for p in old[:-KEEP_FAILED]:
        shutil.rmtree(p, ignore_errors=True)
    return dest
