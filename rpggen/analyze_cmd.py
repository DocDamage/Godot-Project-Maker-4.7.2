"""The ``rpggen analyze`` command: run the analysis pipeline on a pack and print the catalog."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rpggen import cli_support, jsonio
from rpggen.cli_support import Output
from rpggen.core import accuracy, archive, cache, catalog, inventory
from rpggen.errors import RpgGenError


def analyze_pack(source: Path, use_cache: bool = True) -> tuple[catalog.Catalog, list[Any]]:
    """Open, inventory and assemble one pack; returns the catalog and its issues."""
    opened = archive.open_pack(source, set())
    inv = inventory.build_inventory(opened, use_cache=use_cache)
    cat, issues, _generated = catalog.assemble([(opened, inv)], None, [], use_cache=use_cache)
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


def asset_rows(cat: catalog.Catalog) -> list[dict[str, Any]]:
    """The rows of the table as data (``analyze --json``): what each asset was taken for."""
    rows = []
    for asset in sorted(cat.assets, key=lambda a: (a.id.casefold(), a.id)):
        eff = catalog.effective(asset)
        rows.append(
            {
                "id": asset.id,
                "path": asset.path,
                "usage": eff.get("usage"),
                "role": eff.get("role"),
                "grid": eff.get("grid") or None,
                "frame": eff.get("frame") or None,
                "confidence": round(asset.confidence, 2),
                "status": asset.status,
            }
        )
    return rows


def _miss_line(miss: dict[str, Any]) -> str:
    return f"  miss: {miss['path']} {miss['field']}: want {miss['expected']} got {miss['actual']}"


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


def run_private_corpus(corpus: Path, packs: Path | list[Path]) -> dict[str, Any]:
    """Score every entry of ``corpus`` (``*.corpus.json``) against the pack that matches its
    fingerprint: where the entry says it was found (``source``), if it still is, else among the
    folders and archives in the ``packs`` roots; an entry whose pack is not there is reported as
    missing."""
    entries = {}
    for path in sorted(Path(corpus).glob("*.corpus.json")):
        entry = jsonio.read(path)
        entries[str(entry.get("name") or path.name.removesuffix(".corpus.json"))] = entry
    roots = [packs] if isinstance(packs, Path) else list(packs)
    candidates = [Path(e["source"]) for e in entries.values() if e.get("source")]
    candidates = [p for p in candidates if p.exists()]
    for root in roots:
        candidates += sorted(
            p
            for p in Path(root).iterdir()
            if p.is_dir() or p.suffix.lower() in (".zip", ".7z", ".rar")
        )
    reports: dict[str, dict[str, Any]] = {}
    seen: set[Path] = set()
    for source in candidates:
        if source in seen or len(reports) == len(entries):
            continue
        seen.add(source)
        opened = archive.open_pack(source, set())
        inv = inventory.build_inventory(opened)
        for name, entry in entries.items():
            if name in reports or accuracy.match(entry, inv) < accuracy.MIN_MATCH:
                continue
            cat, _issues, _generated = catalog.assemble([(opened, inv)], None, [])
            reports[name] = accuracy.score_private(cat, entry, inv.pack_id)
    missing = [name for name in entries if name not in reports]
    publishers = {n: str(e.get("publisher", "?")) for n, e in entries.items()}
    return accuracy.private_summary(reports, missing, publishers)


def main(args: argparse.Namespace) -> int:
    out = Output("analyze", getattr(args, "json", False))
    if args.no_cache:
        cache.clear()
    try:
        if args.private_corpus:
            if not args.packs:
                return out.usage("--private-corpus needs --packs ROOT")
            roots = [Path(p) for p in args.packs]
            summary = run_private_corpus(Path(args.private_corpus), roots)
            report = Path(args.report or "private_corpus_report.json")
            jsonio.write(report, summary)
            report.with_suffix(".md").write_text(
                accuracy.private_markdown(summary), encoding="utf-8", newline="\n"
            )
            for name, rep in summary["packs"].items():
                shown = ", ".join(
                    f"{g} {'n/a' if v is None else f'{v:.3f}'}" for g, v in rep["groups"].items()
                )
                out.say(f"{name}: {shown}")
            for name in summary["missing"]:
                out.say(f"not found: {name}")
            out.say(f"report written to {report} and {report.with_suffix('.md')}")
            return out.done(
                cli_support.OK, mode="private_corpus", report=str(report), summary=summary
            )
        if args.corpus:
            report_data, failures = run_corpus(Path(args.corpus))
            report = Path(args.report or "accuracy_report.json")
            jsonio.write(report, report_data)
            for group, value in report_data["groups"].items():
                shown = "n/a" if value is None else f"{value:.3f}"
                out.say(f"{group:6} {shown}  (threshold {accuracy.THRESHOLDS[group]:.2f})")
            for miss in report_data["overall"]["misses"]:
                out.say(_miss_line(miss))
            out.say(f"report written to {report}")
            for failure in failures:
                out.say(f"FAIL: {failure}")
            return out.done(
                cli_support.FAILED if failures else cli_support.OK,
                mode="corpus",
                report=str(report),
                passed=not failures,
                failures=failures,
                groups=report_data["groups"],
                thresholds=report_data["thresholds"],
            )
        if not args.pack:
            return out.usage("give a pack or --corpus DIR")
        cat, issues = analyze_pack(Path(args.pack), use_cache=not args.no_cache)
        out.say(format_table(cat))
        out.issues(issues)
        fields: dict[str, Any] = {
            "mode": "pack",
            "pack": str(args.pack),
            "assets": asset_rows(cat),
            "objects": len(cat.objects),
            "tilesets": len(cat.tilesets),
            "catalog_file": None,
            "issues": [cli_support.issue_json(i) for i in issues],
        }
        if args.out:
            catalog.save(cat, Path(args.out))
            out.say(f"catalog written to {args.out}")
            fields["catalog_file"] = str(args.out)
        if args.expected:
            scored = accuracy.score(cat, jsonio.read(Path(args.expected)))
            groups = accuracy.grouped(scored)
            for group, value in groups.items():
                out.say(f"{group:6} {'n/a' if value is None else f'{value:.3f}'}")
            out.say(f"overall {scored['overall']['correct']}/{scored['overall']['total']}")
            for miss in scored["misses"]:
                out.say(_miss_line(miss))
            fields["accuracy"] = {
                "groups": groups,
                "correct": scored["overall"]["correct"],
                "total": scored["overall"]["total"],
                "misses": scored["misses"],
            }
        return out.done(cli_support.OK, **fields)
    except RpgGenError as exc:
        out.say(f"{exc.issue.code}: {exc.issue.message}\n    fix: {exc.issue.fix}")
        return out.done(
            cli_support.exit_code_for([exc.issue]), issues=[cli_support.issue_json(exc.issue)]
        )


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pack", nargs="?", type=Path, help="pack folder or archive")
    parser.add_argument("--out", type=Path, help="write the catalog JSON here")
    parser.add_argument("--expected", type=Path, help="expected.json to score against")
    parser.add_argument("--corpus", type=Path, help="score every pack with an .expected.json")
    parser.add_argument("--report", type=Path, help="corpus report path (accuracy_report.json)")
    parser.add_argument(
        "--private-corpus",
        type=Path,
        metavar="DIR",
        help="score the packs of --packs against the entries (*.corpus.json) in DIR",
    )
    parser.add_argument(
        "--packs",
        type=Path,
        metavar="ROOT",
        action="append",
        help="a folder of your own packs (may be given more than once)",
    )
    parser.add_argument("--no-cache", action="store_true", help="clear the analysis cache first")


__all__ = ["add_arguments", "analyze_pack", "asset_rows", "format_table", "main", "run_corpus"]
