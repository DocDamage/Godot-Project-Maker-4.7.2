from __future__ import annotations

from collections import Counter
from typing import Any

from rpggen.core import catalog as catalog_mod
from rpggen.core.inventory import Inventory

# Minimum accuracy of the synthetic corpus (checked in CI by ``rpggen analyze --corpus``).
THRESHOLDS = {"grid": 0.95, "usage": 0.95, "role": 0.85, "anims": 0.90}
FIELDS = ("usage", "role", "cell", "margin", "separation", "frame", "anims")
GRID_FIELDS = ("cell", "margin", "separation")


def _find_asset(catalog: catalog_mod.Catalog, key: str) -> catalog_mod.Asset | None:
    """Asset for an expected-file key: ``rel/path.png`` or ``rel/path.png#c3`` (variant)."""
    rel, _, variant = key.partition("#")
    for asset in catalog.assets:
        parts = asset.path.split("/", 3)
        in_pack = len(parts) == 4 and parts[0] == "assets" and parts[1] == "packs"
        if (parts[3] if in_pack else asset.path) != rel:
            continue
        has_variant = "#" in asset.id
        if variant and asset.id.endswith("#" + variant):
            return asset
        if not variant and not has_variant:
            return asset
    if variant:
        # a part of a sheet drawn into a picture of its own (T17.30): its path is the picture's,
        # its id the sheet's with the variant
        sheet = _find_asset(catalog, rel)
        if sheet is not None:
            return catalog.asset(f"{sheet.id}#{variant}")
    return None


def _actual(asset: catalog_mod.Asset | None, field: str) -> Any:
    if asset is None:
        return None
    eff = catalog_mod.effective(asset)
    if field in ("usage", "role", "frame"):
        return eff.get(field)
    if field in GRID_FIELDS:
        return (eff.get("grid") or {}).get(field)
    if field == "anims":
        return sorted((eff.get("animations") or {}).keys())
    raise KeyError(field)


def _expected_value(field: str, value: Any) -> Any:
    return sorted(value) if field == "anims" else value


def is_sure(asset: catalog_mod.Asset | None) -> bool:
    """True for a picture the analyzer reads with confidence (T17.34): confirmed, or detected
    at the confidence of Auto-detected or more."""
    if asset is None or asset.status in ("UNUSED", "MISSING", "CONFLICT"):
        return False
    return asset.status == "CONFIRMED" or asset.confidence >= catalog_mod.AUTO_CONFIDENCE


def _sure_row() -> dict[str, int]:
    return {"pictures": 0, "sure": 0, "sure_right": 0, "right": 0}


def sure_numbers(row: dict[str, int]) -> dict[str, float | None]:
    """The share of pictures read as sure, the share of those that are right, and the share
    of all that are right."""
    return {
        "sure_share": row["sure"] / row["pictures"] if row["pictures"] else None,
        "sure_accuracy": row["sure_right"] / row["sure"] if row["sure"] else None,
        "accuracy": row["right"] / row["pictures"] if row["pictures"] else None,
    }


