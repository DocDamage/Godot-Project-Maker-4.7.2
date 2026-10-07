@tool
extends RefCounted
## Content checks of a project's maps, dialogue and resources. Run headless by
## builder/validate.gd and in the editor by the validator panel; both call run(), so they report
## the same findings.
##
## A finding is {code, detail, file, node}: `detail` fills the message template of the code
## (it already holds "file"), `file` is a res:// path and `node` a path inside the scene ("" when
## the finding is about the whole file).

const EntityIds := preload("entity_ids.gd")
const Condition := preload("res://addons/rpg_runtime/dialogue/condition.gd")

const MAPS_DIR := "res://game/maps"
const DIALOGUE_DIR := "res://game/data/dialogue"
const ITEMS_DIR := "res://game/data/items"
const PLACEHOLDER_DIR := "res://generated/debug_placeholders/"
const RESOURCE_ROOTS := ["res://generated", "res://game"]
const DOOR_SUFFIX := "/world/door.gd"
const SPAWN_SUFFIX := "/world/spawn_point.gd"

## `dirs` overrides the folders that are checked (tests): maps, dialogue, items, placeholders and
## resources (an Array of roots).
static func run(dirs: Dictionary = {}) -> Array:
	var findings: Array = []
	var cache := {}  # map path -> instantiated scene (or null), freed at the end
	var maps := list_files(String(dirs.get("maps", MAPS_DIR)), ["tscn"])
	_check_entity_ids(maps, cache, findings)
	_check_doors(maps, cache, findings)
	_check_dialogue(String(dirs.get("dialogue", DIALOGUE_DIR)), String(dirs.get("items", ITEMS_DIR)), findings)
	_check_placeholders(dirs.get("resources", RESOURCE_ROOTS), String(dirs.get("placeholders", PLACEHOLDER_DIR)), findings)
	for key in cache.keys():
		if cache[key] != null:
			cache[key].free()
	findings.sort_custom(_before)
	return findings

static func _before(a: Dictionary, b: Dictionary) -> bool:
	var ka := "%s|%s|%s|%s" % [a["file"], a["node"], a["code"], str(a["detail"])]
	var kb := "%s|%s|%s|%s" % [b["file"], b["node"], b["code"], str(b["detail"])]
	return ka < kb

static func finding(code: String, detail: Dictionary, file: String, node: String = "") -> Dictionary:
	var d := detail.duplicate()
	d["file"] = file.trim_prefix("res://")
	return {"code": code, "detail": d, "file": file, "node": node}

## Files below dir_path with one of the extensions, sorted by path, recursive.
static func list_files(dir_path: String, extensions: Array) -> Array:
	var found: Array = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	var entries: Array = []
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		entries.append([entry, dir.current_is_dir()])
		entry = dir.get_next()
	dir.list_dir_end()
	entries.sort_custom(func(a: Array, b: Array) -> bool: return String(a[0]) < String(b[0]))
	for e in entries:
		var full: String = dir_path + "/" + e[0]
		if e[1]:
			if not String(e[0]).begins_with("."):
				found.append_array(list_files(full, extensions))
		elif extensions.has(String(e[0]).get_extension()):
			found.append(full)
	return found

static func _instance(path: String, cache: Dictionary) -> Node:
	if not cache.has(path):
		var packed := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
		cache[path] = packed.instantiate() if packed != null else null
	return cache[path]

static func _script_ends_with(node: Node, suffix: String) -> bool:
	var script := node.get_script() as Script
	return script != null and script.resource_path.ends_with(suffix)

static func _walk(node: Node, out: Array) -> void:
	out.append(node)
	for child in node.get_children():
		_walk(child, out)

# ---------------------------------------------------------------- entity ids (VAL-008, VAL-009)

static func _check_entity_ids(maps: Array, cache: Dictionary, findings: Array) -> void:
	var owners := {}  # id -> Array of map paths (one entry per node)
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		for node in EntityIds.entity_nodes(root):
			var id := str(node.get("entity_id"))
			if id == "":
				if EntityIds.is_persistent(node):
					var node_path := String(root.get_path_to(node))
					findings.append(finding("VAL-009", {"node": node_path}, path, node_path))
				continue
			if not owners.has(id):
				owners[id] = []
			owners[id].append(path)
	var ids: Array = owners.keys()
	ids.sort()
	for id in ids:
		var files: Array = owners[id]
		if files.size() < 2:
			continue
		var unique: Array = []
		for f in files:
			var shown := String(f).trim_prefix("res://")
			if not unique.has(shown):
				unique.append(shown)
		findings.append(finding("VAL-008", {"id": id, "files": ", ".join(unique)}, files[0]))

