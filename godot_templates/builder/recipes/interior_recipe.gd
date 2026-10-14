extends RefCounted
## Seeds one interior per house of the starter map (T13.12): game/maps/interior_<n>.tscn for the
## n-th house, once each (user_seed ownership). An interior is as wide as its house (at least 10
## tiles) and 8 tiles deep, with its exit on the bottom wall at the house's door column; leaving
## it returns to the door of that house.
##
## A new project takes the houses from the plan the starter map recipe builds from. A project
## that has a starter map (it is the user's, and may be from 1.0, where every house led to
## interior_1) takes them from that map: an interior is added for each house the map still has,
## and its exit goes to the spawn that house really has.

const RECIPE_VERSION := 3
## The version of what the recipe does for an isometric project only (T17.14): in the hash of
## such a project and of no other.
const ISO_VERSION := 1

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const MapBuild := preload("../lib/map_build.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")
const MapGeo := preload("../lib/map_geo.gd")

const MAPS_DIR := "res://game/maps/"
const OUT_PATH := "res://game/maps/interior_1.tscn"  # the first house's (the only one before 1.1)
const STARTER_MAP := "res://game/maps/starter_map.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const FURNITURE: Array[String] = ["bed", "table"]  # placed when the packs have such an object

static func interior_path(n: int) -> String:
	return "%sinterior_%d.tscn" % [MAPS_DIR, n]

static func interior_id(n: int) -> String:
	return "interior_%d" % n

## The spawn in front of the n-th house's door (n from 1): the building scene's own id for the
## first house, and that id with the number for the others.
static func exit_spawn_for(building_id: String, n: int) -> StringName:
	var base := ObjectIndex.exit_spawn_id(building_id)
	return base if n <= 1 else StringName("%s_%d" % [base, n])

## {size: [w, h], door: [dx, dy]} in tiles of the starter building; {} without one.
static func building_info(building: Dictionary, tile_px: int) -> Dictionary:
	if building.is_empty():
		return {}
	var region: Array = building["region"]
	var door_px := Vector2(JsonUtil.to_float(region[2]) / 2.0, JsonUtil.to_float(region[3]) - 1.0)
	var door_info: Array = building["door"]
	if door_info.size() == 2:
		door_px = Vector2(JsonUtil.to_float(door_info[0]), JsonUtil.to_float(door_info[1]))
	return {
		"size": [ceili(JsonUtil.to_float(region[2]) / tile_px), ceili(JsonUtil.to_float(region[3]) / tile_px)],
		"door": [floori(float(int(door_px.x)) / tile_px), floori(float(int(door_px.y)) / tile_px) + 1],
	}

func _tile_px(ctx: BuildContext) -> int:
	var def := _tileset_for_interior(ctx)
	if def.is_empty():
		return 16
	return JsonUtil.to_int(def["tile_size"][0])

## The houses that get an interior: [{n, spawn}] with the spawn its exit returns to.
func _houses(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var building := ObjectEntries.starter_building(ctx)
	if ctx.demo_removed or building.is_empty():
		return out
	var building_id: String = building["id"]
	if FileAccess.file_exists(STARTER_MAP):
		return _houses_of_map(building_id)
	# a new project: the starter map is built later in this run, from the same plan
	var options: Dictionary = ctx.config.get("starter_map", {})
	var layout := MapBuild.plan(options, JsonUtil.to_int(ctx.config.get("seed", 12345)), MapGeo.new(ctx).building_info(building), JsonUtil.to_str(ctx.config.get("archetype", "turn_based")))
	var planned: Array = layout["interiors"]
	for i in planned.size():
		out.append({"n": i + 1, "spawn": exit_spawn_for(building_id, i + 1)})
	return out

## The houses of the starter map that exists, in the order of the scene: each instance of the
## building scene, with the id of the exit spawn it really has.
func _houses_of_map(building_id: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var packed := load(STARTER_MAP) as PackedScene
	if packed == null:
		return out
	var map := packed.instantiate()
	if map == null:
		return out
	var scene_path := ObjectIndex.scene_path(building_id)
	var found: Array[Node] = []
	_collect_instances(map, scene_path, found)
	for i in found.size():
		var spawn_node := found[i].get_node_or_null("ExitSpawn")
		var spawn := exit_spawn_for(building_id, 1)
		if spawn_node != null and spawn_node.get("spawn_id") != null:
			spawn = StringName(JsonUtil.to_str(spawn_node.get("spawn_id")))
		out.append({"n": i + 1, "spawn": spawn})
	map.free()
	return out

func _collect_instances(node: Node, scene_path: String, out: Array[Node]) -> void:
	if node.scene_file_path == scene_path:
		out.append(node)
		return
	for child in node.get_children():
		_collect_instances(child, scene_path, out)

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for house in _houses(ctx):
		var path := interior_path(JsonUtil.to_int(house["n"]))
		if not FileAccess.file_exists(path):
			out.append(path)
	return out

func input_hash(ctx: BuildContext) -> String:
	var interior: Dictionary = ctx.catalog.tileset_def("interior")
	var overworld: Dictionary = ctx.catalog.tileset_def("overworld")
	var hashed := {
		"v": RECIPE_VERSION,
		"building": ObjectEntries.starter_building(ctx).get("id", ""),
		"houses": _houses(ctx),
		"layers": ctx.config.get("map_layers", []),
		"interior": interior,
		"overworld": overworld,
	}
	if MapGeo.is_isometric(ctx):  # only an isometric project's hash has the keys (T17.14)
		hashed["iso"] = MapGeo.new(ctx).def
		hashed["iso_v"] = ISO_VERSION
		hashed.merge(MapGeo.edge_hash(ctx))  # T17.22: only with walls along a side
	return ctx.stable_hash(hashed)

func _tileset_for_interior(ctx: BuildContext) -> Dictionary:
	var interior: Dictionary = ctx.catalog.tileset_def("interior")
	if not interior.is_empty() and ResourceLoader.exists(Paths.TILESETS_DIR + "interior.tres"):
		return interior
	return ctx.catalog.tileset_def("overworld")

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var houses := _houses(ctx)
	if houses.is_empty():
		return issues
	var building := ObjectEntries.starter_building(ctx)
	var def := _tileset_for_interior(ctx)
	# the seam between the room's cells and its px (T17.14): an isometric project's rooms are
	# painted with its tile set of diamonds (the same ground as outside: the packs that were
	# listed have no floor of their own), every other project's with the interior tile set
	var geo := MapGeo.new(ctx, JsonUtil.to_str(def.get("name", "")))
	if geo.def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, OUT_PATH))
		return issues
	var tile_path := geo.tileset_path()
	var tile_set := geo.load_tile_set()
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tile_path}, tile_path))
		return issues
	var tile_px := geo.tile_px
	var overworld: Dictionary = ctx.catalog.tileset_def("overworld")
	var world_px := tile_px if overworld.is_empty() else JsonUtil.to_int(overworld["tile_size"][0])
	# the planner says how large an interior is and where its exit is (the preview counts them)
	var house_info := geo.building_info(building) if geo.isometric else building_info(building, world_px)
	var spec: Dictionary = MapBuild.interiors_for(1, house_info)[0]
	var size := Vector2i(JsonUtil.to_int(spec["size"][0]), JsonUtil.to_int(spec["size"][1]))
	var exit_cell := Vector2i(JsonUtil.to_int(spec["door"]), size.y - 1)
	for house in houses:
		var n := JsonUtil.to_int(house["n"])
		var path := interior_path(n)
		if FileAccess.file_exists(path):
			continue  # the user's by now: never rewritten
		_build_one(ctx, issues, n, path, StringName(JsonUtil.to_str(house["spawn"])), geo, tile_set, size, exit_cell)
	return issues

