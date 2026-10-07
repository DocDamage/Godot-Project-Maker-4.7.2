"""What a pack update changed (T5.05): files added, removed, replaced or resized."""

from __future__ import annotations

from dataclasses import dataclass, field

from rpggen.core.inventory import Inventory, InventoryFile


@dataclass
class PackDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed_same_size: list[str] = field(default_factory=list)
    changed_resized: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    renamed: dict[str, str] = field(default_factory=dict)  # new path -> old path

    @property
    def is_empty(self) -> bool:
        return not (
            self.added
            or self.removed
            or self.changed_same_size
            or self.changed_resized
            or self.renamed
        )

    def changed_paths(self) -> list[str]:
        """Paths the audit's "Changed in update" filter shows (added, resized, missing)."""
        return sorted(set(self.added) | set(self.changed_resized) | set(self.removed))


def _size(f: InventoryFile) -> tuple[int, int] | None:
    return (f.image["w"], f.image["h"]) if f.image else None


def diff(old_inv: Inventory, new_inv: Inventory) -> PackDiff:
    """Compare two inventories of the same pack by path.

    A file that is new by path but has the hash of a removed file is a rename (the vendor moved
    it), not an addition plus a removal.
    """
    old = {f.path: f for f in old_inv.files}
    new = {f.path: f for f in new_inv.files}
    result = PackDiff()
    for path in sorted(set(old) & set(new)):
        a, b = old[path], new[path]
        if a.sha256 == b.sha256:
            result.unchanged.append(path)
        elif _size(a) is not None and _size(b) is not None and _size(a) != _size(b):
            result.changed_resized.append(path)
        else:
            result.changed_same_size.append(path)
    gone = {p: old[p] for p in sorted(set(old) - set(new))}
    fresh = [p for p in sorted(set(new) - set(old))]
    by_hash: dict[str, list[str]] = {}
    for p, f in gone.items():
        by_hash.setdefault(f.sha256, []).append(p)
    for path in fresh:
        candidates = [
            p for p in by_hash.get(new[path].sha256, []) if p not in result.renamed.values()
        ]
        if len(candidates) == 1:
            result.renamed[path] = candidates[0]
        else:
            result.added.append(path)
    renamed_old = set(result.renamed.values())
    result.removed = [p for p in gone if p not in renamed_old]
    return result
