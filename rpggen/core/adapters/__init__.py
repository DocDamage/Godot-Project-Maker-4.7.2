from __future__ import annotations

import logging
from pathlib import Path

from rpggen.core.adapters.base import (
    Adapter,
    AdapterContext,
    AdapterResult,
    AssetFragment,
)
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

__all__ = [
    "Adapter",
    "AdapterContext",
    "AdapterResult",
    "AssetFragment",
    "MATCH_THRESHOLD",
    "get_adapters",
    "register_defaults",
    "register",
    "run_adapters",
]

log = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.5
_ADAPTERS: list[Adapter] = []


def register(adapter: Adapter) -> None:
    """Add an adapter to the registry (replacing one with the same name)."""
    _ADAPTERS[:] = [a for a in _ADAPTERS if a.name != adapter.name]
    _ADAPTERS.append(adapter)


def get_adapters() -> list[Adapter]:
    """Registered adapters ordered by priority (ties: name)."""
    return sorted(_ADAPTERS, key=lambda a: (a.priority, a.name))


def run_adapters(
    inv: Inventory,
    root: Path,
    ctx: AdapterContext,
    adapters: list[Adapter] | None = None,
) -> list[AdapterResult]:
    """Run every adapter whose match score is >= 0.5, in priority order.

    Paths claimed ("full") by an adapter are skipped by later ones: fragments a later adapter
    returns for such paths are dropped. An adapter that raises produces an ADAPT-001 warning and
    the remaining adapters still run. This is the only place a broad ``except Exception`` is
    allowed.
    """
    results: list[AdapterResult] = []
    for adapter in (
        sorted(adapters, key=lambda a: (a.priority, a.name))
        if adapters is not None
        else get_adapters()
    ):
        try:
            if adapter.match(inv, root) < MATCH_THRESHOLD:
                continue
            already_claimed = set(ctx.claimed)
            result = adapter.extract(inv, root, ctx)
            result.assets = [f for f in result.assets if f.path not in already_claimed]
        except Exception as exc:  # noqa: BLE001 - adapter failures must not stop generation
            log.debug("adapter %s failed", adapter.name, exc_info=True)
            issues = IssueList()
            issues.add("ADAPT-001", adapter=adapter.name, file=f"({inv.pack_id})", reason=str(exc))
            results.append(AdapterResult(adapter.name, issues=list(issues)))
            ctx.results.append(results[-1])
            continue
        for fragment in result.assets:
            if fragment.claim == "full":
                ctx.claimed.add(fragment.path)
        ctx.claimed.update(result.consumed)
        results.append(result)
        ctx.results.append(result)
    return results


def register_defaults() -> None:
    """Register the built-in adapters (idempotent)."""
    from rpggen.core.adapters.aseprite import AsepriteAdapter
    from rpggen.core.adapters.generic_grid import GenericGridAdapter
    from rpggen.core.adapters.ldtk import LdtkAdapter
    from rpggen.core.adapters.lpc import LpcAdapter
    from rpggen.core.adapters.rpgmaker import RpgMakerAdapter
    from rpggen.core.adapters.strips import StripsAdapter
    from rpggen.core.adapters.tiled import TiledAdapter

    for adapter in (
        TiledAdapter(),
        AsepriteAdapter(),
        LdtkAdapter(),
        RpgMakerAdapter(),
        LpcAdapter(),
        StripsAdapter(),
        GenericGridAdapter(),
    ):
        register(adapter)
