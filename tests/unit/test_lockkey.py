"""The lock-and-key planner (T13.21)."""

from __future__ import annotations

from random import Random

import pytest

from rpggen.core import lockkey
from rpggen.core.lockkey import LockKeyError

# start - a - b =red= c - d =blue= goal, with a side room e off a
CHAIN = {
    "start": ["a"],
    "a": ["start", "b", "e"],
    "e": ["a"],
    "b": ["a", ("c", "red")],
    "c": [("b", "red"), "d"],
    "d": ["c", ("goal", "blue")],
    "goal": [("d", "blue")],
}


def _valid_path(graph, plan, keys, start, goal) -> None:
    """The critical path only uses edges that exist and are open with the keys picked up so far."""
    held: set[str] = set()
    where = {node: key for key, node in plan.placements.items()}
    assert plan.path[0] == start and plan.path[-1] == goal
    for a, b in zip(plan.path, plan.path[1:], strict=False):
        if a in where:
            held.add(where[a])
        edges = dict(lockkey._edges(graph, a))
        assert b in edges, (a, b)
        assert edges[b] is None or edges[b] in held, (a, b, edges[b])
    assert held == set(keys)


def test_a_chain_puts_each_key_before_its_lock() -> None:
    plan = lockkey.plan(CHAIN, ["red", "blue"], "start", "goal", Random(1))
    assert plan.placements["red"] in {"a", "b", "e"}
    assert plan.placements["blue"] in {"c", "d"}  # behind the red lock
    assert list(plan.placements) == ["red", "blue"]
    assert plan.needed == ["red", "blue"]
    _valid_path(CHAIN, plan, ["red", "blue"], "start", "goal")
    result = lockkey.check(CHAIN, plan.placements, "start", "goal")
    assert result.ok and result.unreachable == [] and result.order == ["red", "blue"]


def test_the_plan_is_stable_for_a_seed_and_differs_between_seeds() -> None:
    first = lockkey.plan(CHAIN, ["red", "blue"], "start", "goal", Random(7))
    again = lockkey.plan(CHAIN, ["red", "blue"], "start", "goal", Random(7))
    assert first == again
    shuffled = dict(reversed(list(CHAIN.items())))  # the mapping's order does not matter
    assert lockkey.plan(shuffled, ["red", "blue"], "start", "goal", Random(7)).placements == (
        first.placements
    )
    seen = {
        tuple(lockkey.plan(CHAIN, ["red", "blue"], "start", "goal", Random(s)).placements.items())
        for s in range(40)
    }
    assert len(seen) > 1


def test_too_few_free_nodes_raises_with_the_count() -> None:
    tiny = {"start": [("goal", "red")], "goal": []}
    with pytest.raises(LockKeyError) as info:
        lockkey.plan(tiny, ["red"], "start", "goal", Random(0))
    assert info.value.reason == "nodes" and info.value.needed == 1 and info.value.available == 0
    assert info.value.key == "red"
    # two keys, one free node before the first lock
    short = {"start": ["a"], "a": [("goal", "red")], "goal": []}
    with pytest.raises(LockKeyError) as info:
        lockkey.plan(short, ["red", "blue"], "start", "goal", Random(0))
    assert info.value.needed == 1 and info.value.key == "blue"


def test_a_goal_that_is_cut_off_raises() -> None:
    cut = {"start": ["a"], "a": ["start"], "goal": ["start"]}
    with pytest.raises(LockKeyError) as info:
        lockkey.plan(cut, [], "start", "goal", Random(0))
    assert info.value.reason == "goal"
    locked = {"start": ["a"], "a": [("goal", "green")], "goal": []}  # nobody places green
    with pytest.raises(LockKeyError) as info:
        lockkey.plan(locked, ["red"], "start", "goal", Random(0))
    assert info.value.reason == "goal"


def test_check_names_the_unreachable_nodes() -> None:
    # the red key lies behind its own lock
    result = lockkey.check(CHAIN, {"red": "c", "blue": "d"}, "start", "goal")
    assert not result.ok and not result.goal_reachable
    assert result.unreachable == ["c", "d", "goal"]
    assert result.order == []
    # a node only an edge names counts, and an island is reported
    island = {"start": ["a"], "a": ["goal"], "x": ["y"]}
    result = lockkey.check(island, {}, "start", "goal")
    assert result.goal_reachable and not result.ok and result.unreachable == ["x", "y"]
    # keys may be picked up in any order
    result = lockkey.check(CHAIN, {"blue": "e", "red": "a"}, "start", "goal")
    assert result.ok and sorted(result.order) == ["blue", "red"]


def test_a_key_the_goal_does_not_need_is_not_listed_as_needed() -> None:
    graph = {"start": ["a", "goal"], "a": ["start", ("vault", "red")], "vault": [], "goal": []}
    plan = lockkey.plan(graph, ["red"], "start", "goal", Random(3))
    assert plan.placements == {"red": "a"} and plan.needed == []
    assert lockkey.check(graph, plan.placements, "start", "goal").ok


def _random_world(rng: Random, key_count: int) -> tuple[dict[str, list], list[str]]:
    """Regions in a row; the only way from region i to region i + 1 needs key i. Every region has
    one to four rooms joined into a tree plus a few extra doors; the goal is beyond the last
    lock."""
    keys = [f"k{i}" for i in range(key_count)]
    graph: dict[str, list] = {"start": [], "goal": []}

    def join(a: str, b: str, key: str | None = None) -> None:
        graph.setdefault(a, []).append((b, key) if key else b)
        graph.setdefault(b, []).append((a, key) if key else a)

    previous = ["start"]
    for region in range(key_count + 1):
        rooms = [f"r{region}_{i}" for i in range(rng.randint(1, 4))]
        for i, room in enumerate(rooms):
            if i:
                join(rooms[rng.randrange(i)], room)
        for _ in range(rng.randint(0, 2)):
            a, b = rng.choice(rooms), rng.choice(rooms)
            if a != b:
                join(a, b)
        join(rng.choice(previous), rooms[0], keys[region - 1] if region else None)
        previous = rooms
    join(rng.choice(previous), "goal")
    return graph, keys


def test_200_random_worlds_plan_and_verify() -> None:
    rng = Random(20261009)
    for _ in range(200):
        key_count = rng.randint(2, 6)
        graph, keys = _random_world(rng, key_count)
        seed = rng.randrange(1 << 30)
        plan = lockkey.plan(graph, keys, "start", "goal", Random(seed))
        assert plan == lockkey.plan(graph, keys, "start", "goal", Random(seed))
        assert len(set(plan.placements.values())) == key_count
        assert "start" not in plan.placements.values() and "goal" not in plan.placements.values()
        result = lockkey.check(graph, plan.placements, "start", "goal")
        assert result.ok, (graph, plan)
        assert result.order == keys and plan.needed == keys
        _valid_path(graph, plan, keys, "start", "goal")
