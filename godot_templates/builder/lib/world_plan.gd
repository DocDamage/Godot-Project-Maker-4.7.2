extends RefCounted
## The stored world plan (res://rpggen/world_plan.json, T13.20): the areas of a world, written by
## rpggen from `starter_map.areas`. The recipes only read it: the starter map (the village) gets
## its doors from it, and every other area is built from it by the area recipe.

const JsonUtil := preload("json_util.gd")
const MapUtil := preload("map_util.gd")
const MapBuild := preload("map_build.gd")
const SceneUtil := preload("scene_util.gd")

const PATH := "res://rpggen/world_plan.json"
const VILLAGE_ID := "starter_map"
const GATE_SCRIPT := "res://addons/rpg_runtime/world/gate.gd"
const STEP := {"N": Vector2i(0, -1), "E": Vector2i(1, 0), "S": Vector2i(0, 1), "W": Vector2i(-1, 0)}

## The plan, or {} when the project has none (a project without `starter_map.areas`).
static func read() -> Dictionary:
	if not FileAccess.file_exists(PATH):
		return {}
	return JsonUtil.to_dict(JsonUtil.read(PATH))

static func areas(plan: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(plan.get("areas", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

static func area(plan: Dictionary, area_id: String) -> Dictionary:
	for entry in areas(plan):
		if JsonUtil.to_str(entry.get("id", "")) == area_id:
			return entry
	return {}

static func list_of(entry: Dictionary, key: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(entry.get(key, [])):
		out.append(JsonUtil.to_dict(raw))
	return out

static func cell(value: Variant) -> Vector2i:
	var pair := JsonUtil.to_array(value)
	return Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

static func map_path(entry: Dictionary) -> String:
	return "res://" + JsonUtil.to_str(entry.get("map", ""))

## The floor cell in front of a door in the wall on `edge`.
static func inside(edge: String, door_cell: Vector2i) -> Vector2i:
	var step: Vector2i = STEP.get(edge, Vector2i.ZERO)
	return door_cell - step

## A wall cell on `edge` near `wanted` whose two cells toward the inside are not in `blocked`
## (a Dictionary of Vector2i): the wanted one first, then the cells beside it, further and further.
static func free_edge_cell(wanted: Vector2i, edge: String, size: Vector2i, blocked: Dictionary) -> Vector2i:
	var along := Vector2i(1, 0) if edge in ["N", "S"] else Vector2i(0, 1)
	var limit := size.x if edge in ["N", "S"] else size.y
	for offset in limit:
		for sign: int in [1, -1]:
			var candidate: Vector2i = wanted + along * offset * sign
			var at := candidate.x if edge in ["N", "S"] else candidate.y
			if at < 2 or at > limit - 3:
				continue
			var first := inside(edge, candidate)
			if not blocked.has(first) and not blocked.has(inside(edge, first)):
				return candidate
	return wanted

## One door of the plan in a map: the gap is the caller's (paint_walls' `skip`); this adds the spawn
## point where a player arrives, the door trigger, and the gate when the door needs a key.
static func add_door(door: Dictionary, door_cell: Vector2i, spawn_cell: Vector2i, root: Node2D, nodes: Dictionary, tile_px: int) -> void:
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var spawn_id := JsonUtil.to_str(door.get("spawn_id", ""))
	MapUtil.add_marker(spawns, root, spawn_id, MapUtil.tile_center(spawn_cell, tile_px), true, JsonUtil.to_str(door.get("facing", "down")))
	MapBuild.add_exit_door(triggers, root, JsonUtil.to_str(door.get("id", "")), door_cell, tile_px, "res://" + JsonUtil.to_str(door.get("to_map", "")), StringName(JsonUtil.to_str(door.get("to_spawn", ""))))

## The gate in front of a locked door: on the door's cell, opened for good by the key item (the
## key is kept, so one key opens every gate of its kind).
static func add_gate(gate: Dictionary, door_cell: Vector2i, root: Node2D, entities: Node2D, tile_px: int) -> void:
	var node := StaticBody2D.new()
	SceneUtil.attach_script(node, GATE_SCRIPT)
	var id := JsonUtil.to_str(gate.get("id", ""))
	node.set("entity_id", id)
	node.set("key_item", StringName(JsonUtil.to_str(gate.get("key_item", ""))))
	node.set("consume_key", false)
	node.set("size", Vector2(tile_px, tile_px))
	node.position = Vector2(door_cell.x * tile_px + tile_px / 2.0, (door_cell.y + 1) * tile_px)
	SceneUtil.add(entities, node, root, "Gate_%s" % id.get_slice("_", id.get_slice_count("_") - 1))

## The gate of a door of `entry`, or {}.
static func gate_of(entry: Dictionary, door_id: String) -> Dictionary:
	for gate in list_of(entry, "gates"):
		if JsonUtil.to_str(gate.get("door", "")) == door_id:
			return gate
	return {}
