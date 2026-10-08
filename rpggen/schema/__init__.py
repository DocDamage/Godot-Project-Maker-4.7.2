from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from rpggen.errors import RpgGenError

KINDS = ("config", "inventory", "catalog", "ledger", "profile", "results", "cli")


@cache
def _validator(kind: str) -> Draft202012Validator:
    if kind not in KINDS:
        raise KeyError(f"unknown schema kind: {kind}")
    text = (resources.files(__package__) / f"{kind}.schema.json").read_text(encoding="utf-8")
    return Draft202012Validator(json.loads(text))


def validate(kind: str, obj: Any) -> None:
    """Validate ``obj`` against the named schema; raise on the first error (by JSON path)."""
    errors = sorted(_validator(kind).iter_errors(obj), key=lambda e: [str(p) for p in e.path])
    if not errors:
        return
    err = errors[0]
    where = "/" + "/".join(str(p) for p in err.absolute_path)
    raise RpgGenError("CAT-002", file=kind, reason=f"{where}: {err.message}")


def errors(kind: str, obj: Any) -> list[tuple[str, str]]:
    """Every schema violation of ``obj`` as ``(json path, message)``, sorted by path."""
    found = sorted(_validator(kind).iter_errors(obj), key=lambda e: [str(p) for p in e.path])
    return [("/" + "/".join(str(p) for p in e.absolute_path), e.message) for e in found]
