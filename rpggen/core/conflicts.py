"""Resolving ``.rpggen-new`` conflicts (T12.58).

A regeneration that finds a generated file the user changed writes the new version beside it as
``<file>.rpggen-new`` (REGEN-001). This module lists those files, shows the three versions (the
*base* rpggen last wrote, the user's, the new one) and resolves one file at a time:

* **Keep mine** deletes the ``.rpggen-new`` file and records its hash as the ledger entry's
  ``declined_sha256``: promotion does not raise the conflict again while the generator still
  produces exactly that content.
* **Take new** replaces the file with the new version and records its hash, so the next
  regeneration rewrites the file freely.
* **Merge** (text files) writes a line-based three-way merge, with conflict markers where both
  sides changed the same lines, and records the new version as both the base and the declined
  content. ``.tscn`` and ``.tres`` files should be opened in Godot afterwards.

Every action first backs up the file, its ``.rpggen-new`` and the ledger into a new folder of
``.rpggen_backups`` (so *Restore previous* undoes it); that backup also keeps the new version.
The base is the content whose hash the ledger holds: looked up in the backups, newest first (the
file itself or its ``.rpggen-new``), then in the project's git history (rpggen commits every
generation).
"""

from __future__ import annotations

import difflib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rpggen import paths
from rpggen.core import ledger as ledger_mod
from rpggen.core import promote, vcs
from rpggen.core.ledger import LedgerEntry
from rpggen.errors import RpgGenError

log = logging.getLogger(__name__)

NEW_SUFFIX = promote.NEW_SUFFIX
# folders that are rpggen's or the tools' own, never the project's files
SKIP_TOP = (".rpggen_backups", ".rpggen_staging", ".rpggen_failed", ".git", ".godot")
GODOT_RESOURCE_EXTS = (".tscn", ".tres")
MARK_MINE = "<<<<<<< yours"
MARK_BASE = "||||||| last generated"
MARK_SPLIT = "======="
MARK_NEW = ">>>>>>> rpggen"


class Action(StrEnum):
    KEEP_MINE = "keep_mine"
    TAKE_NEW = "take_new"
    MERGE = "merge"


@dataclass(frozen=True)
class Versions:
    """The three versions of a conflicting file (bytes; ``base`` None when no backup has it)."""

    rel: str
    base: bytes | None
    mine: bytes | None  # None when the user has since deleted the file
    new: bytes

    @property
    def text(self) -> bool:
        return ledger_mod.is_text(self.rel)


@dataclass(frozen=True)
class Resolution:
    rel: str
    action: Action
    backup: Path
    conflicts: int = 0  # merge: the regions left with conflict markers
    check_in_godot: bool = False  # a merged scene or resource: open it in Godot to validate it


def _new_rel(rel: str) -> str:
    return rel + NEW_SUFFIX


def list_conflicts(target: Path) -> list[str]:
    """The project files (posix_rel) that have a ``.rpggen-new`` sibling, sorted."""
    target = Path(target)
    found: list[str] = []
    for path in target.rglob(f"*{NEW_SUFFIX}"):
        if not path.is_file():
            continue
        rel = paths.to_posix_rel(path, target)
        if rel.split("/", 1)[0] in SKIP_TOP:
            continue
        found.append(rel[: -len(NEW_SUFFIX)])
    return sorted(found)


def find_base(target: Path, rel: str, ledger: ledger_mod.Ledger | None = None) -> bytes | None:
    """The content rpggen last wrote to ``rel``: the newest backup file (``rel`` itself or its
    ``.rpggen-new``) whose hash is the ledger's. None when no backup holds it."""
    target = Path(target)
    ledger = ledger if ledger is not None else promote.load_ledger(target)
    entry = ledger.files.get(rel)
    if entry is None:
        return None
    for backup in reversed(promote.list_backups(target)):
        for candidate in (rel, _new_rel(rel)):
            path = paths.from_posix_rel(candidate, backup)
            if path.is_file():
                data = path.read_bytes()
                if ledger_mod.hash_bytes(data, rel) == entry.sha256:
                    return data
    # rpggen commits every generation (T12.12): the version it wrote is usually in git
    for data in vcs.committed_versions(target, rel):
        if ledger_mod.hash_bytes(data, rel) == entry.sha256:
            return data
    return None


def versions(target: Path, rel: str) -> Versions:
    target = Path(target)
    new_path = paths.from_posix_rel(_new_rel(rel), target)
    if not new_path.is_file():
        raise RpgGenError("REGEN-009", file=rel)
    mine_path = paths.from_posix_rel(rel, target)
    return Versions(
        rel,
        find_base(target, rel),
        mine_path.read_bytes() if mine_path.is_file() else None,
        new_path.read_bytes(),
    )


# --------------------------------------------------------------------------- merge


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="surrogateescape")


def _encode(text: str) -> bytes:
    return text.encode("utf-8", errors="surrogateescape")


def _lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").splitlines(keepends=True)


def _matches(base: Sequence[str], other: Sequence[str]) -> dict[int, int]:
    """base line index -> other line index, for the lines the two have in common (in order)."""
    matcher = difflib.SequenceMatcher(None, base, other, autojunk=False)
    out: dict[int, int] = {}
    for a, b, size in matcher.get_matching_blocks():
        for n in range(size):
            out[a + n] = b + n
    return out


def _closed(lines: Sequence[str]) -> list[str]:
    """``lines`` whose last line ends with a newline, so a marker after it starts a line."""
    out = list(lines)
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    return out


