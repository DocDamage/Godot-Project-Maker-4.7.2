"""Learned adapter (priority 5, T12.59): the user's earlier corrections, as rules.

It runs after the profile adapter (a pack profile's full claims win) and before the readers and
the heuristics. For each file a learned rule matches it proposes that rule's role, usage or
collision as a *preferred* partial fragment: it wins over the partial guesses of other adapters
and keeps the classifier from guessing the role, but not over a format reader's full claim. Its
confidence is the rule's hit rate, capped at ``learned_rules.CAP``, so the asset stays
"Auto-detected". Without rules in the context (the CLI, the tests) it proposes nothing.
"""

from __future__ import annotations

from pathlib import Path

from rpggen.core import learned_rules
from rpggen.core.adapters.base import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory

NAME = "learned"


class LearnedAdapter:
    name = NAME
    priority = 5

    def match(self, inv: Inventory, root: Path) -> float:
        return 1.0  # cheap; extract proposes nothing without rules

    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult:
        result = AdapterResult(self.name)
        if not ctx.learned:
            return result
        for f in inv.files:
            if f.kind not in ("image", "audio", "font"):
                continue
            decided = learned_rules.proposals(ctx.learned, f.path)
            if not decided:
                continue
            result.assets.append(
                AssetFragment(
                    f.path,
                    {facet: rule.value for facet, rule in sorted(decided.items())},
                    min(rule.confidence for rule in decided.values()),
                    "partial",
                    preferred=True,
                )
            )
        return result
