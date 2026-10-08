"""Licences of the packs, read from their licence, credits and readme files (T12.51).

``detect`` finds the licence (CC0, the Creative Commons BY family, OGA-BY, MIT, RPG Maker terms,
or "commercial use" wording), whether the game must credit the pack, and the author and URL
lines. The result goes into the catalog pack; the Audit page can correct it, and the generated
game shows it on its Credits screen.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COMMERCIAL = "commercial"  # a vendor's own licence that allows commercial use
RPG_MAKER = "rpgmaker"  # the RPG Maker terms: the art may only be used with RPG Maker
UNKNOWN = ""

KNOWN_IDS = (
    "CC0-1.0",
    "CC-BY-3.0",
    "CC-BY-4.0",
    "CC-BY-SA-3.0",
    "CC-BY-SA-4.0",
    "CC-BY-NC-4.0",
    "OGA-BY-3.0",
    "MIT",
    COMMERCIAL,
    RPG_MAKER,
)
KEYS = ("license_id", "author", "url", "attribution_required")
MAX_BYTES = 64 * 1024  # a readme longer than this is read in part
TEXT_SUFFIXES = {"", ".txt", ".text", ".md", ".markdown", ".nfo", ".html", ".htm", ".rtf"}


@dataclass(frozen=True)
class PackLicense:
    license_id: str = UNKNOWN
    author: str = ""
    url: str = ""
    attribution_required: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "license_id": self.license_id,
            "author": self.author,
            "url": self.url,
            "attribution_required": self.attribution_required,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any] | None) -> PackLicense:
        d = d or {}
        return cls(
            str(d.get("license_id", "")),
            str(d.get("author", "")),
            str(d.get("url", "")),
            bool(d.get("attribution_required", False)),
        )


@dataclass
class _Found:
    license_id: str = UNKNOWN
    attribution: bool | None = None  # what the wording says, None when it says nothing
    authors: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- names


def label(license_id: str) -> str:
    """How the licence is named on the Audit page and the credits: "CC BY-SA 4.0"."""
    if license_id == UNKNOWN:
        return "Unknown licence"
    if license_id == COMMERCIAL:
        return "Commercial licence"
    if license_id == RPG_MAKER:
        return "RPG Maker terms"
    head, _, version = license_id.rpartition("-")
    if not re.fullmatch(r"\d\.\d", version):
        return license_id
    if head.startswith("CC-"):
        return f"CC {head[3:]} {version}"
    return f"{head} {version}"


def license_url(license_id: str) -> str:
    """The licence's own page ("" when it has none)."""
    m = re.fullmatch(r"CC-((?:BY)(?:-NC)?(?:-SA|-ND)?)-(\d\.\d)", license_id)
    if m:
        return f"https://creativecommons.org/licenses/{m.group(1).lower()}/{m.group(2)}/"
    if license_id == "CC0-1.0":
        return "https://creativecommons.org/publicdomain/zero/1.0/"
    if license_id.startswith("OGA-BY"):
        return "https://opengameart.org/content/oga-by-30-faq"
    if license_id == "MIT":
        return "https://opensource.org/license/mit"
    return ""


def requires_attribution(license_id: str) -> bool | None:
    """Whether the licence itself asks for credit; None when the wording decides."""
    if license_id.startswith(("CC-BY", "OGA-BY")) or license_id == "MIT":
        return True
    if license_id in ("CC0-1.0", RPG_MAKER):
        return False
    return None


# --------------------------------------------------------------------------- reading


def read_text(path: Path) -> str:
    """The text of a licence file (the first ``MAX_BYTES``; HTML and RTF markup removed), ""
    for a file that is not text."""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES)
    except OSError:
        return ""
    if b"\x00" in raw[:1024]:
        return ""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    elif suffix == ".rtf":
        text = re.sub(r"\\par[d]?\b", "\n", text)
        text = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", text)
    return text


def _priority(name: str) -> int:
    """Licence files first, then credits and attribution files, then readmes."""
    stem = Path(name).name.casefold()
    if stem.startswith(("license", "licence", "copying")):
        return 0
    if stem.startswith(("credits", "attribution")):
        return 1
    return 2


# --------------------------------------------------------------------------- detection

