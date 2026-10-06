"""Catalog edits: pure copy-on-write functions plus an undoable ``EditSession``.

The GUI never mutates a catalog. Every change is a function ``Catalog -> Catalog`` in this
module; the session pushes one undo command per edit holding the catalogs before and after.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from rpggen.core import catalog as catalog_mod
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


class _CatalogCommand(QUndoCommand):
    def __init__(
        self, session: EditSession, text: str, before: Catalog, after: Catalog, ids: list[str]
    ) -> None:
        super().__init__(text)
        self.session, self.before, self.after, self.ids = session, before, after, ids

    def redo(self) -> None:
        self.session._set(self.after, self.ids)

    def undo(self) -> None:
        self.session._set(self.before, self.ids)


class EditSession(QObject):
    """Owns the catalog being audited and its undo stack."""

    changed = Signal(list)  # ids of the assets touched ([] when the whole catalog changed)

    def __init__(self, catalog: Catalog, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.undo_stack = QUndoStack(self)

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
