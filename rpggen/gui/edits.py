"""Catalog edits: pure copy-on-write functions plus an undoable ``EditSession``.

The GUI never mutates a catalog. Every change is a function ``Catalog -> Catalog`` in this
module; the session pushes one undo command per edit holding the catalogs before and after.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from rpggen.core import catalog as catalog_mod
from rpggen.core import learned_rules, licenses
from rpggen.core.catalog import Asset, Catalog

RETILE_KEYS = frozenset({"grid", "usage", "tileset", "role"})  # facets that change tile sets


# --------------------------------------------------------------------------- pure functions


def _status_after_edit(asset: Asset) -> str:
    return catalog_mod.recompute_status(asset, file_missing=asset.status == "MISSING")


def _replace_assets(catalog: Catalog, new: dict[str, Asset]) -> Catalog:
    assets = [new.get(a.id, a) for a in catalog.assets]
    return dataclasses.replace(catalog, assets=assets)


def retile(catalog: Catalog) -> Catalog:
    """Re-group tile sheets into tile sets, keeping existing source ids."""
    assets = [dataclasses.replace(a, detected=dict(a.detected)) for a in catalog.assets]
    fresh = dataclasses.replace(
        catalog,
        assets=assets,
        tilesets=copy.deepcopy(catalog.tilesets),
        id_allocations=copy.deepcopy(catalog.id_allocations),
    )
    catalog_mod.assign_tilesets(fresh, previous=catalog)
    return fresh


def set_override(catalog: Catalog, asset_id: str, key: str, value: Any) -> Catalog:
    """Write ``overrides[key] = value`` (None deletes the facet). Status follows the edit."""
    return set_overrides(catalog, [asset_id], {key: value})


def set_overrides(catalog: Catalog, asset_ids: list[str], values: dict[str, Any]) -> Catalog:
    """Write several override keys on several assets as one change."""
    wanted = set(asset_ids)
    new: dict[str, Asset] = {}
    for asset in catalog.assets:
        if asset.id not in wanted:
            continue
        edited = dataclasses.replace(
            asset, overrides={**copy.deepcopy(asset.overrides), **copy.deepcopy(values)}
        )
        new[asset.id] = dataclasses.replace(edited, status=_status_after_edit(edited))
    if not new:
        return catalog
    result = _replace_assets(catalog, new)
    return retile(result) if RETILE_KEYS & values.keys() else result


def add_variant(
    catalog: Catalog, definition: dict[str, Any], pack_roots: dict[str, Path]
) -> Catalog:
    """A recolour variant (T13.18): its definition and its effective asset. Nothing changes
    when the definition cannot be rendered (a source that has no file)."""
    from rpggen.core import variants
    from rpggen.errors import IssueList

    fresh = dataclasses.replace(catalog, assets=list(catalog.assets))
    variants.apply(fresh, [*catalog.variants, definition], pack_roots, IssueList(), catalog)
    if fresh.asset(str(definition.get("id"))) is None:
        return catalog
    fresh.assets.sort(key=lambda a: catalog_mod._sort_key(a.id))
    return fresh


def remove_variant(catalog: Catalog, variant_id: str) -> Catalog:
    """Take a variant away again: its definition and its asset."""
    if not any(v.get("id") == variant_id for v in catalog.variants):
        return catalog
    return dataclasses.replace(
        catalog,
        assets=[a for a in catalog.assets if a.id != variant_id],
        variants=[copy.deepcopy(v) for v in catalog.variants if v.get("id") != variant_id],
    )


def clear_override(catalog: Catalog, asset_id: str, key: str) -> Catalog:
    """Remove ``overrides[key]`` so the detected (or rule) value applies again."""
    asset = catalog.asset(asset_id)
    if asset is None or key not in asset.overrides:
        return catalog
    overrides = {k: v for k, v in asset.overrides.items() if k != key}
    edited = dataclasses.replace(asset, overrides=overrides)
    edited = dataclasses.replace(edited, status=_status_after_edit(edited))
    result = _replace_assets(catalog, {asset_id: edited})
    return retile(result) if key in RETILE_KEYS else result


def confirm(catalog: Catalog, asset_ids: list[str]) -> Catalog:
    """Mark assets CONFIRMED without changing any facet (resolves CONFLICT too)."""
    wanted = set(asset_ids)
    new: dict[str, Asset] = {}
    for asset in catalog.assets:
        if asset.id not in wanted:
            continue
        if catalog_mod.effective(asset).get("role") == "NONE":
            status = "UNUSED"
        else:
            status = "MISSING" if asset.status == "MISSING" else "CONFIRMED"
        if status != asset.status:
            new[asset.id] = dataclasses.replace(asset, status=status)
    return _replace_assets(catalog, new) if new else catalog


def bulk_tags(catalog: Catalog, asset_ids: list[str], add: list[str], remove: list[str]) -> Catalog:
    """Add and remove tags on several assets (each keeps its other tags)."""
    wanted = set(asset_ids)
    new: dict[str, Asset] = {}
    for asset in catalog.assets:
        if asset.id not in wanted:
            continue
        tags = list(catalog_mod.effective(asset).get("tags") or [])
        updated = [t for t in tags if t not in remove] + [
            t for t in add if t not in tags and t not in remove
        ]
        if updated != tags:
            edited = dataclasses.replace(asset, overrides={**asset.overrides, "tags": updated})
            new[asset.id] = dataclasses.replace(edited, status=_status_after_edit(edited))
    return _replace_assets(catalog, new) if new else catalog


def _with_rules(catalog: Catalog, rules: list[catalog_mod.FolderRule]) -> Catalog:
    """A catalog with ``rules`` applied (rule layers rebuilt, statuses and tile sets redone)."""
    assets = [dataclasses.replace(a, rule={}, detected=dict(a.detected)) for a in catalog.assets]
    fresh = dataclasses.replace(
        catalog,
        assets=assets,
        folder_rules=copy.deepcopy(rules),
        tilesets=copy.deepcopy(catalog.tilesets),
        id_allocations=copy.deepcopy(catalog.id_allocations),
    )
    catalog_mod.apply_folder_rules(fresh)
    for i, asset in enumerate(fresh.assets):
        fresh.assets[i] = dataclasses.replace(
            asset,
            status=catalog_mod.recompute_status(
                asset,
                file_missing=asset.status == "MISSING",
                user_confirmed=asset.status == "CONFIRMED",
            ),
        )
    catalog_mod.assign_tilesets(fresh, previous=catalog)
    return fresh


def add_folder_rule(catalog: Catalog, rule: catalog_mod.FolderRule) -> Catalog:
    return _with_rules(catalog, [*catalog.folder_rules, rule])


def delete_folder_rule(catalog: Catalog, index: int) -> Catalog:
    if not 0 <= index < len(catalog.folder_rules):
        return catalog
    rules = [r for i, r in enumerate(catalog.folder_rules) if i != index]
    return _with_rules(catalog, rules)


def reorder_folder_rules(catalog: Catalog, order: list[int]) -> Catalog:
    """Rules in the order given by ``order`` (indices into the current list); re-applies all."""
    if sorted(order) != list(range(len(catalog.folder_rules))) or order == sorted(order):
        return catalog
    return _with_rules(catalog, [catalog.folder_rules[i] for i in order])


def set_pack_license(catalog: Catalog, pack_id: str, key: str, value: Any) -> Catalog:
    """A correction of a pack's licence (``key`` one of ``licenses.KEYS``). A value that equals
    what the pack would have without the correction removes it."""
    pack = next((p for p in catalog.packs if p.pack_id == pack_id), None)
    if pack is None or key not in licenses.KEYS:
        return catalog
    overrides = {k: v for k, v in pack.license_overrides.items() if k != key}
    if value != getattr(licenses.effective(pack.license, overrides), key):
        overrides[key] = value
    if overrides == pack.license_overrides:
        return catalog
    packs = [
        dataclasses.replace(p, license_overrides=overrides) if p is pack else p
        for p in catalog.packs
    ]
    return dataclasses.replace(catalog, packs=packs)


def _with_objects(catalog: Catalog, objects: list[catalog_mod.SheetObject]) -> Catalog:
    return dataclasses.replace(catalog, objects=objects)


def add_object(catalog: Catalog, obj: catalog_mod.SheetObject) -> Catalog:
    return _with_objects(catalog, [*catalog.objects, copy.deepcopy(obj)])


def update_object(catalog: Catalog, object_id: str, **changes: Any) -> Catalog:
    """Replace fields of an object. An edited auto object becomes a user object, so a later
    re-analysis keeps the edit instead of re-creating the detection."""
    out: list[catalog_mod.SheetObject] = []
    found = False
    for obj in catalog.objects:
        if obj.id != object_id:
            out.append(obj)
            continue
        found = True
        edited = copy.deepcopy(obj)
        for key, value in changes.items():
            setattr(edited, key, copy.deepcopy(value))
        if edited.source == "auto" and "source" not in changes and "status" not in changes:
            edited.source = "user"
        out.append(edited)
    return _with_objects(catalog, out) if found else catalog


def remove_object(catalog: Catalog, object_id: str) -> Catalog:
    objects = [o for o in catalog.objects if o.id != object_id]
    return _with_objects(catalog, objects) if len(objects) != len(catalog.objects) else catalog


def reject_object(catalog: Catalog, object_id: str) -> Catalog:
    """Remember a rejected suggestion: it stays in the catalog with role NONE, so detection
    does not create it again."""
    return update_object(catalog, object_id, role="NONE", status="UNUSED")


def accept_suggestions(catalog: Catalog, sheet_id: str) -> Catalog:
    """Mark the auto-detected objects of a sheet CONFIRMED."""
    out = []
    changed = False
    for obj in catalog.objects:
        if obj.sheet == sheet_id and obj.source != "user" and obj.status == "AUTO_DETECTED":
            obj = dataclasses.replace(copy.deepcopy(obj), status="CONFIRMED")
            changed = True
        out.append(obj)
    return _with_objects(catalog, out) if changed else catalog


def set_sheet_objects(
    catalog: Catalog, sheet_id: str, objects: list[catalog_mod.SheetObject]
) -> Catalog:
    """Replace every object of one sheet (the object cutter's Apply)."""
    kept = [o for o in catalog.objects if o.sheet != sheet_id]
    result = kept + [copy.deepcopy(o) for o in objects]
    result.sort(key=lambda o: o.id)
    return _with_objects(catalog, result) if result != catalog.objects else catalog


# --------------------------------------------------------------------------- undoable session


def learnable_edits(before: Catalog, after: Catalog, ids: list[str]) -> list[learned_rules.Edit]:
    """The role, usage or collision values the user set on ``ids`` in this step (T12.59)."""
    old = {a.id: a for a in before.assets}
    new = {a.id: a for a in after.assets}
    found: list[learned_rules.Edit] = []
    for asset_id in ids:
        a, b = old.get(asset_id), new.get(asset_id)
        if a is None or b is None:
            continue
        for facet in learned_rules.LEARNABLE:
            value = b.overrides.get(facet)
            if value is not None and value != a.overrides.get(facet):
                found.append(learned_rules.Edit(learned_rules.pack_relative(b.path), facet, value))
    return found


class _CatalogCommand(QUndoCommand):
    def __init__(
        self, session: EditSession, text: str, before: Catalog, after: Catalog, ids: list[str]
    ) -> None:
        super().__init__(text)
        self.session, self.before, self.after, self.ids = session, before, after, ids
        self.taught = learnable_edits(before, after, ids) if session.learner else []

    def redo(self) -> None:
        self.session._set(self.after, self.ids)
        if self.taught and self.session.learner is not None:
            self.session.learner(self.taught, 1)

    def undo(self) -> None:
        self.session._set(self.before, self.ids)
        if self.taught and self.session.learner is not None:
            self.session.learner(self.taught, -1)  # an undone fix teaches nothing


class EditSession(QObject):
    """Owns the catalog being audited and its undo stack."""

    changed = Signal(list)  # ids of the assets touched ([] when the whole catalog changed)

    def __init__(self, catalog: Catalog, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.undo_stack = QUndoStack(self)
        # learns from role, usage and collision fixes (T12.59): (edits, +1, or -1 on undo)
        self.learner: Callable[[list[learned_rules.Edit], int], None] | None = None

    def _set(self, catalog: Catalog, ids: list[str]) -> None:
        self.catalog = catalog
        self.changed.emit(list(ids))

    def apply(
        self, text: str, change: Callable[[Catalog], Catalog], ids: list[str] | None = None
    ) -> bool:
        """Run ``change`` on the current catalog and push it as one undo step."""
        before = self.catalog
        after = change(before)
        if after is before:
            return False
        self.undo_stack.push(_CatalogCommand(self, text, before, after, ids or []))
        return True

    def reset(self, catalog: Catalog) -> None:
        """Replace the catalog without an undo step (a new analysis result)."""
        self.undo_stack.clear()
        self._set(catalog, [])

    # convenience wrappers: one undo step each
    def set_override(self, asset_id: str, key: str, value: Any) -> bool:
        return self.apply(f"Set {key}", lambda c: set_override(c, asset_id, key, value), [asset_id])

    def clear_override(self, asset_id: str, key: str) -> bool:
        return self.apply(f"Reset {key}", lambda c: clear_override(c, asset_id, key), [asset_id])

    def confirm(self, asset_ids: list[str]) -> bool:
        return self.apply("Confirm", lambda c: confirm(c, asset_ids), list(asset_ids))

    def add_variant(self, definition: dict[str, Any], pack_roots: dict[str, Path]) -> bool:
        ids = [str(definition.get("id"))]
        return self.apply("Make variant", lambda c: add_variant(c, definition, pack_roots), ids)

    def remove_variant(self, variant_id: str) -> bool:
        return self.apply("Remove variant", lambda c: remove_variant(c, variant_id), [variant_id])

    def set_overrides(
        self, asset_ids: list[str], values: dict[str, Any], text: str = "Edit"
    ) -> bool:
        return self.apply(text, lambda c: set_overrides(c, asset_ids, values), list(asset_ids))

    def bulk_edit(
        self,
        asset_ids: list[str],
        values: dict[str, Any],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
    ) -> bool:
        """Facet overrides and tag changes for several assets as one undo step."""
        ids = list(asset_ids)

        def change(c: Catalog) -> Catalog:
            if values:
                c = set_overrides(c, ids, values)
            if add_tags or remove_tags:
                c = bulk_tags(c, ids, add_tags or [], remove_tags or [])
            return c

        return self.apply("Edit selection", change, ids)

    def revert(self, change: Change) -> bool:
        """Put one change back to the detected state (an undo step of its own)."""
        if change.key == "folder_rule":
            return self.delete_rule(int(change.ref))
        if change.key == "object":
            if change.after == "rejected":
                return self.apply(
                    "Revert object",
                    lambda c: update_object(c, str(change.ref), status="AUTO_DETECTED"),
                )
            return self.remove_object(str(change.ref))
        return self.apply(
            f"Revert {change.key}",
            lambda c: clear_override(c, change.asset_id, change.key),
            [change.asset_id],
        )

    def set_pack_license(self, pack_id: str, key: str, value: Any) -> bool:
        return self.apply(
            "Edit pack information", lambda c: set_pack_license(c, pack_id, key, value)
        )

    def add_rule(self, rule: catalog_mod.FolderRule) -> bool:
        return self.apply("Add folder rule", lambda c: add_folder_rule(c, rule))

    def delete_rule(self, index: int) -> bool:
        return self.apply("Delete folder rule", lambda c: delete_folder_rule(c, index))

    def reorder_rules(self, order: list[int]) -> bool:
        return self.apply("Reorder folder rules", lambda c: reorder_folder_rules(c, order))

    def add_object(self, obj: catalog_mod.SheetObject) -> bool:
        return self.apply("Add object", lambda c: add_object(c, obj))

    def update_object(self, object_id: str, **changes: Any) -> bool:
        return self.apply("Edit object", lambda c: update_object(c, object_id, **changes))

    def remove_object(self, object_id: str) -> bool:
        return self.apply("Remove object", lambda c: remove_object(c, object_id))

    def reject_object(self, object_id: str) -> bool:
        return self.apply("Reject object", lambda c: reject_object(c, object_id))

    def accept_suggestions(self, sheet_id: str) -> bool:
        return self.apply("Accept suggestions", lambda c: accept_suggestions(c, sheet_id))

    def set_sheet_objects(self, sheet_id: str, objects: list[catalog_mod.SheetObject]) -> bool:
        return self.apply("Edit objects", lambda c: set_sheet_objects(c, sheet_id, objects))


# --------------------------------------------------------------------------- what changed (T12.43)

CHANGE_KINDS = ("role", "excluded", "grid", "collision", "animations", "objects", "rules", "other")
_OVERRIDE_KIND = {
    "role": "role",
    "grid": "grid",
    "collision": "collision",
    "animations": "animations",
}


@dataclass(frozen=True)
class Change:
    """One difference between what was detected and what the catalog says now."""

    kind: str  # one of CHANGE_KINDS
    key: str  # the facet ("role", "grid", ...), "folder_rule" or "object"
    label: str  # the asset's path, the rule's glob or the object's name
    before: Any  # the detected value (None: there was none)
    after: Any
    asset_id: str = ""  # the asset (or the sheet of an object) the row belongs to
    ref: Any = None  # rule index or object id, for the revert


def describe_changes(catalog: Catalog) -> list[Change]:
    """Every asset override that differs from the detection, the folder rules and the objects
    the user added or rejected, in a stable order (assets by path, then rules, then objects)."""
    found: list[Change] = []
    for asset in sorted(catalog.assets, key=lambda a: a.path):
        for key, after in sorted(asset.overrides.items()):
            before = asset.detected.get(key)
            if before == after:
                continue
            if key == "role" and after == "NONE":
                kind = "excluded"
            else:
                kind = _OVERRIDE_KIND.get(key, "other")
            found.append(Change(kind, key, asset.path, before, after, asset.id))
    for index, rule in enumerate(catalog.folder_rules):
        found.append(
            Change(
                "rules",
                "folder_rule",
                f"{rule.pack_id}: {rule.glob}",
                None,
                dict(rule.set),
                "",
                index,
            )
        )
    for obj in sorted(catalog.objects, key=lambda o: o.id):
        if obj.status == "UNUSED":
            found.append(
                Change("objects", "object", obj.name, "detected", "rejected", obj.sheet, obj.id)
            )
        elif obj.source != "auto":
            found.append(Change("objects", "object", obj.name, None, "added", obj.sheet, obj.id))
    return found