_VERSION = r"(?:[ \-_v]*(\d\.\d))?"
_CC_SHORT = re.compile(r"\bcc[ \-_]?by((?:[ \-_](?:nc|nd|sa)\b)*)" + _VERSION, re.I)
_CC_URL = re.compile(r"creativecommons\.org/licenses/(by(?:-nc)?(?:-sa|-nd)?)/(\d\.\d)", re.I)
_CC_LONG = re.compile(
    r"creative\s+commons\s+attribution((?:[\s\-]+(?:non-?commercial|share-?alike|no-?deriv\w*))*)"
    r"(?:\s+(?:license\s+)?(?:v(?:ersion)?\s*)?(\d\.\d))?",
    re.I,
)
_CC0 = re.compile(
    r"\bcc[ \-]?0\b|\bcc[ \-]?zero\b|publicdomain/zero|creative\s+commons\s+zero|"
    r"public\s+domain\s+dedication",
    re.I,
)
_OGA = re.compile(r"\boga[ \-_]?by" + _VERSION, re.I)
_MIT = re.compile(
    r"\bmit\s+licen[cs]e\b|permission\s+is\s+hereby\s+granted,\s+free\s+of\s+charge", re.I
)
_RPG_MAKER = re.compile(
    r"(?:only|exclusively|solely|licensed)\b.{0,80}\brpg\s?maker\b|"
    r"\brpg\s?maker\b.{0,80}\b(?:only|terms\s+of\s+(?:use|service)|eula|license\s+agreement)",
    re.I | re.S,
)
_COMMERCIAL = re.compile(
    r"\b(?:can|may|allowed|permitted|free)\b.{0,60}\bcommercial(?:ly)?\b|"
    r"\bcommercial\s+(?:and\s+non-?commercial\s+)?(?:use|projects?|games?|purposes?|products?)\b"
    r".{0,40}\b(?:allowed|permitted|ok|fine)\b",
    re.I | re.S,
)
_NEEDS_CREDIT = re.compile(
    r"\b(?:credit|attribution)\s+(?:is\s+)?(?:required|mandatory|necessary)\b|"
    r"\b(?:must|have\s+to|need\s+to|required\s+to)\s+(?:give\s+)?(?:credit|attribut|be\s+credited|mention)|"
    r"\bplease\s+(?:give\s+)?credit\b|\bcredit\s+(?:me|us|the\s+(?:author|artist))\b",
    re.I,
)
_NO_CREDIT = re.compile(
    r"\b(?:no|without)\s+(?:credit|attribution)\s+(?:is\s+)?(?:required|needed|necessary)\b|"
    r"\b(?:credit|attribution)\s+(?:is\s+)?(?:not\s+required|optional|appreciated\s+but\s+not)",
    re.I,
)
_AUTHOR_LINE = re.compile(
    r"^\s*[*\-#>]*\s*(?:author|authors|artist|artists|creator|creators|created\s+by|made\s+by|"
    r"art\s+by|artwork\s+by|graphics\s+by|drawn\s+by|designed\s+by|credit(?:s)?(?:\s+to)?|"
    r"please\s+credit|attribution|by)\s*[:=\-–]\s*(.+?)\s*$",
    re.I,
)
_BY_LINE = re.compile(
    r"^\s*[*\-#>]*\s*(?:created|made|drawn|designed|art|artwork|graphics|sprites|tiles)\s+by\s+"
    r"(.+?)\s*$",
    re.I,
)
_CREDIT_PHRASE = re.compile(
    r"(?i:\b(?:please\s+)?(?:give\s+)?credit(?:\s+(?:to|goes\s+to))?)\s+"
    r"(?!(?i:me|us|is|the\s+author)\b)"
    r"([A-Z0-9][^.!?\n]{0,60})",
)
_COPYRIGHT_LINE = re.compile(
    r"^\s*[*\-#>]*\s*copyright\s*(?:\(c\)|©)?\s*(?:\d{4}(?:\s*[-–,]\s*\d{4})*\s*,?)\s*(?:by\s+)?"
    r"(.+?)\s*$",
    re.I,
)
_URL_LINE = re.compile(
    r"^\s*[*\-#>]*\s*(?:url|website|web|web\s*site|link|homepage|home\s*page|source|site|page|"
    r"itch(?:\.io)?|more\s+at|download(?:ed)?(?:\s+from)?)\s*[:=\-–]\s*<?(https?://\S+)",
    re.I,
)
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
_LICENCE_HOSTS = ("creativecommons.org", "opensource.org", "gnu.org", "spdx.org", "choosealicense")