def _conflict(mine: Sequence[str], base: Sequence[str] | None, new: Sequence[str]) -> list[str]:
    out = [MARK_MINE + "\n", *_closed(mine)]
    if base is not None:
        out += [MARK_BASE + "\n", *_closed(base)]
    return out + [MARK_SPLIT + "\n", *_closed(new), MARK_NEW + "\n"]


def merge3(base: Sequence[str], mine: Sequence[str], new: Sequence[str]) -> tuple[list[str], int]:
    """Line-based three-way merge (diff3). A region only one side changed takes that change; a
    region both changed the same way is taken once; any other region gets conflict markers with
    all three versions. Returns (lines, the number of conflict regions)."""
    to_mine, to_new = _matches(base, mine), _matches(base, new)
    out: list[str] = []
    conflicts = 0
    i = j = k = 0  # positions in base, mine, new
    n = len(base)
    while True:
        run = 0  # lines stable in all three
        while i + run < n and to_mine.get(i + run) == j + run and to_new.get(i + run) == k + run:
            run += 1
        if run:
            out += base[i : i + run]
            i, j, k = i + run, j + run, k + run
            continue
        sync = i  # the next base line both sides still have
        while sync < n and not (
            sync in to_mine and sync in to_new and to_mine[sync] >= j and to_new[sync] >= k
        ):
            sync += 1
        end_mine, end_new = (to_mine[sync], to_new[sync]) if sync < n else (len(mine), len(new))
        b, m, w = base[i:sync], mine[j:end_mine], new[k:end_new]
        if not (b or m or w):
            break
        if m == w or w == b:
            out += m
        elif m == b:
            out += w
        else:
            out += _conflict(m, b, w)
            conflicts += 1
        i, j, k = sync, end_mine, end_new
    return out, conflicts


def merge2(mine: Sequence[str], new: Sequence[str]) -> tuple[list[str], int]:
    """Without a base: the lines both have stay, every difference becomes a conflict region."""
    out: list[str] = []
    conflicts = 0
    matcher = difflib.SequenceMatcher(None, mine, new, autojunk=False)
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            out += mine[a1:a2]
        else:
            out += _conflict(mine[a1:a2], None, new[b1:b2])
            conflicts += 1
    return out, conflicts


def merge_text(base: bytes | None, mine: bytes, new: bytes) -> tuple[bytes, int]:
    """Merge three versions of a text file; the result keeps the line endings of ``mine``."""
    crlf = b"\r\n" in mine
    m, w = _lines(_decode(mine)), _lines(_decode(new))
    if base is None:
        merged, count = merge2(m, w)
    else:
        merged, count = merge3(_lines(_decode(base)), m, w)
    text = "".join(merged)
    if crlf:
        text = text.replace("\n", "\r\n")
    return _encode(text), count


# --------------------------------------------------------------------------- actions


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + promote.TMP_SUFFIX)
    tmp.write_bytes(data)
    try:
        promote._atomic_replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def resolve(target: Path, rel: str, action: Action | str) -> Resolution:
    """Resolve the conflict of ``rel`` (see the module docstring). Backs up first; a failure puts
    the backed-up files back and raises REGEN-004."""
    target = Path(target)
    action = Action(action)
    found = versions(target, rel)
    if action is Action.MERGE and not found.text:
        raise RpgGenError("REGEN-010", file=rel)
    mine_path = paths.from_posix_rel(rel, target)
    new_path = paths.from_posix_rel(_new_rel(rel), target)
    ledger_path = paths.from_posix_rel(paths.LEDGER, target)
    ledger = promote.load_ledger(target)
    new_hash = ledger_mod.hash_bytes(found.new, rel)
    entry = ledger.files.get(rel)
    backup = promote._backup_dir(target)
    promote._backup_files(target, backup, [rel, _new_rel(rel), paths.LEDGER])
    count = 0
    try:
        if action is Action.KEEP_MINE:
            if entry is not None:
                entry.declined_sha256 = new_hash
        elif action is Action.TAKE_NEW:
            _write(mine_path, found.new)
            ledger.files[rel] = LedgerEntry(
                new_hash,
                entry.written_by if entry else "conflict_resolver",
                ledger_mod.owner_of(rel),
            )
        else:
            merged, count = merge_text(found.base, found.mine or b"", found.new)
            _write(mine_path, merged)
            # the new version is now the base, and is not offered again as a conflict
            ledger.files[rel] = LedgerEntry(
                new_hash,
                entry.written_by if entry else "conflict_resolver",
                ledger_mod.owner_of(rel),
                new_hash,
            )
        new_path.unlink()
        ledger.save(ledger_path)
    except Exception as exc:
        log.exception("resolving %s failed; putting the files back", rel)
        for item in (rel, _new_rel(rel), paths.LEDGER):
            saved = paths.from_posix_rel(item, backup)
            if saved.is_file():
                _write(paths.from_posix_rel(item, target), saved.read_bytes())
            elif item == rel:  # the user had deleted it: Take new must not leave it created
                mine_path.unlink(missing_ok=True)
        raise RpgGenError("REGEN-004", reason=f"{type(exc).__name__}: {exc}") from exc
    return Resolution(
        rel,
        action,
        backup,
        count,
        action is Action.MERGE and Path(rel).suffix.lower() in GODOT_RESOURCE_EXTS,
    )
