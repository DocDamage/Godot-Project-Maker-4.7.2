from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageSequence

from rpggen import paths
from rpggen.core.adapters import naming
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.analyzer import frames as frames_mod
from rpggen.core.analyzer import image_facts
from rpggen.core.inventory import Inventory, InventoryFile
from rpggen.errors import IssueList

STRIP_NAME = re.compile(
    r"^(?P<name>.+?)[_\- ](?P<action>idle|walk|run|attack|hurt|death|die|hit|move)"
    r"(?:[_\- ](?P<dir>down|up|left|right|front|back|side|s|n|e|w))?$",
    re.IGNORECASE,
)
DEFAULT_FPS = {"idle": 4.0, "walk": 8.0, "attack": 12.0, "hurt": 10.0, "death": 8.0}
GIF_STRIP_DIR = "generated/gif_strips"
STANDARD_ACTIONS = {"idle", "walk", "attack", "hurt", "death"}


def _fps(action: str) -> float:
    return DEFAULT_FPS.get(action.split("_")[0], 8.0)


def _is_still_png(f: InventoryFile) -> bool:
    return f.kind == "image" and f.image is not None and f.ext != ".gif"


def gif_strip_name(sha256: str) -> str:
    return f"{sha256}.png"


def _write_gif_strip(src: Path, dest: Path) -> tuple[int, tuple[int, int], list[int]]:
    """Compose a GIF's frames into a horizontal PNG strip; returns (frames, size, durations ms)."""
    with Image.open(src) as im:
        size = im.size
        frames, durations = [], []
        for fr in ImageSequence.Iterator(im):
            durations.append(int(fr.info.get("duration", 100)) or 100)
            frames.append(fr.convert("RGBA"))
    strip = Image.new("RGBA", (size[0] * len(frames), size[1]), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        strip.paste(fr, (i * size[0], 0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    strip.save(dest, format="PNG", optimize=False, pnginfo=None)
    return len(frames), size, durations


class StripsAdapter:
    name = "strips"
    priority = 60

    def match(self, inv: Inventory, root: Path) -> float:
        for f in inv.files:
            if f.kind != "image":
                continue
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            if STRIP_NAME.match(stem) or (f.ext == ".gif" and f.image and f.image["frames"] > 1):
                return 1.0
        return 0.0

    # ------------------------------------------------------------------ extraction

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        issues = IssueList()
        groups: dict[tuple[str, str], list[tuple[InventoryFile, re.Match[str]]]] = {}
        for f in inv.files:
            if not _is_still_png(f) or f.path in ctx.claimed:
                continue
            stem = posixpath.splitext(posixpath.basename(f.path))[0]
            m = STRIP_NAME.match(stem)
            if m:
                key = (posixpath.dirname(f.path), m.group("name").casefold())
                groups.setdefault(key, []).append((f, m))
        for key in sorted(groups):
            self._group(root, ctx.pack_id, key, groups[key], result, issues)
        for f in inv.files:
            animated = f.kind == "image" and f.ext == ".gif" and f.image and f.image["frames"] > 1
            if animated and f.path not in ctx.claimed:
                self._gif(root, f, ctx, result, issues)
        result.issues = list(issues)
        return result

    def _group(
        self,
        root: Path,
        pack_id: str,
        key: tuple[str, str],
        members: list[tuple[InventoryFile, re.Match[str]]],
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        members = sorted(members, key=lambda fm: (fm[0].path.casefold(), fm[0].path))
        analyses: list[tuple[InventoryFile, re.Match[str], Any, Any]] = []
        for f, m in members:
            mask = image_facts.occupancy(image_facts.load_rgba(root / f.path))
            strip = frames_mod.detect_strip(mask)
            if strip is None or strip.axis != "x":
                continue  # not a horizontal strip: leave it to the generic adapter
            analyses.append((f, m, strip, mask))
        if not analyses:
            return
        frame = analyses[0][2].frame
        animations: dict[str, Any] = {}
        used: list[InventoryFile] = []
        baseline = 0
        for f, m, strip, mask in analyses:
            if strip.frame != frame:
                continue
            raw = m.group("action") + ("_" + m.group("dir") if m.group("dir") else "")
            norm = naming.normalize_name(raw)
            if norm.name in animations:
                continue
            spec: dict[str, Any] = {
                "frames": [[i, 0] for i in range(strip.frames)],
                "fps": _fps(norm.action),
                "loop": naming.is_looping(norm.action),
                "source": f"assets/packs/{pack_id}/{f.path}",
            }
            animations[norm.name] = spec
            if norm.side and norm.direction == "right":
                mirror = f"{norm.action}_left"
                animations.setdefault(mirror, {**spec, "flip_h": True})
                issues.add("ANIM-002", anim=mirror, source_anim=norm.name, file=f.path)
            if norm.direction_assumed:
                result.pack_warnings.append(f"strips_direction_assumed:{f.path}")
            if not used:
                rects = [(i * frame[0], 0, frame[0], frame[1]) for i in range(strip.frames)]
                baseline = frames_mod.baseline_y(mask, rects)
            used.append(f)
        if not used:
            return
        facets = {
            "usage": "sprite",
            "grid": {"cell": list(frame), "margin": [0, 0], "separation": [0, 0]},
            "frame": list(frame),
            "origin": [frame[0] // 2, baseline],
            "animations": {k: animations[k] for k in sorted(animations)},
        }
        primary = used[0]
        result.assets.append(AssetFragment(primary.path, facets, 0.9, "full"))
        result.consumed.extend(f.path for f in used[1:])

    def _gif(
        self,
        root: Path,
        f: InventoryFile,
        ctx: AdapterContext,
        result: AdapterResult,
        issues: IssueList,
    ) -> None:
        work = (ctx.work_dir or paths.cache_dir()) / "gif_strips"
        dest = work / gif_strip_name(f.sha256)
        try:
            count, size, durations = _write_gif_strip(root / f.path, dest)
        except (OSError, ValueError) as exc:
            issues.add("ADAPT-001", adapter=self.name, file=f.path, reason=str(exc))
            return
        stem = posixpath.splitext(posixpath.basename(f.path))[0]
        m = STRIP_NAME.match(stem)
        norm = (
            naming.normalize_name(
                m.group("action") + ("_" + m.group("dir") if m.group("dir") else "")
            )
            if m
            else None
        )
        name = norm.name if norm and norm.action in STANDARD_ACTIONS else "idle_down"
        action = name.split("_")[0]
        base_ms = sorted(durations)[len(durations) // 2] or 100
        project_path = f"{GIF_STRIP_DIR}/{gif_strip_name(f.sha256)}"
        facets = {
            "usage": "sprite",
            "grid": {"cell": [size[0], size[1]], "margin": [0, 0], "separation": [0, 0]},
            "frame": [size[0], size[1]],
            "origin": [size[0] // 2, size[1] - 1],
            "animations": {
                name: {
                    "frames": [[i, 0] for i in range(count)],
                    "fps": round(1000.0 / base_ms, 6),
                    "loop": naming.is_looping(action),
                    "source": project_path,
                }
            },
        }
        result.assets.append(AssetFragment(f.path, facets, 0.85, "full"))
        result.generated[project_path] = str(dest)
