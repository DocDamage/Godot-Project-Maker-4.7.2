@tool
extends RefCounted
## The maps of a project as a graph (T13.20): every map with its doors and its spawn points, which
## maps the starter map cannot reach through doors, and which doors lead nowhere. The validator
## (content_checks.gd) and the world repair read the same graph, so they agree on what is broken.
##
## A graph is {map path: {"doors": [{node, target, spawn}], "spawns": [spawn ids]}}. `node` is the
## door's path inside its scene.

const DOOR_SUFFIX := "/world/door.gd"
const SPAWN_SUFFIX := "/world/spawn_point.gd"
const START := "res://game/maps/starter_map.tscn"
## Maps that are not part of the world on purpose: the library of imported Tiled and LDtk maps.
const LIBRARY_DIR := "/imported/"

## The graph of `maps` (scene paths). `instance_of.call(path)` gives a map's instantiated root (or
## null); the caller owns and frees those nodes.
static func read(maps: Array[String], instance_of: Callable) -> Dictionary:
	var graph := {}
	for path in maps:
		var root: Node = instance_of.call(path)
		if root == null:
			continue
		var doors: Array[Dictionary] = []
		var spawns: Array[String] = []
		var nodes: Array[Node] = []
		_walk(root, nodes)
		for node in nodes:
			if _is(node, DOOR_SUFFIX) and str(node.get("target_map")) != "":
				doors.append({"node": String(root.get_path_to(node)), "target": str(node.get("target_map")), "spawn": str(node.get("target_spawn"))})
			elif _is(node, SPAWN_SUFFIX):
				spawns.append(str(node.get("spawn_id")))
		graph[path] = {"doors": doors, "spawns": spawns}
	return graph

static func _is(node: Node, suffix: String) -> bool:
	var script: Script = node.get_script()
	return script != null and script.resource_path.ends_with(suffix)

static func _walk(node: Node, out: Array[Node]) -> void:
	out.append(node)
	for child in node.get_children():
		_walk(child, out)

## The maps that can be reached from `start` by walking through doors (start included).
static func reachable(graph: Dictionary, start: String = START) -> Array[String]:
	var seen: Array[String] = []
	if not graph.has(start):
		return seen
	var queue: Array[String] = [start]
	while not queue.is_empty():
		var path: String = queue.pop_front()
		if seen.has(path):
			continue
		seen.append(path)
		var entry: Dictionary = graph[path]
		var doors: Array = entry["doors"]
		for door: Dictionary in doors:
			var target := str(door["target"])
			if graph.has(target) and not seen.has(target):
				queue.append(target)
	return seen

## The maps of the graph that `start` cannot reach, sorted (the library of imported maps is left
## out: those are built on request, not placed in the world). Empty when there is no start map.
static func unreachable(graph: Dictionary, start: String = START) -> Array[String]:
	var out: Array[String] = []
	if not graph.has(start):
		return out
	var seen := reachable(graph, start)
	for path: String in graph.keys():
		if not seen.has(path) and not path.contains(LIBRARY_DIR):
			out.append(path)
	out.sort()
	return out

## The doors that lead nowhere: [{map, node, target, spawn, missing}] with `missing` "map" (the
## target map is not a file) or "spawn" (the map exists but has no such spawn point), in map and
## node order. `exists.call(path)` says whether a map file exists (a map outside the graph may).
static func dangling(graph: Dictionary, exists: Callable) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var paths: Array = graph.keys()
	paths.sort()
	for path: String in paths:
		var entry: Dictionary = graph[path]
		var doors: Array = entry["doors"]
		for door: Dictionary in doors:
			var target := str(door["target"])
			var missing := ""
			if not graph.has(target) and not exists.call(target):
				missing = "map"
			elif graph.has(target):
				var target_entry: Dictionary = graph[target]
				var spawns: Array = target_entry["spawns"]
				if not spawns.has(str(door["spawn"])):
					missing = "spawn"
			if missing != "":
				out.append({"map": path, "node": door["node"], "target": target, "spawn": door["spawn"], "missing": missing})
	return out

## True when `from` has a door to `to`.
static func has_door(graph: Dictionary, from: String, to: String) -> bool:
	if not graph.has(from):
		return false
	var entry: Dictionary = graph[from]
	var doors: Array = entry["doors"]
	for door: Dictionary in doors:
		if str(door["target"]) == to:
			return true
	return false
