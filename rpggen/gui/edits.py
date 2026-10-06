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
