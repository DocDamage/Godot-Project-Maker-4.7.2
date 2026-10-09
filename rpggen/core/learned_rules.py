"""Rules learned from the user's corrections in the audit (T12.59).

When the user sets a role, usage or collision on assets, every folder token and name token of
those files becomes evidence for "files with this token get this value": a rule
``{pattern -> facet value, hits, misses}``. Setting a different value on a file the pattern
matches is a miss for the old value. A rule applies once it has ``MIN_HITS`` hits and a hit rate
of at least ``MIN_RATE``; the learned adapter (``adapters/learned.py``) then proposes its value
for new packs, with a confidence equal to the hit rate capped at ``CAP`` so that the asset stays
"Auto-detected" and is still reviewed.

The rules live in ``learned_rules.json`` in rpggen's data folder. They are never uploaded and are
never part of a project. The wizard's analysis passes them to the catalog explicitly; the CLI,
the goldens and the tests run without them unless they pass some.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rpggen import jsonio, paths
from rpggen.errors import RpgGenError

log = logging.getLogger(__name__)

FILE_NAME = "learned_rules.json"
LEARNABLE = ("role", "usage", "collision")
MIN_HITS = 2
MIN_RATE = 0.6
CAP = 0.85  # below the confirmed threshold: a learned value is still reviewed
MAX_RULES = 500
MIN_TOKEN = 3
# tokens every pack has: they say nothing about one file
STOP_TOKENS = frozenset(
    {"assets", "asset", "pack", "packs", "png", "free", "sprites", "sprite", "graphics", "art",
     "images", "image", "img", "gfx", "pixel", "files", "res", "resources", "the", "and", "new",
     "final", "copy", "version", "export", "exports", "game", "data"}
)  # fmt: skip


@dataclass
class LearnedRule:
    kind: str  # "folder" or "name": where the token is found
    token: str
    facet: str  # role, usage or collision
    value: Any
    hits: int = 0
    misses: int = 0
    enabled: bool = True
    updated: str = ""  # ISO date of the last change

    @property
    def id(self) -> str:
        text = json.dumps([self.kind, self.token, self.facet, self.value], sort_keys=True)
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]

    @property
    def rate(self) -> float:
        seen = self.hits + self.misses
        return self.hits / seen if seen else 0.0

    @property
    def active(self) -> bool:
        return self.enabled and self.hits >= MIN_HITS and self.rate >= MIN_RATE

    @property
    def confidence(self) -> float:
        return round(min(CAP, self.rate), 6)

    def describe(self) -> str:
        where = "folder" if self.kind == "folder" else "file name"
        value = self.value
        if not isinstance(value, str):
            value = json.dumps(value, sort_keys=True)
        return f'{where} "{self.token}" -> {self.facet} {value}'

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "token": self.token,
            "facet": self.facet,
            "value": copy.deepcopy(self.value),
            "hits": self.hits,
            "misses": self.misses,
            "enabled": self.enabled,
            "updated": self.updated,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> LearnedRule:
        return cls(
            str(d["kind"]),
            str(d["token"]),
            str(d["facet"]),
            copy.deepcopy(d["value"]),
            int(d.get("hits", 0)),
            int(d.get("misses", 0)),
            bool(d.get("enabled", True)),
            str(d.get("updated", "")),
        )


@dataclass
class Edit:
    """One correction: the pack-relative path, the facet and the value the user set."""

    path: str
    facet: str
    value: Any


@dataclass
class RuleBook:
    rules: list[LearnedRule] = field(default_factory=list)

    def find(self, kind: str, token: str, facet: str, value: Any) -> LearnedRule | None:
        for rule in self.rules:
            if (rule.kind, rule.token, rule.facet, rule.value) == (kind, token, facet, value):
                return rule
        return None

    def by_id(self, rule_id: str) -> LearnedRule | None:
        return next((r for r in self.rules if r.id == rule_id), None)

    def to_json(self) -> dict[str, Any]:
        return {"version": 1, "rules": [r.to_json() for r in self.rules]}

    @classmethod
    def from_json(cls, data: Any) -> RuleBook:
        if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
            return cls()
        rules: list[LearnedRule] = []
        for item in data["rules"]:
            try:
                rule = LearnedRule.from_json(item)
            except (KeyError, TypeError, ValueError):
                continue
            if rule.kind in ("folder", "name") and rule.facet in LEARNABLE:
                rules.append(rule)
        return cls(rules)


def store_path() -> Path:
    return paths.data_dir() / FILE_NAME


def load(path: Path | None = None) -> RuleBook:
    """The saved rules; none when the file is missing or unreadable."""
    path = path or store_path()
    if not path.is_file():
        return RuleBook()
    try:
        return RuleBook.from_json(jsonio.read(path))
    except (OSError, ValueError, RpgGenError):  # unreadable or not JSON
        log.warning("learned rules: %s cannot be read; starting without them", path)
        return RuleBook()


def save(book: RuleBook, path: Path | None = None) -> None:
    path = path or store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonio.write(path, book.to_json())


def pack_relative(asset_path: str) -> str:
    """``assets/packs/<pack>/a/b.png`` -> ``a/b.png`` (other paths stay as they are)."""
    parts = asset_path.split("/", 3)
    return parts[3] if len(parts) == 4 and parts[:2] == ["assets", "packs"] else asset_path


def patterns(path: str) -> list[tuple[str, str]]:
    """The (kind, token) pairs of a pack-relative path that a rule can key on."""
    from rpggen.core import classifier

    folders, names = classifier.tokens(path)
    out: list[tuple[str, str]] = []
    for kind, tokens in (("folder", folders), ("name", names)):
        for token in dict.fromkeys(tokens):
            if len(token) >= MIN_TOKEN and token.isalpha() and token not in STOP_TOKENS:
                out.append((kind, token))
    return out


def learn(book: RuleBook, edits: Iterable[Edit], today: str | None = None, weight: int = 1) -> int:
    """Add the evidence of ``edits`` to ``book``; returns how many rules changed. Every pattern
    of an edited file is a hit for the value set; a rule of the same pattern and facet with
    another value gets a miss. ``weight=-1`` takes the evidence back (an undone edit); a rule
    left with no evidence is dropped."""
    today = today or datetime.now(UTC).date().isoformat()
    changed: set[int] = set()
    for edit in edits:
        if edit.facet not in LEARNABLE:
            continue
        for kind, token in patterns(edit.path):
            rule = book.find(kind, token, edit.facet, edit.value)
            if rule is None:
                if weight < 0:
                    continue
                rule = LearnedRule(kind, token, edit.facet, copy.deepcopy(edit.value))
                book.rules.append(rule)
            rule.hits = max(0, rule.hits + weight)
            rule.updated = today
            changed.add(id(rule))
            for other in book.rules:
                if (
                    other is not rule
                    and (other.kind, other.token, other.facet) == (kind, token, edit.facet)
                    and other.value != edit.value
                ):
                    other.misses = max(0, other.misses + weight)
                    other.updated = today
                    changed.add(id(other))
    book.rules = [r for r in book.rules if r.hits or r.misses or not r.enabled]
    _prune(book)
    return len(changed)


_cache: dict[str, Any] = {}


def cached(path: Path | None = None) -> RuleBook:
    """The saved rules, read again only when the file changed (the audit's "Why" line asks
    for them on every selection)."""
    path = path or store_path()
    try:
        stamp = path.stat().st_mtime_ns if path.is_file() else None
    except OSError:
        stamp = None
    if _cache.get("key") != (str(path), stamp):
        _cache["key"] = (str(path), stamp)
        _cache["book"] = load(path)
    book: RuleBook = _cache["book"]
    return book


def times_learned(rules: Iterable[LearnedRule], path: str) -> int:
    """How many earlier fixes back the rules that decide ``path`` (for the "Why" line)."""
    return max((r.hits for r in proposals(rules, path).values()), default=0)


def _prune(book: RuleBook) -> None:
    """Keep at most MAX_RULES: the disabled ones (the user's decision) and the best supported."""
    if len(book.rules) <= MAX_RULES:
        return
    ranked = sorted(book.rules, key=lambda r: (r.enabled, -r.hits, r.misses, r.updated, r.id))
    keep = {id(r) for r in ranked if not r.enabled}
    for rule in sorted(book.rules, key=lambda r: (-r.hits, r.misses, r.id)):
        if len(keep) >= MAX_RULES:
            break
        keep.add(id(rule))
    book.rules = [r for r in book.rules if id(r) in keep]


def proposals(rules: Iterable[LearnedRule], path: str) -> dict[str, LearnedRule]:
    """facet -> the active rule that decides it for ``path`` (the most reliable when several
    match: confidence, then hits, then folder before name, then id)."""
    found = set(patterns(path))
    best: dict[str, LearnedRule] = {}
    for rule in rules:
        if not rule.active or (rule.kind, rule.token) not in found:
            continue
        current = best.get(rule.facet)
        key = (rule.confidence, rule.hits, rule.kind == "folder", rule.id)
        if current is None or key > (
            current.confidence,
            current.hits,
            current.kind == "folder",
            current.id,
        ):
            best[rule.facet] = rule
    return best


def as_folder_rule(rule: LearnedRule, pack_id: str) -> dict[str, Any]:
    """A folder rule (``{pack_id, glob, set}``) with the rule's value. A token becomes a glob on
    the folder or file name that contains it, which can also match a longer word."""
    glob = f"**/*{rule.token}*/**" if rule.kind == "folder" else f"**/*{rule.token}*"
    return {"pack_id": pack_id, "glob": glob, "set": {rule.facet: copy.deepcopy(rule.value)}}