def _cc_id(modifiers: str, version: str | None) -> str:
    """The id ("CC-BY-NC-SA-4.0") from the words after "BY" (short or spelled out)."""
    words = modifiers.lower()
    mods = ""
    if re.search(r"\bnc\b|non-?\s?commercial", words):
        mods += "-NC"
    if re.search(r"\bsa\b|share-?\s?alike", words):
        mods += "-SA"
    elif re.search(r"\bnd\b|no-?\s?deriv", words):
        mods += "-ND"
    return f"CC-BY{mods}-{version or '4.0'}"


def _licence_of(text: str) -> str:
    if m := _OGA.search(text):
        return f"OGA-BY-{m.group(1) or '3.0'}"
    if m := _CC_URL.search(text):
        return _cc_id(m.group(1)[2:], m.group(2))
    if m := _CC_LONG.search(text):
        return _cc_id(m.group(1), m.group(2))
    if m := _CC_SHORT.search(text):
        return _cc_id(m.group(1), m.group(2))
    if _CC0.search(text):
        return "CC0-1.0"
    if _MIT.search(text):
        return "MIT"
    if _RPG_MAKER.search(text):
        return RPG_MAKER
    if _COMMERCIAL.search(text):
        return COMMERCIAL
    return UNKNOWN


def _clean_author(raw: str) -> str:
    text = _URL.sub("", raw)
    text = re.sub(r"\s*[(\[<].*$", "", text)  # "(website)", "[link]", "<mail>" and the rest
    text = re.split(
        r"\s+(?:-|–|—|\|)\s+|\.\s+|\ball rights reserved\b|"
        r"\s+(?:in|on|when|if|for)\s+(?:your|the|any|you)\b",  # "Fox Studio in your game"
        text,
        flags=re.I,
    )[0]
    text = text.strip(" \t*_.,;:-–—\"'`")
    if not text or len(text) > 80 or not re.search(r"\w", text):
        return ""
    if re.fullmatch(r"(?i)the\s+author\(?s?\)?|unknown|n/?a|none|-+", text):
        return ""
    return text


def _scan(text: str) -> _Found:
    found = _Found(license_id=_licence_of(text))
    if _NO_CREDIT.search(text):
        found.attribution = False
    elif _NEEDS_CREDIT.search(text):
        found.attribution = True
    for line in text.splitlines():
        for pattern in (_AUTHOR_LINE, _BY_LINE, _COPYRIGHT_LINE):
            m = pattern.match(line)
            if m and (author := _clean_author(m.group(1))):
                found.authors.append(author)
                break
        else:
            m = _CREDIT_PHRASE.search(line)
            if m and (author := _clean_author(m.group(1))):
                found.authors.append(author)
        if m := _URL_LINE.match(line):
            found.urls.append(m.group(1).rstrip(".,;:)>"))  # labelled URLs come first
    for url in _URL.findall(text):
        url = url.rstrip(".,;:")
        if not any(host in url.casefold() for host in _LICENCE_HOSTS) and url not in found.urls:
            found.urls.append(url)
    return found


def detect(files: list[tuple[str, str]]) -> PackLicense:
    """The licence of a pack from its licence files, given as (file name, text) pairs."""
    ordered = sorted(files, key=lambda pair: (_priority(pair[0]), pair[0].casefold()))
    license_id = UNKNOWN
    wording: bool | None = None
    author = url = ""
    for _name, text in ordered:
        found = _scan(text)
        license_id = license_id or found.license_id
        if wording is None:
            wording = found.attribution
        author = author or next(iter(found.authors), "")
        url = url or next(iter(found.urls), "")
    required = requires_attribution(license_id)  # a licence with a rule wins over the wording
    return PackLicense(license_id, author, url, bool(wording) if required is None else required)


def detect_files(root: Path, rel_paths: list[str]) -> PackLicense:
    """``detect`` on the licence files ``rel_paths`` of the pack folder ``root``."""
    return detect([(rel, read_text(root / rel)) for rel in rel_paths])


def effective(detected: dict[str, Any] | None, overrides: dict[str, Any] | None) -> PackLicense:
    """The licence the user sees: the detected one with the Audit page's corrections. A licence
    chosen by the user brings its own "credit required" unless that was set too."""
    out = {**PackLicense.from_json(detected).to_json(), **(overrides or {})}
    if overrides and "license_id" in overrides and "attribution_required" not in overrides:
        required = requires_attribution(str(overrides["license_id"]))
        if required is not None:
            out["attribution_required"] = required
    return PackLicense.from_json(out)
