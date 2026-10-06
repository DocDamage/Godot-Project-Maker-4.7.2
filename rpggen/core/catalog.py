from __future__ import annotations

import copy
from typing import Any

# T1.07 introduces only effective(); T1.10 adds the catalog data classes and I/O.


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Deep merge of ``over`` onto ``base``.

    A ``None`` value in ``over`` deletes the key. Dictionaries merge recursively; every other
    value (including lists) replaces. Mirrors ``catalog_reader.gd: merge``.
    """
    result = copy.deepcopy(base)
    for key, value in over.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            existing = result.get(key)
            result[key] = merge(existing if isinstance(existing, dict) else {}, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def effective(asset: dict[str, Any]) -> dict[str, Any]:
    """Effective facets of an asset: ``detected`` merged with ``overrides``."""
    return merge(asset.get("detected", {}), asset.get("overrides", {}))
