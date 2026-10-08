"""The wizard's data: one ``WizardState`` edited by the pages, plus session drafts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rpggen import jsonio, paths
from rpggen.core import catalog as catalog_mod
from rpggen.core import config as config_mod
from rpggen.core.archive import OpenedPack
from rpggen.core.inventory import Inventory
from rpggen.core.orchestrator import RunResult

DRAFT_VERSION = 1


@dataclass
class WizardState:
    project_name: str = ""
    target: Path | None = None
    godot_exe: Path | None = None
    pack_sources: list[Path] = field(default_factory=list)
    archetype: str = "turn_based"
    opened_packs: list[OpenedPack] = field(default_factory=list)
    inventories: list[Inventory] = field(default_factory=list)
    catalog: catalog_mod.Catalog | None = None  # assembled, with user overrides applied
    config: config_mod.GeneratorConfig | None = None
    placeholders: set[str] = field(default_factory=set)
    regenerating: bool = False  # target is an existing rpggen project
    analyzed_key: tuple[str, ...] | None = None  # packs the catalog was assembled from
    run_result: RunResult | None = None  # outcome of the last generation (not drafted)
    changed_paths: set[str] = field(default_factory=set)  # pack update: added, resized, missing
    pack_updates: dict[str, str] = field(default_factory=dict)  # new source -> pack_id it updates
    git_commit: bool | None = None  # init a repository / commit; None = the default
    force_while_open: bool = False  # regenerate although a Godot editor seems to be open


def draft_path(target: Path) -> Path:
    """``data_dir()/drafts/<sha256(str(target.resolve()).casefold())[:16]>.json``"""
    key = hashlib.sha256(str(Path(target).resolve()).casefold().encode("utf-8")).hexdigest()
    return paths.data_dir() / "drafts" / f"{key[:16]}.json"


def save_draft(state: WizardState) -> Path | None:
    """Write the user's work (catalog with its overrides, rules, objects, config) to a draft."""
    if state.target is None:
        return None
    data: dict[str, Any] = {
        "draft_version": DRAFT_VERSION,
        "project_name": state.project_name,
        "archetype": state.archetype,
        "pack_sources": [str(p) for p in state.pack_sources],
        "placeholders": sorted(state.placeholders),
        "config": state.config.to_json() if state.config else None,
        "catalog": state.catalog.to_json() if state.catalog else None,
    }
    path = draft_path(state.target)
    jsonio.write(path, data)
    return path


def load_draft(target: Path) -> dict[str, Any] | None:
    """The draft saved for ``target``, or None when there is none or it is unreadable."""
    path = draft_path(target)
    if not path.exists():
        return None
    try:
        data = jsonio.read(path)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("draft_version") != DRAFT_VERSION:
        return None
    return data


def apply_draft(state: WizardState, data: dict[str, Any]) -> catalog_mod.Catalog | None:
    """Copy a draft's settings into ``state``; returns its catalog (``previous`` for assemble)."""
    state.project_name = data.get("project_name", state.project_name)
    state.archetype = data.get("archetype", state.archetype)
    state.placeholders = set(data.get("placeholders", []))
    if data.get("config"):
        state.config = config_mod.GeneratorConfig.from_json(data["config"])
    previous = catalog_mod.Catalog.from_json(data["catalog"]) if data.get("catalog") else None
    return previous


def delete_draft(target: Path) -> None:
    draft_path(target).unlink(missing_ok=True)
