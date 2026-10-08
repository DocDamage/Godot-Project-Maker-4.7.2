@tool
extends RefCounted
## Entity ids (<map_id>_<kind>_<nnn>) of the nodes in a map: reading, allocating, repairing.

const JsonIo := preload("json_io.gd")

const PERSISTENT_SUFFIX := "/world/persistent.gd"

## True for nodes that carry an `entity_id` property (world objects, actors, chests, doors ...).
## The RpgPersistent component has one too, but it only mirrors its parent's.
static func has_entity_id(node: Node) -> bool:
	var script: Script = node.get_script()
	if script != null and script.resource_path.ends_with(PERSISTENT_SUFFIX):
		return false
	return node.get("entity_id") != null

## True when the node's state is saved by id: it has an RpgPersistent child. Props with an empty
## entity_id are not persistent and need no id.
static func is_persistent(node: Node) -> bool:
	for child in node.get_children():
		var script: Script = child.get_script()
		if script != null and script.resource_path.ends_with(PERSISTENT_SUFFIX):
			return true
	return false

## Every node below `root` (root included) with an entity_id property, in tree order. Nodes inside
## an instanced scene are included.
static func entity_nodes(root: Node) -> Array[Node]:
	var out: Array[Node] = []
	_collect(root, out)
	return out

static func _collect(node: Node, out: Array) -> void:
	if has_entity_id(node):
		out.append(node)
	for child in node.get_children():
		_collect(child, out)

## The map id of a map scene: the root's `map_id`, else its snake-cased name.
static func map_id_of(root: Node) -> String:
	var id := str(root.get("map_id")) if root.get("map_id") != null else ""
	if id != "":
		return id
	return String(root.name).to_snake_case()

## The id kind of a library entry: chest and sign by tag, else the lower-cased role.
static func kind_of(role: String, tags: Array) -> String:
	if tags.has("chest"):
		return "chest"
	if tags.has("sign"):
		return "sign"
	var kind := role.to_lower()
	return kind if kind != "" else "object"

static func make_id(map_id: String, kind: String, number: int) -> String:
	return "%s_%s_%03d" % [map_id, kind, number]

## The number of an id of the form <map_id>_<kind>_<digits>, or -1.
static func number_of(id: String, map_id: String, kind: String) -> int:
	var prefix := "%s_%s_" % [map_id, kind]
	if not id.begins_with(prefix):
		return -1
	var tail := id.substr(prefix.length())
	return int(tail) if tail.is_valid_int() and not tail.begins_with("-") and not tail.begins_with("+") else -1

## 1 + the highest number among `ids` for this kind (1 when there is none). `ids` are the ids
## already in the map, so a stale catalog allocation cannot produce a duplicate.
static func next_number(ids: Array, map_id: String, kind: String) -> int:
	var highest := 0
	for id: Variant in ids:
		highest = maxi(highest, number_of(JsonIo.to_str(id), map_id, kind))
	return highest + 1

## The kind to use for a node already in a map (a node without a known kind gets its script-less
## class-name based kind "entity"): the kind of its current id when it has one, else from the
## node's `role` meta or its scene name.
static func kind_of_node(node: Node, map_id: String) -> String:
	if node.has_meta("tags") or node.has_meta("role"):
		var tags: Array = node.get_meta("tags", [])
		var role := str(node.get_meta("role", ""))
		if tags.has("chest") or tags.has("sign") or role != "":
			return kind_of(role, tags)
	var script: Script = node.get_script()
	if script != null:
		var base := script.resource_path.get_file().get_basename()
		if base in ["npc", "chest", "sign", "overworld_enemy"]:
			return "enemy" if base == "overworld_enemy" else base
	var existing := str(node.get("entity_id"))
	if existing.begins_with(map_id + "_"):
		var tail := existing.substr(map_id.length() + 1)
		var cut := tail.rfind("_")
		if cut > 0:
			return tail.substr(0, cut)
	return "entity"

## Result of fix_ids: {changes: [{node, old, new}], allocations: {kind: last number}}.
## Assigns ids to persistent nodes with an empty id and renames the later one of every duplicate
## pair. Nothing is changed in the scene: the caller applies `changes` (with undo).
## `elsewhere` holds ids used by other maps (id -> true): they count as taken, so a node here that
## carries one of them is a duplicate too.
static func plan_fixes(root: Node, elsewhere: Dictionary = {}) -> Dictionary:
	var map_id := map_id_of(root)
	var nodes := entity_nodes(root)
	var taken: Array = elsewhere.keys()
	for n in nodes:
		var id := str(n.get("entity_id"))
		if id != "":
			taken.append(id)
	var seen := elsewhere.duplicate()
	var changes: Array = []
	var allocations := {}
	for n in nodes:
		var old := str(n.get("entity_id"))
		var needs := false
		if old == "":
			needs = is_persistent(n)
		elif seen.has(old):
			needs = true
		else:
			seen[old] = true
		if not needs:
			continue
		var kind := kind_of_node(n, map_id)
		var number := next_number(taken, map_id, kind)
		var new_id := make_id(map_id, kind, number)
		taken.append(new_id)
		seen[new_id] = true
		allocations[kind] = maxi(JsonIo.to_int(allocations.get(kind, 0)), number)
		changes.append({"node": n, "old": old, "new": new_id})
	return {"changes": changes, "allocations": allocations}
