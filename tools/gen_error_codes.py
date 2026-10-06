"""Generate error-code tables from the spec's 03_ERROR_CODES.md.

Usage: python tools/gen_error_codes.py [path/to/03_ERROR_CODES.md]

Writes (relative to the repository root):
  rpggen/errors_table.py
  godot_templates/builder/lib/error_codes.gd
  docs/errors.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = REPO_ROOT / "docs" / "spec" / "03_ERROR_CODES.md"

ROW = re.compile(r"^\|\s*([A-Z]+-\d{3})\s*\|\s*([EWI])\s*\|(.*)\|\s*$")
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
SEVERITY = {"E": "error", "W": "warning", "I": "info"}
AREA_TITLES = {
    "ENV": "Environment",
    "ARCH": "Archives",
    "ASSET": "Assets",
    "ADAPT": "Adapters",
    "CAT": "Catalog",
    "TILE": "Tiles",
    "ANIM": "Animation",
    "BUILD": "Build",
    "VAL": "Validation",
    "SMOKE": "Smoke test",
    "REGEN": "Regeneration",
    "GUI": "GUI",
}


def parse(text: str) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        code, sev, rest = m.group(1), m.group(2), m.group(3)
        # message and fix are separated by the last " | " (templates contain no pipes)
        parts = [p.strip() for p in rest.split(" | ")]
        if len(parts) != 2:
            raise SystemExit(f"{code}: expected message and fix columns, got {parts!r}")
        message, fix = parts
        for field in (message, fix):
            for name in PLACEHOLDER.findall(field):
                if not name.isidentifier():
                    raise SystemExit(f"{code}: placeholder {{{name}}} is not a valid identifier")
        if code in seen:
            raise SystemExit(f"duplicate code {code}")
        seen.add(code)
        rows.append((code, SEVERITY[sev], message, fix))
    if not rows:
        raise SystemExit("no error-code rows found")
    return rows


def _py_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_py(rows: list[tuple[str, str, str, str]]) -> str:
    out = [
        "# GENERATED — do not edit. Source: docs/spec/03_ERROR_CODES.md",
        "# Regenerate with: python tools/gen_error_codes.py",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True, slots=True)",
        "class CodeInfo:",
        "    code: str",
        "    severity: str  # error | warning | info",
        "    message: str",
        "    fix: str",
        "",
        "",
        "CODES: dict[str, CodeInfo] = {",
    ]
    for code, sev, message, fix in rows:
        out.append(
            f"    {_py_str(code)}: CodeInfo({_py_str(code)}, {_py_str(sev)}, "
            f"{_py_str(message)}, {_py_str(fix)}),"
        )
    out.append("}")
    return "\n".join(out) + "\n"


def render_gd(rows: list[tuple[str, str, str, str]]) -> str:
    out = [
        "# GENERATED — do not edit. Source: docs/spec/03_ERROR_CODES.md",
        "# Regenerate with: python tools/gen_error_codes.py",
        "extends RefCounted",
        "",
        "const CODES := {",
    ]
    for code, sev, message, fix in rows:
        out.append(
            f'\t"{code}": {{"severity": "{sev}", "message": {_py_str(message)}, '
            f'"fix": {_py_str(fix)}}},'
        )
    out.append("}")
    return "\n".join(out) + "\n"


def render_md(rows: list[tuple[str, str, str, str]]) -> str:
    out = [
        "# Error codes",
        "",
        "<!-- GENERATED from docs/spec/03_ERROR_CODES.md by tools/gen_error_codes.py -->",
        "",
    ]
    areas: dict[str, list[tuple[str, str, str, str]]] = {}
    for row in rows:
        areas.setdefault(row[0].split("-")[0], []).append(row)
    for area, items in areas.items():
        out.append(f"## {AREA_TITLES.get(area, area)} ({area})")
        out.append("")
        out.append("| Code | Severity | Message | Recommended fix |")
        out.append("|------|----------|---------|-----------------|")
        for code, sev, message, fix in items:
            out.append(f"| {code} | {sev} | {message} | {fix} |")
        out.append("")
    return "\n".join(out)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    spec = Path(args[0]) if args else DEFAULT_SPEC
    rows = parse(spec.read_text(encoding="utf-8"))
    _write(REPO_ROOT / "rpggen" / "errors_table.py", render_py(rows))
    _write(REPO_ROOT / "godot_templates" / "builder" / "lib" / "error_codes.gd", render_gd(rows))
    _write(REPO_ROOT / "docs" / "errors.md", render_md(rows))
    print(f"generated {len(rows)} error codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