def score(
    catalog: catalog_mod.Catalog,
    expected: dict[str, dict[str, Any]],
    source_keys: dict[str, catalog_mod.Asset] | None = None,
) -> dict[str, Any]:
    """Per-field ``correct/total`` over the paths listed in ``expected`` plus an overall value,
    and per picture whether it was read as sure and was right in every field (``sure``; per
    reader under ``readers`` and picture by picture under ``pictures``: what calibration fits)."""
    counts = {f: [0, 0] for f in FIELDS}
    misses: list[dict[str, Any]] = []
    sure = _sure_row()
    readers: dict[str, dict[str, int]] = {}
    pictures: list[dict[str, Any]] = []
    for key, facts in sorted(expected.items()):
        asset = (source_keys or {}).get(key) or _find_asset(catalog, key)
        right = True
        for field in FIELDS:
            if field not in facts:
                continue
            want = _expected_value(field, facts[field])
            got = _actual(asset, field)
            counts[field][1] += 1
            if got == want:
                counts[field][0] += 1
            else:
                right = False
                misses.append({"path": key, "field": field, "expected": want, "actual": got})
        sure_here = is_sure(asset)
        reader = (asset.detected_by if asset is not None else "") or "none"
        for row in (sure, readers.setdefault(reader, _sure_row())):
            row["pictures"] += 1
            row["sure"] += int(sure_here)
            row["sure_right"] += int(sure_here and right)
            row["right"] += int(right)
        pictures.append(
            {
                "path": key,
                "reader": reader,
                "role": str(_actual(asset, "role") or ""),
                "confidence": round(asset.confidence, 4) if asset is not None else 0.0,
                "sure": sure_here,
                "right": right,
                "fields": [f for f in FIELDS if f in facts],
                "source_sha256": asset.sha256 if asset is not None else "",
            }
        )
    fields = {
        f: {"correct": c, "total": t, "accuracy": (c / t if t else None)}
        for f, (c, t) in counts.items()
    }
    total = sum(t for _, t in counts.values())
    correct = sum(c for c, _ in counts.values())
    return {
        "fields": fields,
        "overall": {
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else None,
        },
        "misses": misses,
        "sure": {**sure, **sure_numbers(sure)},
        "readers": {r: {**row, **sure_numbers(row)} for r, row in sorted(readers.items())},
        "pictures": pictures,
    }


def _merge_sure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = _sure_row()
    for row in rows:
        for k in total:
            total[k] += int(row.get(k, 0))
    return {**total, **sure_numbers(total)}


def merge_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine per-pack reports into one corpus report."""
    counts = {f: [0, 0] for f in FIELDS}
    for rep in reports:
        for f in FIELDS:
            counts[f][0] += rep["fields"][f]["correct"]
            counts[f][1] += rep["fields"][f]["total"]
    fields = {
        f: {"correct": c, "total": t, "accuracy": (c / t if t else None)}
        for f, (c, t) in counts.items()
    }
    total = sum(t for _, t in counts.values())
    correct = sum(c for c, _ in counts.values())
    return {
        "fields": fields,
        "overall": {
            "correct": correct,
            "total": total,
            "accuracy": correct / total if total else None,
        },
        "misses": [m for rep in reports for m in rep["misses"]],
        "sure": _merge_sure([rep["sure"] for rep in reports if "sure" in rep]),
    }


def grouped(report: dict[str, Any]) -> dict[str, float | None]:
    """Accuracy per threshold group (``grid`` combines cell, margin and separation)."""
    out: dict[str, float | None] = {}
    for group, members in (
        ("grid", GRID_FIELDS),
        ("usage", ("usage",)),
        ("role", ("role",)),
        ("anims", ("anims",)),
    ):
        correct = sum(report["fields"][m]["correct"] for m in members)
        total = sum(report["fields"][m]["total"] for m in members)
        out[group] = correct / total if total else None
    return out


def check_thresholds(report: dict[str, Any]) -> list[str]:
    """Messages for every group below its threshold (empty when the corpus passes)."""
    failures = []
    for group, value in grouped(report).items():
        if value is not None and value < THRESHOLDS[group]:
            failures.append(f"{group} accuracy {value:.3f} is below {THRESHOLDS[group]:.2f}")
    return failures


# ----------------------------------------------------------------------- private corpus (T12.26)
#
# Purchased packs cannot be committed, so the real-pack corpus holds no pixels: an entry is the
# fingerprint of a pack (paths, sizes and sha256) and the decisions a person confirmed for it, in
# the exported-profile format. ``rpggen analyze --private-corpus DIR --packs ROOT`` finds each pack
# under ROOT by its fingerprint and scores the detection against the confirmed decisions.

CORPUS_VERSION = 1
MIN_MATCH = 0.8  # the part of an entry's files that must be found, unchanged, in a pack


def fingerprint(inv: Inventory) -> dict[str, dict[str, Any]]:
    """``{pack-relative path: {"sha256": ..., "size": ...}}`` of every file of a pack."""
    return {f.path: {"sha256": f.sha256, "size": f.size} for f in inv.files}


def expected_from_profile(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The decisions of an exported profile as ``score`` wants them: per asset key the usage,
    role, grid, frame size and the names of its animations."""
    expected: dict[str, dict[str, Any]] = {}
    for key, facets in sorted((profile.get("assets") or {}).items()):
        facts: dict[str, Any] = {}
        for name in ("usage", "role", "frame"):
            if name in facets:
                facts[name] = facets[name]
        grid = facets.get("grid") or {}
        for name in GRID_FIELDS:
            if name in grid:
                facts[name] = grid[name]
        if "animations" in facets:
            facts["anims"] = sorted(facets["animations"])
        if facts:
            expected[key] = facts
    return expected


