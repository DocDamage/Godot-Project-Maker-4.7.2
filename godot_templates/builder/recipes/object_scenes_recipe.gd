extends RefCounted
## Builds one scene per world object under res://generated/scenes/objects/ and the index
## res://rpggen/object_index.json (object id -> scene path).

const RECIPE_VERSION := 4

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const ObjectEntries := preload("../lib/object_entries.gd")
const ObjectIndex := preload("../lib/object_index.gd")
const ActorBuild := preload("../lib/actor_build.gd")
const BuildContext := preload("../lib/build_context.gd")
const MapGeo := preload("../lib/map_geo.gd")
const IsoHouse := preload("../lib/iso_house.gd")
const SideTileset := preload("../lib/side_tileset.gd")

const WORLD_OBJECT_SCRIPT := "res://addons/rpg_runtime/world/world_object.gd"
const DOOR_SCRIPT := "res://addons/rpg_runtime/world/door.gd"
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"
const CHEST_SCRIPT := "res://addons/rpg_runtime/world/chest.gd"
const SIGN_SCRIPT := "res://addons/rpg_runtime/world/sign.gd"
const LIGHT_SCRIPT := "res://addons/rpg_runtime/world/light_source.gd"
const LightingRecipe := preload("lighting_recipe.gd")
## Names that are lamps (a steady light); every other light is a flame and flickers.
const STEADY_LIGHT_WORDS: Array[String] = ["lamp", "lantern"]
const LIGHT_COLOR := Color(1.0, 0.82, 0.55)

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([ObjectIndex.INDEX_PATH])
	for e in ObjectEntries.entries(ctx):
		var scene_id: String = e["id"]
		out.append(ObjectIndex.scene_path(scene_id))
	return out

func input_hash(ctx: BuildContext) -> String:
	var hashed := {"v": RECIPE_VERSION, "tile": _tile_size(ctx), "entries": ObjectEntries.entries(ctx), "chest": ObjectEntries.chest_entry(ctx).get("id", "")}
	if _side_view(ctx):
		hashed["side_view"] = true  # only a metroidvania's hash has the key
	return ctx.stable_hash(hashed)

## A metroidvania's rooms are seen from the side (T14.04): nothing blocks the way but the tiles,
## and chests and signs are used from beside them.
static func _side_view(ctx: BuildContext) -> bool:
	return SideTileset.side_view(ctx.config)

func _tile_size(ctx: BuildContext) -> int:
	return MapGeo.tile_unit(ctx)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := _tile_size(ctx)
	var index := {}
	var chest: Dictionary = ObjectEntries.chest_entry(ctx)
	for e in ObjectEntries.entries(ctx):
		var entry_id: String = e["id"]
		var path: String = ObjectIndex.scene_path(entry_id)
		var is_chest: bool = chest.get("id", "") == entry_id
		var err := _build_scene(e, path, tile, is_chest, JsonUtil.to_bool(chest.get("fallback", false)), _side_view(ctx))
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

## A light (T12.62) near the top of the picture, as wide as four tiles, with the texture the
## lighting recipe generated; a flame flickers, a lamp does not.
static func add_light(root: Node2D, e: Dictionary, tile: int, origin: Vector2) -> void:
	var region: Array = e["region"]
	var light := PointLight2D.new()
	light.name = "Light"
	SceneUtil.attach_script(light, LIGHT_SCRIPT)
	# the lighting recipe's texture; an embedded copy when it is not there (tests)
	if ResourceLoader.exists(LightingRecipe.TEXTURE_PATH):
		light.texture = load(LightingRecipe.TEXTURE_PATH) as Texture2D
	else:
		light.texture = LightingRecipe.make_texture()
	light.texture_scale = tile * 4.0 / LightingRecipe.SIZE
	light.color = LIGHT_COLOR
	light.position = Vector2(JsonUtil.to_float(region[2]) / 2.0, JsonUtil.to_float(region[3]) * 0.3) - origin
	var name_text := JsonUtil.to_str(e["name"]).to_lower() + " " + JsonUtil.to_str(e["id"]).to_lower()
	var steady := false
	for word in STEADY_LIGHT_WORDS:
		if name_text.contains(word):
			steady = true
	light.set("flicker", not steady)
	root.add_child(light)

