extends RefCounted
## Builds one scene per world object under res://generated/scenes/objects/ and the index
## res://rpggen/object_index.json (object id -> scene path).

const RECIPE_VERSION := 3

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")
const ActorBuild := preload("../lib/actor_build.gd")
const BuildContext := preload("../lib/build_context.gd")

const WORLD_OBJECT_SCRIPT := "res://addons/rpg_runtime/world/world_object.gd"
const DOOR_SCRIPT := "res://addons/rpg_runtime/world/door.gd"
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"
const CHEST_SCRIPT := "res://addons/rpg_runtime/world/chest.gd"
const SIGN_SCRIPT := "res://addons/rpg_runtime/world/sign.gd"

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([ObjectIndex.INDEX_PATH])
	for e in ObjectEntries.entries(ctx):
		var scene_id: String = e["id"]
		out.append(ObjectIndex.scene_path(scene_id))
	return out

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "tile": _tile_size(ctx), "entries": ObjectEntries.entries(ctx), "chest": ObjectEntries.chest_entry(ctx).get("id", "")})

func _tile_size(ctx: BuildContext) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return JsonUtil.to_int(def["tile_size"][0]) if not def.is_empty() else JsonUtil.to_int(ctx.config.get("base_tile_size", 16))

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := _tile_size(ctx)
	var index := {}
	var chest: Dictionary = ObjectEntries.chest_entry(ctx)
	for e in ObjectEntries.entries(ctx):
		var entry_id: String = e["id"]
		var path: String = ObjectIndex.scene_path(entry_id)
		var is_chest: bool = chest.get("id", "") == entry_id
		var err := _build_scene(e, path, tile, is_chest, JsonUtil.to_bool(chest.get("fallback", false)))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
		else:
			index[e["id"]] = path
	var write_err := JsonUtil.write(ObjectIndex.INDEX_PATH, index)
	if write_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ObjectIndex.INDEX_PATH, "err": write_err}, ObjectIndex.INDEX_PATH))
	return issues

## "building", "chest", "sign", "obstacle" or "prop" (T4.03 template selection, in order).
func template_for(e: Dictionary, tile: int, is_chest: bool = false) -> String:
	var tags: Array = e["tags"]
	if tags.has("door") or e["role"] == "BUILDING":
		return "building"
	if tags.has("chest") or is_chest:
		return "chest"
	if tags.has("sign"):
		return "sign"
	var coll: Dictionary = e["collision"]
	if coll.get("profile", "NONE") != "NONE":
		return "obstacle"
	if e["role"] == "DECORATION" and ObjectEntries.footprint_area(e) >= 0.5 * tile * tile:
		return "obstacle"
	return "prop"

func _build_scene(e: Dictionary, path: String, tile: int, is_chest: bool = false, chest_fallback: bool = false) -> int:
	var template := template_for(e, tile, is_chest)
	var region: Array = e["region"]
	var entry_id: String = e["id"]
	var texture_path: String = e["texture_path"]
	var door_info: Array = e["door"]
	var origin := Vector2(JsonUtil.to_float(e["origin"][0]), JsonUtil.to_float(e["origin"][1]))
	var solid := template != "prop"
	var root: Node2D
	var solid_body: StaticBody2D = null
	if solid:
		var body := StaticBody2D.new()
		body.collision_layer = 0
		body.collision_mask = 0
		body.set_collision_layer_value(1, true)  # world
		root = body
		solid_body = body
	else:
		root = Node2D.new()
	root.name = JsonUtil.to_str(e["name"]).validate_node_name() if JsonUtil.to_str(e["name"]) != "" else "Object"
	if template == "chest" or template == "sign":
		# Interactable: also on layer 5 so the player's interaction area finds it.
		solid_body.set_collision_layer_value(5, true)
		SceneUtil.attach_script(root, CHEST_SCRIPT if template == "chest" else SIGN_SCRIPT)
		if template == "chest":
			root.name = "Chest"
	else:
		SceneUtil.attach_script(root, WORLD_OBJECT_SCRIPT)
		root.set("asset_id", entry_id)
		root.set("blocks_movement", solid)
	var entry_tags: Array = e["tags"]
	root.set_meta("tags", entry_tags.duplicate())
	if chest_fallback:
		var tags: Array = root.get_meta("tags")
		tags.append("chest_fallback")
		root.set_meta("tags", tags)
	root.set_meta("role", e["role"])

	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = TextureUtil.region_texture(texture_path, Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3])))
	sprite.centered = false
	sprite.offset = -origin
	root.add_child(sprite)
	if template == "chest":
		var open: Array = e.get("open_region", [])
		if open.size() == 4:
			# Frame 0 is the closed chest, the second picture is shown once it is opened.
			sprite.set_meta("open_texture", TextureUtil.region_texture(texture_path, Rect2i(JsonUtil.to_int(open[0]), JsonUtil.to_int(open[1]), JsonUtil.to_int(open[2]), JsonUtil.to_int(open[3]))))

	if solid:
		var shape := CollisionPolygon2D.new()
		shape.name = "Footprint"
		var pts := ObjectEntries.footprint_polygon(e)
		var shifted := PackedVector2Array()
		for p in pts:
			shifted.append(p - origin)
		shape.polygon = shifted
		root.add_child(shape)

	if template == "chest":
		ActorBuild.add_persistent(root)
	if template == "building":
		var door := Vector2(JsonUtil.to_float(region[2]) / 2.0, JsonUtil.to_float(region[3]) - 1.0)
		if door_info.size() == 2:
			door = Vector2(JsonUtil.to_float(door_info[0]), JsonUtil.to_float(door_info[1]))
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
		exit_spawn.set("spawn_id", ObjectIndex.exit_spawn_id(entry_id))
		exit_spawn.set("facing", "down")
		exit_spawn.position = door - origin + Vector2(0, tile)
		root.add_child(exit_spawn)
	return SceneUtil.save_scene(root, path)