def make_entry(
    name: str,
    inv: Inventory,
    profile: dict[str, Any],
    publisher: str = "",
    source: str = "",
) -> dict[str, Any]:
    """A corpus entry: the fingerprint of the pack and the confirmed profile (no pixels); the
    publisher the report groups packs by, and where the pack was found (tried first), if known."""
    entry: dict[str, Any] = {
        "corpus_version": CORPUS_VERSION,
        "name": name,
        "fingerprint": fingerprint(inv),
        "profile": {k: profile[k] for k in ("assets", "objects", "tilesets") if k in profile},
    }
    if publisher:
        entry["publisher"] = publisher
    if source:
        entry["source"] = source
    return entry


def match(entry: dict[str, Any], inv: Inventory) -> float:
    """The fraction of the entry's files that the pack has, with the same size and hash."""
    wanted = entry.get("fingerprint") or {}
    if not wanted:
        return 0.0
    have = fingerprint(inv)
    same = sum(1 for path, facts in wanted.items() if have.get(path) == facts)
    return same / len(wanted)


def roles_report(
    catalog: catalog_mod.Catalog,
    expected: dict[str, dict[str, Any]],
    source_keys: dict[str, catalog_mod.Asset] | None = None,
) -> dict[str, Any]:
    """Per-role precision and recall and the confusion matrix (expected role -> detected role)
    over the assets that have an expected role."""
    confusion: dict[str, Counter[str]] = {}
    for key, facts in expected.items():
        if "role" not in facts:
            continue
        asset = (source_keys or {}).get(key) or _find_asset(catalog, key)
        detected = _actual(asset, "role") if asset is not None else None
        confusion.setdefault(str(facts["role"]), Counter())[str(detected)] += 1
    detected_totals: Counter[str] = Counter()
    for row in confusion.values():
        detected_totals.update(row)
    roles: dict[str, dict[str, Any]] = {}
    for role in sorted(set(confusion) | set(detected_totals)):
        hits = confusion.get(role, Counter())[role]
        wanted = sum(confusion.get(role, Counter()).values())
        found = detected_totals[role]
        roles[role] = {
            "expected": wanted,
            "detected": found,
            "correct": hits,
            "precision": hits / found if found else None,
            "recall": hits / wanted if wanted else None,
        }
    return {
        "roles": roles,
        "confusion": {e: dict(sorted(row.items())) for e, row in sorted(confusion.items())},
    }


def objects_report(
    catalog: catalog_mod.Catalog, profile: dict[str, Any], pack_id: str
) -> dict[str, Any]:
    """How many of the confirmed objects were found (same sheet and region), how many had the
    right role, and how many extra objects were found on those sheets."""
    from rpggen.core import profiles

    expected = profile.get("objects") or []
    paths_by_id = {a.id: profiles.asset_key(a, pack_id) for a in catalog.assets}
    detected = {
        (paths_by_id[o.sheet], tuple(o.region)): o.role
        for o in catalog.objects
        if o.sheet in paths_by_id
    }
    wanted = {
        (o.get("sheet_path", ""), tuple(o.get("region", []))): o.get("role") for o in expected
    }
    sheets = {sheet for sheet, _region in wanted}
    found = sum(1 for key in wanted if key in detected)
    right_role = sum(1 for key, role in wanted.items() if detected.get(key) == role)
    extra = sum(1 for key in detected if key[0] in sheets and key not in wanted)
    return {
        "expected": len(wanted),
        "found": found,
        "role_correct": right_role,
        "extra": extra,
        "recall": found / len(wanted) if wanted else None,
    }


