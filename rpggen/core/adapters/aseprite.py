from __future__ import annotations

import json
import posixpath
from collections import Counter
from pathlib import Path
from typing import Any

from rpggen.core.adapters import naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import frames as frames_mod
from rpggen.core.analyzer import image_facts
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

MAX_JSON_BYTES = 16 * 1024 * 1024


def _load_export(root: Path, rel: str) -> dict[str, Any] | None:
    path = root / rel
    if path.stat().st_size > MAX_JSON_BYTES:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    if not isinstance(data, dict) or "frames" not in data:
        return None
    meta = data.get("meta")
    if not isinstance(meta, dict) or "aseprite" not in str(meta.get("app", "")).lower():
        return None
    return data


def _frame_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data["frames"]
    return list(raw.values()) if isinstance(raw, dict) else list(raw)


def _tag_indices(tag: dict[str, Any]) -> list[int]:
    lo, hi = int(tag["from"]), int(tag["to"])
    forward = list(range(lo, hi + 1))
    direction = tag.get("direction", "forward")
    if direction == "reverse":
        return forward[::-1]
    if direction == "pingpong":
        return forward + forward[-2:0:-1]
    if direction == "pingpong_reverse":
        rev = forward[::-1]
        return rev + rev[-2:0:-1]
    return forward


class AsepriteAdapter:
    name = "aseprite"
    priority = 20

    def _exports(self, inv: Inventory, root: Path) -> list[tuple[str, dict[str, Any]]]:
        out = []
        for f in inv.files:
            if f.ext == ".json":
                data = _load_export(root, f.path)
                if data is not None:
                    out.append((f.path, data))
        return out

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0 if self._exports(inv, root) else 0.0

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        by_lower = {f.path.casefold(): f.path for f in inv.files}
        for json_path, data in self._exports(inv, root):
            image_rel = posixpath.normpath(
                posixpath.join(posixpath.dirname(json_path), str(data["meta"].get("image", "")))
            )
            image = by_lower.get(image_rel.casefold())
            if image is None:
                issues.add("ADAPT-002", file=json_path, image=data["meta"].get("image", ""))
                continue
            fragment = self._convert(root, image, data, result, issues)
            if fragment is not None:
                result.assets.append(fragment)
        result.issues = list(issues)
        return result

    def _convert(
        self,
        root: Path,
        image: str,
        data: dict[str, Any],
        result: AdapterResult,
        issues: IssueList,
    ) -> AssetFragment | None:
        frame_list = _frame_list(data)
        if not frame_list:
            return None
        source = frame_list[0].get("sourceSize", {})
        sw = int(source.get("w", frame_list[0]["frame"]["w"]))
        sh = int(source.get("h", frame_list[0]["frame"]["h"]))
        tags = data["meta"].get("frameTags") or [
            {"name": "idle_down", "from": 0, "to": len(frame_list) - 1, "direction": "forward"}
        ]
        animations: dict[str, dict[str, Any]] = {}
        for tag in tags:
            norm = naming.normalize_name(str(tag.get("name", "")))
            indices = [i for i in _tag_indices(tag) if 0 <= i < len(frame_list)]
            if not indices:
                continue
            if norm.name in animations:
                result.pack_warnings.append(f"aseprite_duplicate_tag:{norm.name}")
                continue
            if norm.direction_assumed:
                result.pack_warnings.append(f"aseprite_direction_assumed:{tag.get('name')}")
            durations_ms = [int(frame_list[i].get("duration", 100)) for i in indices]
            counts = Counter(durations_ms)
            top = max(counts.values())
            base_ms = min(d for d, n in counts.items() if n == top) or 100
            spec: dict[str, Any] = {
                "frames": [[i, 0] for i in indices],
                "rects": [
                    [int(frame_list[i]["frame"][k]) for k in ("x", "y", "w", "h")] for i in indices
                ],
                "offsets": [
                    [
                        int(frame_list[i].get("spriteSourceSize", {}).get("x", 0)),
                        int(frame_list[i].get("spriteSourceSize", {}).get("y", 0)),
                    ]
                    for i in indices
                ],
                "fps": round(1000.0 / base_ms, 6),
                "loop": naming.is_looping(norm.action),
            }
            durations = [round(d / base_ms, 6) for d in durations_ms]
            if any(d != 1.0 for d in durations):
                spec["durations"] = durations
            animations[norm.name] = spec
            if norm.side and norm.direction == "right":
                mirror = f"{norm.action}_left"
                if mirror not in animations:
                    animations[mirror] = {**spec, "flip_h": True}
                    issues.add("ANIM-002", anim=mirror, source_anim=norm.name, file=image)
        if not animations:
            return None
        facets: dict[str, Any] = {
            "usage": "sprite",
            "frame": [sw, sh],
            "animations": {k: animations[k] for k in sorted(animations)},
            "origin": [sw // 2, self._baseline(root, image, frame_list)],
        }
        return AssetFragment(image, facets, 1.0, "full")

    @staticmethod
    def _baseline(root: Path, image: str, frame_list: list[dict[str, Any]]) -> int:
        first = frame_list[0]
        rect = tuple(int(first["frame"][k]) for k in ("x", "y", "w", "h"))
        oy = int(first.get("spriteSourceSize", {}).get("y", 0))
        mask = image_facts.occupancy(image_facts.load_rgba(root / image))
        rel = frames_mod.baseline_y(mask, [rect])  # relative to the trimmed frame's top
        return oy + rel
