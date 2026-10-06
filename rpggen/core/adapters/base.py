from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from rpggen.core.inventory import Inventory
from rpggen.errors import Issue


@dataclass
class AssetFragment:
    path: str  # posix path inside the pack
    facets: dict[str, Any]  # partial Facets (02_SCHEMAS §4.4)
    confidence: float
    claim: Literal["full", "partial"]  # full: classifier must not change usage/grid/anims
    # Non-empty for fragments that become their own asset ("c3", "f0"): id suffix "#c3".
    variant: str = ""


@dataclass
class AdapterResult:
    adapter: str
    assets: list[AssetFragment] = field(default_factory=list)
    objects: list[dict[str, Any]] = field(default_factory=list)  # SheetObject dicts, "sheet_path"
    tilesets: list[dict[str, Any]] = field(default_factory=list)  # TileSetDef dicts, no source_id
    pack_warnings: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    # Pack paths merged into another asset (no asset of their own); they count as claimed.
    consumed: list[str] = field(default_factory=list)
    # Files the adapter generated: project-relative target path -> absolute source file.
    generated: dict[str, str] = field(default_factory=dict)
    # FolderRule dicts and the matched profile id: only the profile adapter sets them.
    folder_rules: list[dict[str, Any]] = field(default_factory=list)
    profile_id: str | None = None


@dataclass
class AdapterContext:
    """Shared state of one pack's adapter run."""

    pack_id: str = ""
    # Paths claimed ("full") by earlier adapters; later adapters must skip them.
    claimed: set[str] = field(default_factory=set)
    # Image analysis by pack path (cached); None when analysis is unavailable (unit tests).
    analyze: Callable[[str], dict[str, Any]] | None = None
    # Results of the adapters that already ran (used to build the generic grid prior).
    results: list[AdapterResult] = field(default_factory=list)
    # Where generated helper images (GIF strips) are written; None disables them.
    work_dir: Path | None = None


class Adapter(Protocol):
    name: str
    priority: int  # lower runs first

    def match(self, inv: Inventory, root: Path) -> float: ...  # 0..1

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult: ...
