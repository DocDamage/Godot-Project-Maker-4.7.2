"""The ``rpggen analyze`` command: run the analysis pipeline on a pack and print the catalog."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rpggen import jsonio
from rpggen.core import accuracy, archive, cache, catalog, inventory
from rpggen.errors import RpgGenError


def analyze_pack(source: Path) -> tuple[catalog.Catalog, list[Any]]:
    """Open, inventory and assemble one pack; returns the catalog and its issues."""
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened)
    cat, issues, _generated = catalog.assemble([(opened, inv)], None, [])
    return cat, list(issues)


def format_table(cat: catalog.Catalog) -> str:
    rows = [("path", "usage", "role", "grid/frame", "conf", "status")]
    for asset in sorted(cat.assets, key=lambda a: (a.id.casefold(), a.id)):
        eff = catalog.effective(asset)
        grid = eff.get("grid") or {}
        if grid:
            geometry = "x".join(map(str, grid["cell"]))
            if any(grid.get("margin", [0, 0])) or any(grid.get("separation", [0, 0])):
                geometry += f" m{grid['margin'][0]} s{grid['separation'][0]}"
        elif eff.get("frame"):
            geometry = "frame " + "x".join(map(str, eff["frame"]))
        else:
            geometry = "-"
        suffix = "#" + asset.id.split("#", 1)[1] if "#" in asset.id else ""
        rows.append(
            (
                asset.path.split("/", 3)[-1] + suffix,
                str(eff.get("usage", "-")),
                str(eff.get("role", "-")),
                geometry,
                f"{asset.confidence:.2f}",
                asset.status,
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows
    )


def _print_miss(miss: dict[str, Any]) -> None:
    print(f"  miss: {miss['path']} {miss['field']}: want {miss['expected']} got {miss['actual']}")


def _expected_for(source: Path) -> Path:
    return source.with_name(source.stem + ".expected.json")


def run_corpus(corpus: Path) -> tuple[dict[str, Any], list[str]]:
    reports: dict[str, dict[str, Any]] = {}
    for source in sorted(p for p in corpus.iterdir() if p.is_dir() or p.suffix.lower() == ".zip"):
        expected_file = _expected_for(source)
        if not expected_file.exists():
            continue
        cat, _ = analyze_pack(source)
        reports[source.stem] = accuracy.score(cat, jsonio.read(expected_file))
    merged = accuracy.merge_reports(list(reports.values()))
    failures = accuracy.check_thresholds(merged)
    result = {
        "packs": {name: reports[name] for name in sorted(reports)},
        "overall": merged,
        "groups": accuracy.grouped(merged),
        "thresholds": accuracy.THRESHOLDS,
        "passed": not failures,
        "failures": failures,
    }
    return result, failures


def main(args: argparse.Namespace) -> int:
    if args.no_cache:
        cache.clear()
    try:
        if args.corpus:
            report, failures = run_corpus(Path(args.corpus))
            out = Path(args.report or "accuracy_report.json")
            jsonio.write(out, report)
            for group, value in report["groups"].items():
                shown = "n/a" if value is None else f"{value:.3f}"
                print(f"{group:6} {shown}  (threshold {accuracy.THRESHOLDS[group]:.2f})")
            for miss in report["overall"]["misses"]:
                _print_miss(miss)
            print(f"report written to {out}")
            for failure in failures:
                print(f"FAIL: {failure}")
            return 1 if failures else 0
        if not args.pack:
            print("rpggen analyze: give a pack or --corpus DIR")
            return 2
        cat, issues = analyze_pack(Path(args.pack))
        print(format_table(cat))
        for issue in issues:
            print(f"{issue.severity.value.upper():7} {issue.code}: {issue.message}")
        if args.out:
            catalog.save(cat, Path(args.out))
            print(f"catalog written to {args.out}")
        if args.expected:
            report = accuracy.score(cat, jsonio.read(Path(args.expected)))
            for group, value in accuracy.grouped(report).items():
                print(f"{group:6} {'n/a' if value is None else f'{value:.3f}'}")
            print(f"overall {report['overall']['correct']}/{report['overall']['total']}")
            for miss in report["misses"]:
                _print_miss(miss)
        return 0
    except RpgGenError as exc:
        print(f"{exc.issue.code}: {exc.issue.message}\n    fix: {exc.issue.fix}")
        return 1


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pack", nargs="?", type=Path, help="pack folder or archive")
    parser.add_argument("--out", type=Path, help="write the catalog JSON here")
    parser.add_argument("--expected", type=Path, help="expected.json to score against")
    parser.add_argument("--corpus", type=Path, help="score every pack with an .expected.json")
    parser.add_argument("--report", type=Path, help="corpus report path (accuracy_report.json)")
    parser.add_argument("--no-cache", action="store_true", help="clear the analysis cache first")


__all__ = ["add_arguments", "analyze_pack", "format_table", "main", "run_corpus"]