def score_private(
    catalog: catalog_mod.Catalog,
    entry: dict[str, Any],
    pack_id: str,
    inventory: Inventory | None = None,
) -> dict[str, Any]:
    """The report of one pack of the private corpus."""
    profile = entry.get("profile") or {}
    expected = expected_from_profile(profile)
    from rpggen.core import pack_readings, profiles

    source_keys = (
        {
            profiles.asset_key(a, pack_id, inventory): a
            for a in catalog.assets
            if a.pack_id == pack_id
        }
        if inventory is not None
        else {}
    )
    report = score(catalog, expected, source_keys)
    from rpggen.core import calibration

    pack = next((p for p in catalog.packs if p.pack_id == pack_id), None)
    report["publisher_id"] = calibration.publisher_id(pack.license if pack else None)
    for picture in report["pictures"]:
        picture["publisher"] = report["publisher_id"]
        key = picture["path"]
        # Old `reviewed` values name contact-sheet groups, not independently checked fields.
        # Only explicit per-picture field provenance authorizes a calibration observation.
        reviewed_fields = set((entry.get("reviewed_fields") or {}).get(key, []))
        owner_fields = set((entry.get("owner_reviewed_fields") or {}).get(key, []))
        picture["reviewed_fields"] = sorted((reviewed_fields | owner_fields) & set(FIELDS))
        required = {"usage", "role", "anims"} | (
            set(GRID_FIELDS) if expected[key].get("usage") == "tiles" else {"frame"}
        )
        picture["calibration_eligible"] = (
            required <= set(picture["fields"]) and set(picture["fields"]) <= reviewed_fields
        )
        asset = source_keys.get(key) or _find_asset(catalog, key)
        if asset is None or asset.status in ("CONFIRMED", "UNUSED", "MISSING", "CONFLICT"):
            picture["calibration_eligible"] = False
        if picture["reader"] in calibration.USER_READERS:
            picture["calibration_eligible"] = False
        if asset is not None and (
            asset.overrides
            or asset.rule
            or pack_readings.region_facts(asset.sha256, asset.id.partition("#")[2])
        ):
            picture["calibration_eligible"] = False
        source_key = profiles.asset_key(asset, pack_id, inventory) if asset is not None else key
        expected_hash = (entry.get("fingerprint") or {}).get(source_key.partition("#")[0], {})
        if asset is not None and (
            expected_hash.get("sha256") != asset.sha256
            or not asset.path.startswith(f"assets/packs/{pack_id}/")
        ):
            # A matching pack fingerprint can tolerate a changed individual image. Its old
            # labels cannot train calibration. Generated helpers also need pixel-bound labels
            # before a renderer change can be distinguished from a detector error.
            picture["calibration_eligible"] = False
    report["review_coverage"] = {
        "pictures": len(report["pictures"]),
        "with_reviewed_fields": sum(bool(p["reviewed_fields"]) for p in report["pictures"]),
        "calibration_eligible": sum(p["calibration_eligible"] for p in report["pictures"]),
    }
    report["groups"] = grouped(report)
    report.update(roles_report(catalog, expected, source_keys))
    report["objects"] = objects_report(catalog, profile, pack_id)
    return report


