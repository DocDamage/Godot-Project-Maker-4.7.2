from __future__ import annotations

from pathlib import Path

import pytest

from rpggen.core import adapters
from rpggen.core.adapters import AdapterContext, AdapterResult, AssetFragment
from rpggen.core.inventory import Inventory


class Fake:
    def __init__(
        self, name: str, priority: int, score: float = 1.0, paths=(), claim="full", boom=False
    ):
        self.name, self.priority = name, priority
        self.score, self.paths, self.claim, self.boom = score, list(paths), claim, boom
        self.extracted = False
        self.seen_claimed: set[str] = set()

    def match(self, inv, root) -> float:
        return self.score

    def extract(self, inv, root, ctx) -> AdapterResult:
        self.extracted = True
        self.seen_claimed = set(ctx.claimed)
        if self.boom:
            raise RuntimeError("kaboom")
        return AdapterResult(
            self.name,
            assets=[AssetFragment(p, {"usage": "tiles"}, 1.0, self.claim) for p in self.paths],
        )


INV = Inventory("pk", "0" * 64)


def _run(adapter_list: list[Fake]) -> tuple[list[AdapterResult], AdapterContext]:
    ctx = AdapterContext(pack_id="pk")
    return adapters.run_adapters(INV, Path("."), ctx, adapter_list), ctx


def test_runs_in_priority_order_and_skips_low_scores() -> None:
    a, b, c = Fake("a", 20), Fake("b", 10), Fake("c", 5, score=0.4)
    results, _ = _run([a, b, c])
    assert [r.adapter for r in results] == ["b", "a"]
    assert not c.extracted


def test_full_claims_hide_paths_from_later_adapters() -> None:
    first = Fake("first", 10, paths=["x.png", "y.png"], claim="full")
    second = Fake("second", 20, paths=["x.png", "z.png"], claim="partial")
    results, ctx = _run([second, first])
    assert second.seen_claimed == {"x.png", "y.png"}
    assert [f.path for f in results[1].assets] == ["z.png"]
    assert ctx.claimed == {"x.png", "y.png"}


def test_partial_claims_do_not_block() -> None:
    first = Fake("first", 10, paths=["x.png"], claim="partial")
    second = Fake("second", 20, paths=["x.png"], claim="partial")
    results, ctx = _run([first, second])
    assert [f.path for f in results[1].assets] == ["x.png"]
    assert ctx.claimed == set()


def test_failing_adapter_gives_adapt001_and_others_continue(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bad, good = Fake("bad", 10, boom=True), Fake("good", 20, paths=["g.png"])
    results, _ = _run([bad, good])
    assert [r.adapter for r in results] == ["bad", "good"]
    issue = results[0].issues[0]
    assert issue.code == "ADAPT-001" and "kaboom" in issue.message
    assert issue.severity.value == "warning"
    assert good.extracted


def test_registry_orders_and_replaces() -> None:
    saved = list(adapters._ADAPTERS)
    try:
        adapters._ADAPTERS.clear()
        adapters.register(Fake("z", 100))
        adapters.register(Fake("a", 10))
        adapters.register(Fake("a", 15))  # same name replaces
        assert [(x.name, x.priority) for x in adapters.get_adapters()] == [("a", 15), ("z", 100)]
    finally:
        adapters._ADAPTERS[:] = saved