func _build_scene(e: Dictionary, path: String, tile: int, is_chest: bool = false, chest_fallback: bool = false, side_view: bool = false) -> int:
	var template := template_for(e, tile, is_chest)
	if side_view and template == "obstacle":
		template = "prop"  # scenery of a side-view room stands in front of the wall, not in the way
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
		if side_view:
			solid_body.set_collision_layer_value(1, false)  # found by the player, in nobody's way
			root.set("side_view", true)
			root.set("tile_size", float(tile))
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
	if ObjectEntries.is_iso(e):
		# drawn for the isometric view: its origin is the middle of the diamond it stands on
		# (the validation and the smoke steps ask), and `stands_on` the cells
		root.set_meta("iso", JsonUtil.to_array(e["iso"]).duplicate())
		root.set_meta("stands_on", JsonUtil.to_array(e["stands_on"]).duplicate())

	var sprite: Sprite2D = null
	if IsoHouse.is_kit(e):
		# a house of pieces (T17.22): no picture of its own, a sprite a wall and a roof, in the
		# two halves an isometric building sorts by
		root.set_meta("kit", JsonUtil.to_dict(e["kit"]).duplicate())
		IsoHouse.assemble(root, JsonUtil.to_array(e["parts"]), ObjectEntries.iso_cells(e), ObjectEntries.iso_footprint(e))
	elif _frames_of(e) != null:
		# a thing that moves (an assets-only project, 2026-10-26: a fountain, a campfire, an
		# arrow): it plays its animation where it stands
		var playing := AnimatedSprite2D.new()
		playing.name = "Sprite"
		playing.sprite_frames = _frames_of(e)
		playing.animation = JsonUtil.to_str(e["animation"])
		playing.autoplay = JsonUtil.to_str(e["animation"])
		playing.centered = false
		playing.offset = -origin
		root.add_child(playing)
	else:
		sprite = Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = TextureUtil.region_texture(texture_path, Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3])))
		sprite.centered = false
		sprite.offset = -origin
		root.add_child(sprite)
		if ObjectEntries.is_iso(e) and ObjectEntries.iso_cells(e) != Vector2i.ONE:
			_split_for_sorting(root, sprite, e, origin)
	if e.has("shadow"):
		# the pack's shadow under the thing, drawn with the same anchor (2026-10-26)
		ActorBuild.add_shadow(root, {"shadow": e["shadow"]}, -origin, true)
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

	var light_tags: Array = e["tags"]
	if light_tags.has("light"):
		add_light(root, e, tile, origin)
	if template == "chest":
		ActorBuild.add_persistent(root)
	if template == "building" and ObjectEntries.is_iso(e):
		_add_iso_door(root, e, tile)
	elif template == "building":
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

## The SpriteFrames of an entry of a thing that moves (`frames_path`, ObjectEntries), or null.
static func _frames_of(e: Dictionary) -> SpriteFrames:
	var path := JsonUtil.to_str(e.get("frames_path", ""))
	if path == "" or not ResourceLoader.exists(path):
		return null
	return load(path) as SpriteFrames

# ---------------------------------------------------------------- isometric objects (T17.14)

## An isometric object that stands on several cells is drawn in two halves that sort apart:
## they meet at the x of its corner nearest the camera (the x of its origin), the left one sorts
## by the y of the left corner of what it stands on and the right one by the y of the right
## corner (RpgIso.sort_keys). The root sorts its children among the actors of the map, so an
## actor north or west of the object is drawn before the half it stands behind and one south or
## east of it after. On a square of cells the two lines are one and the picture stays whole.
static func _split_for_sorting(root: Node2D, sprite: Sprite2D, e: Dictionary, origin: Vector2) -> void:
	var cells := ObjectEntries.iso_cells(e)
	var footprint := ObjectEntries.iso_footprint(e)
	var region: Array = e["region"]
	var texture_path: String = e["texture_path"]
	var area := Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3]))
	# the keys of the two halves from the middle of the nearest cell, where the root stands
	var left_y := (1 - cells.x) * footprint.y / 2.0
	var right_y := (1 - cells.y) * footprint.y / 2.0
	root.y_sort_enabled = true
	var cut := clampi(roundi(origin.x), 0, area.size.x)
	sprite.position = Vector2(0, left_y)
	sprite.offset = -origin - sprite.position
	if cells.x == cells.y or cut <= 0 or cut >= area.size.x:
		return
	sprite.texture = TextureUtil.region_texture(texture_path, Rect2i(area.position, Vector2i(cut, area.size.y)))
	var right := Sprite2D.new()
	right.name = "SpriteRight"
	right.texture = TextureUtil.region_texture(texture_path, Rect2i(area.position + Vector2i(cut, 0), Vector2i(area.size.x - cut, area.size.y)))
	right.centered = false
	right.position = Vector2(0, right_y)
	right.offset = Vector2(cut, 0) - origin - right.position
	root.add_child(right)

## The door of an isometric building: on the side that faces the camera to the left, the south
## side by the grid, in front of the door cell of the plan. The trigger is a thin band along
## that side of the diamond (walking against it anywhere near its middle enters), and who comes
## out stands on the middle of the door cell.
static func _add_iso_door(root: Node2D, e: Dictionary, tile: int) -> void:
	var cells := ObjectEntries.iso_cells(e)
	var footprint := ObjectEntries.iso_footprint(e)
	var half := Vector2(footprint) / 2.0
	# the column of the door from the cell nearest the camera, which is where the root stands
	@warning_ignore("integer_division")
	var column := float((cells.x - 1) / 2 - (cells.x - 1))
	var south := Vector2(-half.x, half.y).normalized()
	var entrance := Area2D.new()
	entrance.name = "Entrance"
	SceneUtil.attach_script(entrance, DOOR_SCRIPT)
	entrance.collision_layer = 0
	entrance.collision_mask = 0
	entrance.set_collision_layer_value(6, true)  # triggers
	entrance.set_collision_mask_value(2, true)  # player
	entrance.position = Vector2((column - 0.5) * half.x, (column + 0.5) * half.y) + south * 2.0
	root.add_child(entrance)
	var area_shape := CollisionShape2D.new()
	area_shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile * 0.6, 6.0)
	area_shape.shape = rect
	area_shape.rotation = Vector2(half.x, half.y).angle()
	entrance.add_child(area_shape)
	var exit_spawn := Marker2D.new()
	exit_spawn.name = "ExitSpawn"
	SceneUtil.attach_script(exit_spawn, SPAWN_SCRIPT)
	exit_spawn.set("spawn_id", ObjectIndex.exit_spawn_id(JsonUtil.to_str(e["id"])))
	exit_spawn.set("facing", "down")
	exit_spawn.position = Vector2((column - 1.0) * half.x, (column + 1.0) * half.y)
	root.add_child(exit_spawn)