def private_summary(
    reports: dict[str, dict[str, Any]],
    missing: list[str],
    publishers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The report of a whole run: every pack, the merged numbers, the sure share and the
    accuracy of the sure pictures per publisher (``publishers``: pack name -> publisher) and
    the packs not found."""
    scored = list(reports.values())
    merged = merge_reports(scored) if scored else None
    by_publisher: dict[str, list[dict[str, Any]]] = {}
    for name, rep in reports.items():
        if "sure" in rep:
            by_publisher.setdefault((publishers or {}).get(name, "?"), []).append(rep["sure"])
    confusion: dict[str, Counter[str]] = {}
    for rep in scored:
        for expected_role, row in rep["confusion"].items():
            confusion.setdefault(expected_role, Counter()).update(row)
    return {
        "packs": {name: reports[name] for name in sorted(reports)},
        "missing": sorted(missing),
        "overall": merged,
        "groups": grouped(merged) if merged else {},
        "confusion": {e: dict(sorted(row.items())) for e, row in sorted(confusion.items())},
        "thresholds": THRESHOLDS,
        "publishers": {p: _merge_sure(rows) for p, rows in sorted(by_publisher.items())},
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def private_markdown(summary: dict[str, Any]) -> str:
    """The report as Markdown (what the maintainer pastes into docs/coverage.md)."""
    lines = ["# Real-pack accuracy", ""]
    if summary["missing"]:
        lines += ["Not found under the packs folder: " + ", ".join(summary["missing"]), ""]
    lines += [
        "| Pack | Pictures | Sure | Sure right | Grid | Usage | Role | Animations | Objects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, rep in summary["packs"].items():
        groups, objs = rep["groups"], rep["objects"]
        found = f"{objs['found']}/{objs['expected']}" if objs["expected"] else "n/a"
        sure = rep.get("sure") or {}
        lines.append(
            f"| {name} | {sure.get('pictures', '')} | {_pct(sure.get('sure_share'))} | "
            f"{_pct(sure.get('sure_accuracy'))} | {_pct(groups['grid'])} | "
            f"{_pct(groups['usage'])} | {_pct(groups['role'])} | {_pct(groups['anims'])} | "
            f"{found} |"
        )
    if summary["overall"]:
        groups = summary["groups"]
        sure = summary["overall"].get("sure") or {}
        lines.append(
            f"| **all** | {sure.get('pictures', '')} | {_pct(sure.get('sure_share'))} | "
            f"{_pct(sure.get('sure_accuracy'))} | {_pct(groups['grid'])} | "
            f"{_pct(groups['usage'])} | {_pct(groups['role'])} | {_pct(groups['anims'])} | |"
        )
    if summary.get("publishers"):
        lines += [
            "",
            "## Per publisher",
            "",
            "| Publisher | Pictures | Sure | Sure right |",
            "|---|---:|---:|---:|",
        ]
        for publisher, row in summary["publishers"].items():
            lines.append(
                f"| {publisher} | {row['pictures']} | {_pct(row['sure_share'])} | "
                f"{_pct(row['sure_accuracy'])} |"
            )
    totals: dict[str, dict[str, int]] = {}
    for rep in summary["packs"].values():
        for role, row in rep["roles"].items():
            acc = totals.setdefault(role, {"expected": 0, "detected": 0, "correct": 0})
            for k in acc:
                acc[k] += row[k]
    if totals:
        lines += [
            "",
            "## Per role",
            "",
            "| Role | Expected | Detected | Precision | Recall |",
            "|---|---:|---:|---:|---:|",
        ]
        for role, row in sorted(totals.items()):
            precision = row["correct"] / row["detected"] if row["detected"] else None
            recall = row["correct"] / row["expected"] if row["expected"] else None
            lines.append(
                f"| {role} | {row['expected']} | {row['detected']} | "
                f"{_pct(precision)} | {_pct(recall)} |"
            )
    if summary["confusion"]:
        columns = sorted({d for row in summary["confusion"].values() for d in row})
        lines += ["", "## Confusion (rows: confirmed role, columns: detected role)", ""]
        lines.append("| | " + " | ".join(columns) + " |")
        lines.append("|---|" + "---:|" * len(columns))
        for expected_role, row in summary["confusion"].items():
            lines.append(
                f"| {expected_role} | " + " | ".join(str(row.get(c, "")) for c in columns) + " |"
            )
    return "\n".join(lines) + "\n"
