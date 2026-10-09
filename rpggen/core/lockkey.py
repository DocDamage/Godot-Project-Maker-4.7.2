"""Lock-and-key planning on a graph of places (T13.21).

Shared by the connected-maps world (T13.20: keys and gates between top-down maps) and the
Metroidvania room graph (M14: abilities and the gates they open). Pure: no files, no Godot, and
every choice comes from the ``rng`` that is passed in.

A graph is ``{node: [edge, ...]}``. An edge is a neighbour, or ``(neighbour, key)`` when passing
it needs ``key``. Edges go one way, as written: a door that works both ways is listed at both
ends. A node that appears only as a neighbour is a node too.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Any

Node = Hashable
Graph = Mapping[Any, Sequence[Any]]


class LockKeyError(Exception):
    """The input has no solution. ``needed`` is how many free nodes (``reason == "nodes"``) the
    key that could not be placed still needed, counting itself and the keys after it;
    ``available`` is how many there were. ``reason == "goal"``: the goal cannot be reached even
    with every key."""

    def __init__(self, reason: str, needed: int, available: int, key: str | None = None) -> None:
        self.reason = reason
        self.needed = needed
        self.available = available
        self.key = key
        if reason == "goal":
            text = "the goal cannot be reached, even with every key"
        else:
            text = (
                f"{needed} free place(s) needed for the key {key!r} and those after it, "
                f"{available} can be reached"
            )
        super().__init__(text)


@dataclass(frozen=True)
class Plan:
    placements: dict[str, Any]  # key -> the node it lies in, in the order of ``keys``
    path: list[Any]  # the critical path: start, each key in order, the goal (every node walked)
    needed: list[str]  # the keys without which the goal cannot be reached, in the order of ``keys``


@dataclass(frozen=True)
class Check:
    ok: bool  # every node and the goal can be reached
    unreachable: list[Any]  # nodes no order of pick-ups reaches, sorted
    goal_reachable: bool
    order: list[str] = field(default_factory=list)  # the keys in the order they can be picked up


def _edges(graph: Graph, node: Any) -> Iterable[tuple[Any, str | None]]:
    for edge in graph.get(node, ()):
        if isinstance(edge, tuple):
            neighbour, key = edge
            yield neighbour, key
        else:
            yield edge, None


def nodes_of(graph: Graph) -> list[Any]:
    """Every node: the keys of the mapping first, then the neighbours only edges name."""
    seen: dict[Any, None] = dict.fromkeys(graph)
    for node in graph:
        for neighbour, _key in _edges(graph, node):
            seen.setdefault(neighbour)
    return list(seen)


def reachable(graph: Graph, start: Any, held: Iterable[str]) -> dict[Any, Any]:
    """The nodes that can be reached from ``start`` holding ``held``, each with the node it was
    first reached from (the start has None): a breadth-first tree, in the graph's own order."""
    have = set(held)
    parent: dict[Any, Any] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbour, key in _edges(graph, node):
            if neighbour in parent or (key is not None and key not in have):
                continue
            parent[neighbour] = node
            queue.append(neighbour)
    return parent


def _walk(parent: dict[Any, Any], node: Any) -> list[Any]:
    out = [node]
    while parent[out[-1]] is not None:
        out.append(parent[out[-1]])
    return out[::-1]


def check(graph: Graph, placements: Mapping[str, Any], start: Any, goal: Any) -> Check:
    """Play the placements through: pick up every key that can be reached, again and again, and
    say what stays out of reach. A validator reports ``unreachable``."""
    held: list[str] = []
    while True:
        reach = reachable(graph, start, held)
        found = [k for k, node in placements.items() if k not in held and node in reach]
        if not found:
            break
        held.extend(found)
    unreachable = sorted((n for n in nodes_of(graph) if n not in reach), key=str)
    goal_ok = goal in reach
    return Check(not unreachable and goal_ok, unreachable, goal_ok, held)


def plan(graph: Graph, keys: Sequence[str], start: Any, goal: Any, rng: Random) -> Plan:
    """Place ``keys`` in order, each in a node that the keys before it reach, never in the start
    or the goal and never two in one node. A key prefers the part of the graph that the key
    before it opened, so the locks chain and the goal needs every key the graph lets it need.
    Deterministic for a given ``rng`` state. Raises ``LockKeyError`` when a key has no free node
    or the goal stays cut off."""
    keys = list(keys)
    placements: dict[str, Any] = {}
    used: set[Any] = {start, goal}
    before: set[Any] = set()
    path: list[Any] = [start]
    here = start
    for index, key in enumerate(keys):
        reach = reachable(graph, start, keys[:index])
        free = [n for n in reach if n not in used]
        if not free:
            raise LockKeyError("nodes", len(keys) - index, 0, key)
        fresh = [n for n in free if n not in before]
        pool = sorted(fresh or free, key=str)
        node = pool[rng.randrange(len(pool))]
        placements[key] = node
        used.add(node)
        before = set(reach)
        path += _walk(reachable(graph, here, keys[:index]), node)[1:]
        here = node
    last = reachable(graph, here, keys)
    if goal not in last or goal not in reachable(graph, start, keys):
        raise LockKeyError("goal", len(keys), len(keys))
    path += _walk(last, goal)[1:]
    needed = [
        key
        for key in keys
        if not check(
            graph, {k: n for k, n in placements.items() if k != key}, start, goal
        ).goal_reachable
    ]
    return Plan(placements, path, needed)
