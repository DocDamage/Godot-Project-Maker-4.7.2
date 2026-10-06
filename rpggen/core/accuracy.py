from __future__ import annotations

from typing import Any

from rpggen.core import catalog as catalog_mod

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


def score(catalog: catalog_mod.Catalog, expected: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Per-field ``correct/total`` over the paths listed in ``expected`` plus an overall value."""
    counts = {f: [0, 0] for f in FIELDS}
    misses: list[dict[str, Any]] = []
    for key, facts in sorted(expected.items()):
        asset = _find_asset(catalog, key)
        for field in FIELDS:
            if field not in facts:
                continue
            want = _expected_value(field, facts[field])
            got = _actual(asset, field)
            counts[field][1] += 1
            if got == want:
                counts[field][0] += 1
            else:
                misses.append({"path": key, "field": field, "expected": want, "actual": got})
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
    }


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
