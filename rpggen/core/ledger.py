"""Ownership ledger (T5.01): which files the generator wrote, with their hashes.

The ledger is what lets regeneration tell a file the user changed from one it can rewrite.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from rpggen import __version__, jsonio, paths, schema

TEXT_EXTS = {
    ".gd",
    ".tscn",
    ".tres",
    ".json",
    ".cfg",
    ".godot",
    ".md",
    ".import",
    ".uid",
    ".txt",
    ".csv",
    ".gitignore",
    ".gitattributes",
}
# Files whose name is the whole story (``Path(".gitignore").suffix`` is empty).
TEXT_NAMES = {".gitignore", ".gitattributes"}

# Paths the ledger covers (T5.01). A trailing slash is a folder prefix.
COVERED_PREFIXES = (
    "generated/",
    "addons/rpg_runtime/",
    "addons/rpg_project_tools/",
    "rpggen/",
    "assets/packs/",
    "game/",
)
COVERED_FILES = ("project.godot", ".gitignore", ".gitattributes", "README.md")
# Never in the ledger: logs and results change on every run, the report is rewritten after
# promotion, backups and staging are regeneration's own working folders.
EXCLUDED_PREFIXES = ("rpggen/logs/", "rpggen/results/")
EXCLUDED_FILES = ("GENERATION_REPORT.md", "rpggen/generation_report.json", paths.LEDGER)
# Never a conflict: the generator merges into these instead (project.godot keys, the catalog's
# user overrides, the config the wizard edits).
MERGE_MANAGED = ("project.godot", paths.CONFIG, paths.CATALOG)


def is_text(rel: str) -> bool:
    """True for files hashed (and merged, T12.58) as text: by extension, or name for dotfiles."""
    p = Path(rel)
    return p.suffix.lower() in TEXT_EXTS or p.name.lower() in TEXT_NAMES


def hash_bytes(data: bytes, rel: str) -> str:
    """The ledger hash of ``data`` as the content of ``rel``: ``file_hash`` without the file, so
    that a ``.rpggen-new`` copy is hashed as the file it stands for."""
    if is_text(rel):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    """sha256. Text files (by extension, or name for dotfiles): read bytes, replace CRLF with LF
    and hash. Other files: raw bytes."""
    path = Path(path)
    if is_text(path.name):
        return hash_bytes(path.read_bytes(), path.name)
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class LedgerEntry:
    sha256: str
    written_by: str
    owner: Literal["generated", "user_seed"]
    # T12.58: generated content the user declined ("Keep mine"); promotion does not raise the
    # conflict again while the generator still produces exactly this
    declined_sha256: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"sha256": self.sha256, "written_by": self.written_by}
        out["owner"] = self.owner
        if self.declined_sha256:
            out["declined_sha256"] = self.declined_sha256
        return out


@dataclass
class Ledger:
    files: dict[str, LedgerEntry] = field(default_factory=dict)
    deleted_by_user: list[str] = field(default_factory=list)
    generator_version: str = __version__
    # The user removed the demo content in the editor (T8.08): the demo recipes leave it out.
    demo_removed: bool = False
    # T15.20: a fingerprint of everything the last successful run was made from (the catalog,
    # the config, the templates, the placeholders) and the Godot that built it. A regeneration
    # with the same two repeats nothing. Empty in a ledger written before 1.3.0.
    inputs_sha256: str = ""
    godot_version: str = ""
    # ... unless the project's owner asked for every check, every time
    run_every_check: bool = False

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ledger_version": 1,
            "generator_version": self.generator_version,
            "files": {rel: e.to_json() for rel, e in sorted(self.files.items())},
            "deleted_by_user": sorted(set(self.deleted_by_user)),
        }
        if self.demo_removed:
            out["demo_removed"] = True
        if self.inputs_sha256:
            out["inputs_sha256"] = self.inputs_sha256
        if self.godot_version:
            out["godot_version"] = self.godot_version
        if self.run_every_check:
            out["run_every_check"] = True
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Ledger:
        schema.validate("ledger", data)
        return cls(
            {
                rel: LedgerEntry(e["sha256"], e["written_by"], e["owner"], e.get("declined_sha256"))
                for rel, e in data["files"].items()
            },
            list(data["deleted_by_user"]),
            data["generator_version"],
            bool(data.get("demo_removed", False)),
            str(data.get("inputs_sha256", "")),
            str(data.get("godot_version", "")),
            bool(data.get("run_every_check", False)),
        )

    @classmethod
    def load(cls, path: Path) -> Ledger:
        return cls.from_json(jsonio.read(path))

    def save(self, path: Path) -> None:
        data = self.to_json()
        schema.validate("ledger", data)
        jsonio.write(path, data)


class FileState(StrEnum):
    UNTOUCHED = "untouched"  # exists, hash == ledger
    MODIFIED = "modified"  # exists, hash != ledger
    DELETED = "deleted"  # in ledger, missing on disk (and not already in deleted_by_user)
    UNKNOWN = "unknown"  # exists, not in ledger (user-created or pre-existing)
    ABSENT = "absent"  # not in ledger, not on disk


def classify(target: Path, rel: str, ledger: Ledger) -> FileState:
    path = paths.from_posix_rel(rel, Path(target))
    entry = ledger.files.get(rel)
    if path.is_file():
        if entry is None:
            return FileState.UNKNOWN
        return FileState.UNTOUCHED if file_hash(path) == entry.sha256 else FileState.MODIFIED
    if entry is not None and rel not in ledger.deleted_by_user:
        return FileState.DELETED
    return FileState.ABSENT


def is_covered(rel: str) -> bool:
    """True when the ledger tracks this project-relative path."""
    if rel in EXCLUDED_FILES or rel.startswith(EXCLUDED_PREFIXES):
        return False
    return rel in COVERED_FILES or rel.startswith(COVERED_PREFIXES)


def owner_of(rel: str) -> Literal["generated", "user_seed"]:
    return "user_seed" if rel.startswith(paths.GAME_DIR) else "generated"


def _written_by(rel: str, recipes: dict[str, str]) -> str:
    if rel in recipes:
        return recipes[rel]
    if rel.startswith(("addons/", "generated/builder/")):
        return "templates"
    if rel.startswith(paths.PACKS_DIR):
        return "pack_install"
    if rel.startswith("rpggen/"):
        return "orchestrator"
    return "project_files"


def recipes_from_results(project: Path) -> dict[str, str]:
    """Output path -> recipe name, read from the build results file."""
    path = Path(project) / paths.RESULTS_BUILD
    if not path.is_file():
        return {}
    items = jsonio.read(path).get("items", [])
    return {i["output"]: i["recipe"] for i in items if i.get("output") and i.get("recipe")}


def edited_generated_files(target: Path, ledger: Ledger, limit: int = 1) -> list[str]:
    """Generated files of the project that are not as the ledger recorded them: changed, or
    deleted without the ledger knowing (T15.20: a regeneration over them is not a repeat; it
    has a conflict to find or a deletion to respect). Files a person is meant to edit are not
    looked at here: the ledger keeps what a ``game/`` seed was when it was made, not what it
    was at the last run (``run_memory.own_files_changed`` knows that), and the config and the
    catalog are in the fingerprint. Stops after ``limit`` finds."""
    found: list[str] = []
    for rel, entry in ledger.files.items():
        if entry.owner != "generated" or rel in MERGE_MANAGED:
            continue
        if classify(Path(target), rel, ledger) in (FileState.MODIFIED, FileState.DELETED):
            found.append(rel)
            if len(found) >= limit:
                break
    return found


def scan(staging: Path, target: Path | None = None, old: Ledger | None = None) -> Ledger:
    """The ledger a finished staging folder describes.

    Every covered file in ``staging`` is hashed. Files under ``game/`` are user seeds: the entry
    of an earlier ledger is kept (it records the content at creation). A file that is in no
    earlier ledger but already exists in ``target`` was made by the user and is not recorded.
    """
    staging = Path(staging)
    old = old or Ledger()
    recipes = recipes_from_results(staging)
    files: dict[str, LedgerEntry] = {}
    for p in sorted(staging.rglob("*")):
        if not p.is_file():
            continue
        rel = paths.to_posix_rel(p, staging)
        if rel.startswith((".rpggen_", ".git/", ".godot/")) or not is_covered(rel):
            continue
        owner = owner_of(rel)
        if owner == "user_seed" and rel in old.files:
            files[rel] = old.files[rel]
            continue
        if rel not in old.files and target is not None and (Path(target) / rel).is_file():
            continue  # exists in the target but the ledger never wrote it: user-created
        digest = file_hash(p)
        previous = old.files.get(rel)
        if previous is not None and previous.sha256 == digest and previous.owner == owner:
            # Unchanged content: keep who wrote it (a run that skipped the recipe has no record).
            files[rel] = previous
            continue
        files[rel] = LedgerEntry(digest, _written_by(rel, recipes), owner)
    return Ledger(
        files,
        list(old.deleted_by_user),
        demo_removed=old.demo_removed,
        run_every_check=old.run_every_check,
    )
