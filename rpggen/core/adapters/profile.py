"""Profile adapter (priority 0): applies an installed pack profile to a pack that matches it."""

from __future__ import annotations

import copy
from pathlib import Path

from rpggen.core import profiles
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory
from rpggen.errors import IssueList

PROFILE_CONFIDENCE = 0.999


class ProfileAdapter:
    name = "profile"
    priority = 0

    def match(self, inv: Inventory, root: Path) -> float:
        return profiles.best_match(inv)[0]

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        ratio, profile = profiles.best_match(inv)
        result = AdapterResult(self.name)
        if profile is None:
            return result
        issues = IssueList()
        issues.add("ADAPT-003", profile_id=profile["profile_id"], ratio=f"{ratio:.0%}")
        result.issues = list(issues)
        result.profile_id = profile["profile_id"]
        files = {f.path: f for f in inv.files}
        fingerprinted = profile["fingerprint"]["required_files"]
        emitted: set[str] = set()
        for key, facets in profile["assets"].items():
            path, variant = profiles.split_key(key)
            f = files.get(path)
            if f is None or f.kind not in ("image", "audio", "font"):
                continue
            expected = fingerprinted.get(path)
            if expected is not None and expected != f.sha256:
                continue  # the file changed: normal detection decides
            result.assets.append(
                AssetFragment(path, copy.deepcopy(facets), PROFILE_CONFIDENCE, "full", variant)
            )
            if not variant:
                emitted.add(path)
        for obj in profile["objects"]:
            sheet = profiles.split_key(obj["sheet_path"])[0]
            if sheet in emitted:
                data = copy.deepcopy(obj)
                data["sheet_path"] = sheet
                data["authoritative"] = True  # replaces auto-detected objects of the same sheet
                result.objects.append(data)
        result.folder_rules = [
            {**copy.deepcopy(rule), "pack_id": ctx.pack_id} for rule in profile["folder_rules"]
        ]
        result.tilesets = [{**copy.deepcopy(t), "from_profile": True} for t in profile["tilesets"]]
        result.pack_license = copy.deepcopy(profile.get("pack_license") or {})
        return result
