"""Confidence calibrated on the answer key (T17.34).

A reader's confidence says how sure it is, not how often it is right. Measured on the key of
the owner's real packs (``tools/answer_key.py``, ``rpggen analyze --private-corpus``), each
reader's pictures are put in bins by the reader, the role it gave and its confidence; a bin's
calibrated confidence follows the share of its pictures that were right, cautiously (the lower
end of its 95 % interval, ``wilson_low``): a bin whose pictures are right 99 % of the time or
more, surely, reads at ``AUTO_CONFIDENCE`` or above (sure), any other below it. So a picture
marked sure is right at least ``SURE_ACCURACY`` of the time, as measured.

The table holds numbers only (readers, roles, bins); nothing of the packs. A picture of a
reader, role or bin the key never saw keeps its confidence. ``RPGGEN_CALIBRATION=off`` turns it
off (the fit itself reads the raw confidences).
"""

from __future__ import annotations

import json
import math
import os
from functools import cache
from pathlib import Path
from typing import Any

SURE_ACCURACY = 0.99
MIN_PICTURES = 30  # a bin with fewer pictures is not fitted
BIN_EDGES = (0.0, 0.3, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0001)
TABLE = Path(__file__).resolve().parent.parent / "data" / "calibration.json"
VERSION = 1
Z95 = 1.96


def wilson_low(right: int, total: int, z: float = Z95) -> float:
    """The lower end of the 95 % Wilson interval of ``right / total``."""
    if total <= 0:
        return 0.0
    p = right / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return max(0.0, (centre - spread) / denom)


def bin_of(confidence: float) -> int:
    for i in range(len(BIN_EDGES) - 1):
        if BIN_EDGES[i] <= confidence < BIN_EDGES[i + 1]:
            return i
    return len(BIN_EDGES) - 2


def mapped(low: float, auto: float, confirmed: float) -> float:
    """The confidence a bin whose accuracy is at least ``low`` reads at: ``auto`` and above
    (up to just under ``confirmed``) from ``SURE_ACCURACY``, below ``auto`` under it."""
    if low >= SURE_ACCURACY:
        span = (low - SURE_ACCURACY) / (1 - SURE_ACCURACY)
        return round(min(confirmed - 0.0005, auto + span * (confirmed - auto)), 4)
    return round(auto * low / SURE_ACCURACY * 0.999, 4)


def fit(pictures: list[dict[str, Any]], auto: float, confirmed: float) -> dict[str, Any]:
    """The table from the pictures of a private-corpus report (``reader``, ``role``,
    ``confidence`` uncalibrated, ``right``)."""
    counts: dict[str, list[int]] = {}
    for p in pictures:
        for key in (f"{p['reader']}|{p.get('role', '')}", f"{p['reader']}|*"):
            row = counts.setdefault(f"{key}|{bin_of(float(p['confidence']))}", [0, 0])
            row[0] += int(bool(p["right"]))
            row[1] += 1
    bins = {}
    for key, (right, total) in sorted(counts.items()):
        if total < MIN_PICTURES:
            continue
        low = wilson_low(right, total)
        bins[key] = {"right": right, "total": total, "low": round(low, 4),
                     "confidence": mapped(low, auto, confirmed)}  # fmt: skip
    return {"version": VERSION, "sure_accuracy": SURE_ACCURACY, "bins": bins}


@cache
def _table() -> dict[str, Any]:
    if not TABLE.is_file():
        return {}
    try:
        data = json.loads(TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("version") == VERSION else {}


def enabled() -> bool:
    return os.environ.get("RPGGEN_CALIBRATION", "").lower() not in ("off", "0", "no")


def calibrate(reader: str, role: str, confidence: float) -> float:
    """``confidence`` as the key measured that reader's pictures of that role at it: the bin of
    the reader and role, else of the reader alone, else unchanged."""
    if not enabled():
        return confidence
    return calibrate_with(_table(), reader, role, confidence)


def calibrate_with(table: dict[str, Any], reader: str, role: str, confidence: float) -> float:
    """``calibrate`` against ``table`` (a table being fitted, or another than the shipped one)."""
    bins = table.get("bins") or {}
    b = bin_of(confidence)
    for key in (f"{reader}|{role}|{b}", f"{reader}|*|{b}"):
        found = bins.get(key)
        if isinstance(found, dict) and isinstance(found.get("confidence"), (int, float)):
            return float(found["confidence"])
    return confidence
