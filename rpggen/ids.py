from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """Lowercase ASCII slug: NFKD, strip combining marks, non-alnum runs -> "_".

    Empty results become "x"; a leading digit gets an "n" prefix.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    out = _NON_ALNUM.sub("_", stripped.lower()).strip("_")
    if not out:
        return "x"
    if out[0].isdigit():
        return "n" + out
    return out


def _strip_extension(rel: str) -> str:
    parts = rel.split("/")
    last = parts[-1]
    dot = last.rfind(".")
    if dot > 0:
        parts[-1] = last[:dot]
    return "/".join(parts)


def asset_id(pack_id: str, rel_path_in_pack: str) -> str:
    """``pack_id`` + "." + dotted slugs of the extension-less relative path."""
    parts = [p for p in _strip_extension(rel_path_in_pack).split("/") if p]
    return pack_id + "." + ".".join(slug(p) for p in parts)


def disambiguate(ids_in_order: list[str]) -> list[str]:
    """Keep the first occurrence of each id; suffix later duplicates with __2, __3, ..."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for ident in ids_in_order:
        count = seen.get(ident, 0) + 1
        seen[ident] = count
        out.append(ident if count == 1 else f"{ident}__{count}")
    return out


PACK_ID_LENGTH = 40  # the longest a pack's id is


def pack_id_from_name(name: str, existing: set[str]) -> str:
    """Slug of the archive/folder stem (max 40 chars), unique against ``existing``."""
    base = slug(PurePosixPath(name.replace("\\", "/")).stem)[:PACK_ID_LENGTH]
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"
