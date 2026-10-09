extends RefCounted
## The scenes of a side-view room that are not characters: the room camera, a pickup for every
## ability and the item pickups (and, from T14.08, the save station). Rooms instance them, and
## they are in the editor's dock like every generated scene.

const RECIPE_VERSION := 2

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const TextureUtil := preload("../../lib/texture_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MvBuild := preload("metroidvania_build.gd")

const OUT_DIR := "res://generated/scenes/metroidvania/"
const CAMERA_PATH := OUT_DIR + "side_camera.tscn"
const CAMERA_SCRIPT := MvBuild.DIR + "side_camera.gd"
const ABILITY_SCRIPT := MvBuild.DIR + "ability_pickup.gd"
const ITEM_SCRIPT := MvBuild.DIR + "item_pickup.gd"
const STATION_PATH := OUT_DIR + "save_station.tscn"
const STATION_SCRIPT := MvBuild.DIR + "save_station.gd"
## The abilities, as in RpgAbilities.ORDER (the builder cannot name a class of the runtime folder
## of one archetype from a shared place, but this recipe is the metroidvania's own).
const ABILITIES: Array[String] = ["double_jump", "dash", "wall_jump", "high_jump", "break_blocks"]
## The item pickups: [scene name, item id, quantity, gold, words that name its art].
const ITEMS: Array[Array] = [
	["item_potion", "potion", 1, 0, ["potion", "heart", "health"]],
	["item_coin", "", 0, 5, ["coin", "gold", "gem", "money"]],
]

static func ability_scene(ability: String) -> String:
	return OUT_DIR + "ability_%s.tscn" % ability

static func item_scene(index: int) -> String:
	return OUT_DIR + "%s.tscn" % JsonUtil.to_str(ITEMS[index % ITEMS.size()][0])

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([CAMERA_PATH, STATION_PATH])
	for ability in ABILITIES:
		out.append(ability_scene(ability))
	for i in ITEMS.size():
		out.append(item_scene(i))
	return out

func input_hash(ctx: BuildContext) -> String:
	var art: Array = []
	for ability in ABILITIES:
		art.append(_art(ctx, ["ability"], [ability, ability.replace("_", "")]).get("id", ""))
	for entry: Array in ITEMS:
		var words: Array = entry[4]
		art.append(_art(ctx, [], words).get("id", ""))
	return ctx.stable_hash({"v": RECIPE_VERSION, "tile": tile_size(ctx), "art": art, "station": _station_art(ctx).get("id", "")})

## The art of the save station: a sprite tagged `save_point` (a bench, a checkpoint), of any role.
static func _station_art(ctx: BuildContext) -> Dictionary:
	for a in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(a)
		if a.get("status", "") in ["UNUSED", "MISSING"] or eff.get("usage", "") != "sprite":
			continue
		if JsonUtil.to_array(eff.get("tags", [])).has("save_point"):
			return a
	return {}

## The save station (RpgSaveStation): the pack's bench, or a drawn one without art. The area is
## two tiles wide, so the player finds it from either side.
static func build_station(ctx: BuildContext, tile: int) -> Area2D:
	var area := Area2D.new()
	area.name = "SaveStation"
	SceneUtil.attach_script(area, STATION_SCRIPT)
	area.set("tile_size", float(tile))
	MvBuild.set_layers(area, [5], [])
	area.monitoring = false
	var shape := MvBuild.rect_shape(Vector2(tile * 2.0, tile))
	shape.position = Vector2(0.0, -tile * 0.5)
	area.add_child(shape)
	var art := _station_art(ctx)
	var texture := _texture(ctx, art)
	if texture != null:
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = texture
		sprite.centered = false
		sprite.position = Vector2(-texture.get_width() * 0.5, -texture.get_height())
		area.add_child(sprite)
	else:
		var bench := Polygon2D.new()
		bench.name = "Sprite"
		bench.color = Color(0.61, 0.42, 0.24)
		var w := tile * 0.9
		bench.polygon = PackedVector2Array([Vector2(-w, -tile * 0.5), Vector2(w, -tile * 0.5), Vector2(w, -tile * 0.3), Vector2(w * 0.8, -tile * 0.3), Vector2(w * 0.8, 0), Vector2(w * 0.6, 0), Vector2(w * 0.6, -tile * 0.3), Vector2(-w * 0.6, -tile * 0.3), Vector2(-w * 0.6, 0), Vector2(-w * 0.8, 0), Vector2(-w * 0.8, -tile * 0.3), Vector2(-w, -tile * 0.3)])
		area.add_child(bench)
	return area

static func tile_size(ctx: BuildContext) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return JsonUtil.to_int(def["tile_size"][0]) if not def.is_empty() else JsonUtil.to_int(ctx.config.get("base_tile_size", 16))

## The camera a room owns (RpgSideCamera), enabled, not yet in a room.
static func build_camera(tile: int) -> Camera2D:
	var camera := Camera2D.new()
	camera.name = "Camera"
	SceneUtil.attach_script(camera, CAMERA_SCRIPT)
	camera.set("tile_size", float(tile))
	camera.enabled = true
	return camera

## The ITEM sprite that shows a thing: one with every tag of `tags` whose name has one of
## `words`; with `tags`, else any asset with those tags. {} when the packs have none.
static func _art(ctx: BuildContext, tags: Array, words: Array) -> Dictionary:
	var tagged: Dictionary = {}
	for a in ctx.catalog.assets_by_role("ITEM"):
		var eff: Dictionary = ctx.catalog.effective(a)
		if a.get("status", "") in ["UNUSED", "MISSING"] or eff.get("usage", "") != "sprite":
			continue
		var asset_tags := JsonUtil.to_array(eff.get("tags", []))
		var has_tags := true
		for tag: Variant in tags:
			if not asset_tags.has(tag):
				has_tags = false
		if not has_tags:
			continue
		var name_text := JsonUtil.to_str(a["id"]).to_lower()
		for word: Variant in words:
			if name_text.contains(JsonUtil.to_str(word)):
				return a
		if tagged.is_empty() and not tags.is_empty():
			tagged = a
	return tagged

## The first frame of a sprite asset as a texture, or null.
static func _texture(ctx: BuildContext, asset: Dictionary) -> Texture2D:
	if asset.is_empty():
		return null
	var eff: Dictionary = ctx.catalog.effective(asset)
	var size: Array = eff.get("frame", eff.get("size", [16, 16]))
	return TextureUtil.region_texture("res://" + JsonUtil.to_str(asset["path"]), Rect2i(0, 0, JsonUtil.to_int(size[0]), JsonUtil.to_int(size[1])))

## An Area2D on the interactables layer that looks for the player, a tile large, standing on its
## origin, with a sprite (a null texture is drawn at run time).
static func _pickup_node(node_name: String, script_path: String, texture: Texture2D, tile: int) -> Area2D:
	var area := Area2D.new()
	area.name = node_name
	SceneUtil.attach_script(area, script_path)
	area.set("tile_size", float(tile))
	MvBuild.set_layers(area, [5], [2])
	var shape := MvBuild.rect_shape(Vector2(tile, tile) * 0.8)
	shape.position = Vector2(0.0, -tile * 0.5)
	area.add_child(shape)
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = texture
	sprite.position = Vector2(0.0, -tile * 0.5)
	area.add_child(sprite)
	return area

## The pickup of one ability: the pack's art for it (an ITEM tagged `ability`, by name when
## several) or a generated glyph.
static func build_ability(ctx: BuildContext, ability: String, tile: int) -> Area2D:
	var art := _art(ctx, ["ability"], [ability, ability.replace("_", "")])
	var area := _pickup_node("Ability", ABILITY_SCRIPT, _texture(ctx, art), tile)
	area.set("ability", StringName(ability))
	return area

## An item pickup of ITEMS, remembered by RpgPersistent once it is collected.
static func build_item(ctx: BuildContext, index: int, tile: int) -> Area2D:
	var entry: Array = ITEMS[index % ITEMS.size()]
	var words: Array = entry[4]
	var area := _pickup_node("Item", ITEM_SCRIPT, _texture(ctx, _art(ctx, [], words)), tile)
	area.set("item_id", StringName(JsonUtil.to_str(entry[1])))
	area.set("qty", JsonUtil.to_int(entry[2]))
	area.set("gold", JsonUtil.to_int(entry[3]))
	ActorBuild.add_persistent(area)
	return area

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := tile_size(ctx)
	_save(ctx, build_camera(tile), CAMERA_PATH, issues)
	_save(ctx, build_station(ctx, tile), STATION_PATH, issues)
	for ability in ABILITIES:
		_save(ctx, build_ability(ctx, ability, tile), ability_scene(ability), issues)
	for i in ITEMS.size():
		_save(ctx, build_item(ctx, i, tile), item_scene(i), issues)
	return issues

func _save(ctx: BuildContext, node: Node, path: String, issues: Array) -> void:
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
