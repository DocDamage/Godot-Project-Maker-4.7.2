extends RefCounted
## Builds one scene per world object under res://generated/scenes/objects/ and the index
## res://rpggen/object_index.json (object id -> scene path).

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const Geometry := preload("../lib/geometry.gd")
const JsonUtil := preload("../lib/json_util.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")

const WORLD_OBJECT_SCRIPT := "res://addons/rpg_runtime/world/world_object.gd"
const DOOR_SCRIPT := "res://addons/rpg_runtime/world/door.gd"
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"

func outputs(ctx) -> PackedStringArray:
	var out := PackedStringArray([ObjectIndex.INDEX_PATH])
	for e in ObjectEntries.entries(ctx):
		out.append(ObjectIndex.scene_path(e["id"]))
	return out

func input_hash(ctx) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "tile": _tile_size(ctx), "entries": ObjectEntries.entries(ctx)})

func _tile_size(ctx) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return int(def["tile_size"][0]) if not def.is_empty() else int(ctx.config.get("base_tile_size", 16))

func build(ctx) -> Array:
	var issues: Array = []
	var tile := _tile_size(ctx)
	var index := {}
	for e in ObjectEntries.entries(ctx):
		var path: String = ObjectIndex.scene_path(e["id"])
		var err := _build_scene(e, path, tile)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
		else:
			index[e["id"]] = path
	var write_err := JsonUtil.write(ObjectIndex.INDEX_PATH, index)
	if write_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ObjectIndex.INDEX_PATH, "err": write_err}, ObjectIndex.INDEX_PATH))
	return issues

## "building", "chest", "sign", "obstacle" or "prop" (T4.03 template selection, in order).
func template_for(e: Dictionary, tile: int) -> String:
	var tags: Array = e["tags"]
	if tags.has("door") or e["role"] == "BUILDING":
		return "building"
	if tags.has("chest"):
		return "chest"
	if tags.has("sign"):
		return "sign"
	if e["collision"].get("profile", "NONE") != "NONE":
		return "obstacle"
	if e["role"] == "DECORATION" and ObjectEntries.footprint_area(e, Geometry) >= 0.5 * tile * tile:
		return "obstacle"
	return "prop"

func _build_scene(e: Dictionary, path: String, tile: int) -> int:
	var template := template_for(e, tile)
	var region: Array = e["region"]
	var origin := Vector2(float(e["origin"][0]), float(e["origin"][1]))
	var solid := template != "prop"
	var root: Node2D
	if solid:
		var body := StaticBody2D.new()
		body.collision_layer = 0
		body.collision_mask = 0
		body.set_collision_layer_value(1, true)  # world
		root = body
	else:
		root = Node2D.new()
	root.name = String(e["name"]).validate_node_name() if String(e["name"]) != "" else "Object"
	SceneUtil.attach_script(root, WORLD_OBJECT_SCRIPT)
	root.set("asset_id", e["id"])
	root.set("blocks_movement", solid)
	root.set_meta("tags", e["tags"].duplicate())
	root.set_meta("role", e["role"])

	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = TextureUtil.region_texture(e["texture_path"], Rect2i(int(region[0]), int(region[1]), int(region[2]), int(region[3])))
	sprite.centered = false
	sprite.offset = -origin
	root.add_child(sprite)

	if solid:
		var shape := CollisionPolygon2D.new()
		shape.name = "Footprint"
		var pts := ObjectEntries.footprint_polygon(e, Geometry)
		var shifted := PackedVector2Array()
		for p in pts:
			shifted.append(p - origin)
		shape.polygon = shifted
		root.add_child(shape)

	if template == "building":
		var door := Vector2(float(region[2]) / 2.0, float(region[3]) - 1.0)
		if e["door"].size() == 2:
			door = Vector2(float(e["door"][0]), float(e["door"][1]))
		else:
			var tags: Array = root.get_meta("tags")
			tags.append("door_assumed")
			root.set_meta("tags", tags)
		var entrance := Area2D.new()
		entrance.name = "Entrance"
		SceneUtil.attach_script(entrance, DOOR_SCRIPT)
		entrance.collision_layer = 0
		entrance.collision_mask = 0
		entrance.set_collision_layer_value(6, true)  # triggers
		entrance.set_collision_mask_value(2, true)  # player
		entrance.position = door - origin + Vector2(0, 4)
		root.add_child(entrance)
		var area_shape := CollisionShape2D.new()
		area_shape.name = "Shape"
		var rect := RectangleShape2D.new()
		rect.size = Vector2(tile * 0.75, tile * 0.5)
		area_shape.shape = rect
		entrance.add_child(area_shape)
		var exit_spawn := Marker2D.new()
		exit_spawn.name = "ExitSpawn"
		SceneUtil.attach_script(exit_spawn, SPAWN_SCRIPT)
		exit_spawn.set("spawn_id", ObjectIndex.exit_spawn_id(e["id"]))
		exit_spawn.set("facing", "down")
		exit_spawn.position = door - origin + Vector2(0, tile)
		root.add_child(exit_spawn)
	return SceneUtil.save_scene(root, path)