func _build_one(ctx: BuildContext, issues: Array, n: int, path: String, exit_spawn: StringName, geo: MapGeo, tile_set: TileSet, size: Vector2i, exit_cell: Vector2i) -> void:
	var root := MapUtil.new_map_root("Interior%d" % n, interior_id(n))
	root.set("is_interior", true)  # a dimmer ambient (T12.62)
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var ground: TileMapLayer = nodes["Ground"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var entities: Node2D = nodes["Entities"]

	MapUtil.fill(ground, Rect2i(Vector2i.ZERO, size), geo.find_tile("GROUND"))
	var wall := geo.wall_tile()
	if geo.isometric:
		geo.paint_walls(root, nodes, size, [exit_cell])
	elif not wall.is_empty() and nodes.has("Walls"):
		var walls: TileMapLayer = nodes["Walls"]
		MapUtil.border(walls, Rect2i(Vector2i.ZERO, size), wall, [exit_cell])
	else:
		geo.border_collision(root, size, [exit_cell])

	var spawn_cell := exit_cell + Vector2i(0, -1)
	MapUtil.add_marker(spawns, root, "default", geo.center(spawn_cell), true, "up")

	var exit_door := Area2D.new()
	SceneUtil.attach_script(exit_door, MapUtil.DOOR_SCRIPT)
	exit_door.collision_layer = 0
	exit_door.collision_mask = 0
	exit_door.set_collision_layer_value(6, true)  # triggers
	exit_door.set_collision_mask_value(2, true)  # player
	exit_door.position = geo.center(exit_cell)
	exit_door.set("target_map", STARTER_MAP)
	exit_door.set("target_spawn", exit_spawn)
	SceneUtil.add(triggers, exit_door, root, "Exit")
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	shape.shape = geo.cell_shape()
	exit_door.add_child(shape)

	_place_furniture(ctx, root, entities, geo, size, exit_cell)
	var player := MapUtil.place(PLAYER_SCENE, entities, root, geo.center(spawn_cell))
	if player == null:
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		root.free()
		return
	var err := SceneUtil.save_scene(root, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## A bed in the top-left corner and a table in the top-right one, when the packs have an object
## whose name says so (a pack without them gives an empty room).
func _place_furniture(ctx: BuildContext, root: Node2D, entities: Node2D, geo: MapGeo, size: Vector2i, exit_cell: Vector2i) -> void:
	var cells := {"bed": Vector2i(2, 2), "table": Vector2i(size.x - 3, 2)}
	for word in FURNITURE:
		var entry := furniture_entry(ObjectEntries.entries(ctx), word)
		if entry.is_empty():
			continue
		var entry_id: String = entry["id"]
		var scene := ObjectIndex.scene_path(entry_id)
		var cell: Vector2i = cells[word]
		if not ResourceLoader.exists(scene) or cell.x == exit_cell.x:
			continue
		MapUtil.place(scene, entities, root, geo.bottom(cell), word.capitalize())

## The first object entry (not the starter building, not a character) whose name or tags say
## `word`; {} when the packs have none.
static func furniture_entry(entries: Array, word: String) -> Dictionary:
	for raw: Variant in entries:
		var entry: Dictionary = raw
		if JsonUtil.to_str(entry.get("role", "")) == "BUILDING":
			continue
		var tags: Array = entry.get("tags", [])
		if JsonUtil.to_str(entry.get("name", "")).to_lower().contains(word) or tags.has(word):
			return entry
	return {}