# ---------------------------------------------------------------- doors (VAL-016, VAL-017)

static func _spawn_ids(root: Node) -> Array:
	var nodes: Array = []
	_walk(root, nodes)
	var out: Array = []
	for n in nodes:
		if _script_ends_with(n, SPAWN_SUFFIX):
			out.append(str(n.get("spawn_id")))
	return out

static func _check_doors(maps: Array, cache: Dictionary, findings: Array) -> void:
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		var nodes: Array = []
		_walk(root, nodes)
		for node in nodes:
			if not _script_ends_with(node, DOOR_SUFFIX):
				continue
			var target := str(node.get("target_map"))
			if target == "":
				continue  # a door that is not wired up yet (the runtime warns when it is used)
			var node_path := String(root.get_path_to(node))
			if not ResourceLoader.exists(target):
				findings.append(finding("VAL-016", {"node": node_path, "target": target}, path, node_path))
				continue
			var spawn := str(node.get("target_spawn"))
			var target_root := _instance(target, cache)
			if target_root != null and not _spawn_ids(target_root).has(spawn):
				findings.append(finding("VAL-017", {"node": node_path, "spawn": spawn, "target": target}, path, node_path))

# ---------------------------------------------------------------- dialogue (VAL-018, VAL-019)

static func _item_ids(items_dir: String) -> Array:
	var ids: Array = []
	for path in list_files(items_dir, ["tres"]):
		var res := load(path)
		if res != null and res.get("id") != null:
			ids.append(str(res.get("id")))
	return ids

## Item ids an expression refers to: its item:<id>[>=N] atoms.
static func condition_items(expr: String) -> Array:
	var out: Array = []
	for token in expr.strip_edges().split(" ", false):
		if token.begins_with("item:"):
			out.append(token.trim_prefix("item:").get_slice(">=", 0))
	return out

## Item ids an event refers to: give_item:<id>[:qty] and take_item:<id>[:qty].
static func event_items(event: String) -> Array:
	var parts := event.strip_edges().split(":")
	if parts.size() >= 2 and (parts[0] == "give_item" or parts[0] == "take_item"):
		return [parts[1]]
	return []

static func _check_dialogue(dialogue_dir: String, items_dir: String, findings: Array) -> void:
	var files := list_files(dialogue_dir, ["tres"])
	if files.is_empty():
		return
	var known := _item_ids(items_dir)
	for path in files:
		var res := load(path)
		if res == null or res.get("lines") == null:
			continue
		var lines: Array = res.get("lines")
		var reported := {}
		for i in lines.size():
			var line: Object = lines[i]
			if line == null:
				continue
			var conditions: Array = [str(line.get("condition"))]
			for choice in line.get("choices"):
				if choice != null:
					conditions.append(str(choice.get("condition")))
			for expr in conditions:
				if Condition.mixes_operators(expr):
					findings.append(finding("VAL-018", {"n": i + 1}, path))
					break
			var items: Array = []
			for expr in conditions:
				items.append_array(condition_items(expr))
			for event in line.get("events"):
				items.append_array(event_items(str(event)))
			for item in items:
				if not known.has(item) and not reported.has(item):
					reported[item] = true
					findings.append(finding("VAL-019", {"item": item}, path))

# ---------------------------------------------------------------- placeholders (VAL-012)

static func _check_placeholders(roots: Array, placeholder_dir: String, findings: Array) -> void:
	for root_dir in roots:
		for path in list_files(root_dir, ["tres", "tscn"]):
			for dep in ResourceLoader.get_dependencies(path):
				if _dependency_path(String(dep)).begins_with(placeholder_dir):
					findings.append(finding("VAL-012", {}, path))
					break

## The file a ResourceLoader.get_dependencies entry points to ("" for an unknown uid).
static func _dependency_path(dep: String) -> String:
	var path := dep
	if dep.contains("::"):
		path = dep.get_slice("::", dep.get_slice_count("::") - 1)
	if path.begins_with("uid://"):
		var id := ResourceUID.text_to_id(path)
		return ResourceUID.get_id_path(id) if ResourceUID.has_id(id) else ""
	return path
