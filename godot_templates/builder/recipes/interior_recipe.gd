extends RefCounted
## Seeds game/maps/interior_1.tscn once (user_seed ownership) for the starter building.

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const MapUtil := preload("../lib/map_util.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")

const OUT_PATH := "res://game/maps/interior_1.tscn"
const STARTER_MAP := "res://game/maps/starter_map.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const MAP_SIZE := Vector2i(12, 9)

func outputs(ctx) -> PackedStringArray:
	if FileAccess.file_exists(OUT_PATH) or ObjectEntries.starter_building(ctx).is_empty():
		return PackedStringArray()
	return PackedStringArray([OUT_PATH])

func input_hash(ctx) -> String:
	var interior: Dictionary = ctx.catalog.tileset_def("interior")
	var overworld: Dictionary = ctx.catalog.tileset_def("overworld")
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"building": ObjectEntries.starter_building(ctx).get("id", ""),
		"layers": ctx.config.get("map_layers", []),
		"interior": interior,
		"overworld": overworld,
	})

func _tileset_for_interior(ctx) -> Dictionary:
	var interior: Dictionary = ctx.catalog.tileset_def("interior")
	if not interior.is_empty() and ResourceLoader.exists(Paths.TILESETS_DIR + "interior.tres"):
		return interior
	return ctx.catalog.tileset_def("overworld")

func build(ctx) -> Array:
	var issues: Array = []
	if FileAccess.file_exists(OUT_PATH):
		return issues
	var building := ObjectEntries.starter_building(ctx)
	if building.is_empty():
		return issues
	var def := _tileset_for_interior(ctx)
	if def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, OUT_PATH))
		return issues
	var tile_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	var tile_set := load(tile_path) as TileSet
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tile_path}, tile_path))
		return issues
	var tile_px: int = int(def["tile_size"][0])

	var root := MapUtil.new_map_root("Interior1", "interior_1")
	var nodes := MapUtil.build_layers(root, ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS), tile_set)
	var exit_cell := Vector2i(MAP_SIZE.x / 2, MAP_SIZE.y - 1)

	MapUtil.fill(nodes["Ground"], Rect2i(Vector2i.ZERO, MAP_SIZE), MapUtil.find_tile(ctx, def, tile_set, "GROUND"))
	var wall := MapUtil.wall_tile(ctx, def, tile_set)
	if not wall.is_empty() and nodes.has("Walls"):
		MapUtil.border(nodes["Walls"], Rect2i(Vector2i.ZERO, MAP_SIZE), wall, [exit_cell])
	else:
		MapUtil.border_collision(root, MAP_SIZE, tile_px, [exit_cell])

	var spawn_cell := exit_cell + Vector2i(0, -1)
	MapUtil.add_marker(nodes["SpawnPoints"], root, "default", MapUtil.tile_center(spawn_cell, tile_px), true, "up")

	var exit_door := Area2D.new()
	SceneUtil.attach_script(exit_door, MapUtil.DOOR_SCRIPT)
	exit_door.collision_layer = 0
	exit_door.collision_mask = 0
	exit_door.set_collision_layer_value(6, true)  # triggers
	exit_door.set_collision_mask_value(2, true)  # player
	exit_door.position = MapUtil.tile_center(exit_cell, tile_px)
	exit_door.set("target_map", STARTER_MAP)
	exit_door.set("target_spawn", ObjectIndex.exit_spawn_id(building["id"]))
	SceneUtil.add(nodes["Triggers"], exit_door, root, "Exit")
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile_px, tile_px)
	shape.shape = rect
	exit_door.add_child(shape)

	var player := MapUtil.place(PLAYER_SCENE, nodes["Entities"], root, MapUtil.tile_center(spawn_cell, tile_px))
	if player == null:
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		root.free()
		return issues
	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
