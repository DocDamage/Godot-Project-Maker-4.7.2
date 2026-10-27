extends RefCounted
## The animals of a farm (T17.07), from the stored plan (`rpggen/world_plan.json`, the key
## `animals` of the section `farm`, planned by rpggen/core/animal_plan.py) and the animal houses
## of the farm's own plan (`farm.map`):
## * generated/scenes/farm/animals/<kind>__<variant>.tscn, an RpgFarmAnimal for every picture
##   of every kind: the body of an NPC (but on layer 5, the feet as its shape) with the animations of
##   the variant's sheet and, when the animal sleeps in a sheet of its own, that sheet's too;
## * generated/data/animals.json, the plan with the scenes and the houses, on every build;
## * game/data/animals.json, the same, once: it is the user's afterwards, and the game takes
##   from the generated file only the kinds and houses the user's does not list;
## * game/data/items/, once: what each kind gives (`egg`) and what it gives as a friend
##   (`egg_large`), the feed (`hay`), and the item the shop lists the kind as (`animal_hen`,
##   a key item that never reaches the bag: RpgAnimalHouse.deliver).
##
## A farm without an animal house (`animals: none`) has no `farm.animals`: this recipe has no
## outputs then and writes nothing.

const RECIPE_VERSION := 1

const Paths := preload("../../lib/paths.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const ActorBuild := preload("../../lib/actor_build.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")
const FarmMapRecipe := preload("farm_map_recipe.gd")

const ANIMAL := FarmBuild.DIR + "animal.gd"
const PLANNED_PATH := "res://generated/data/animals.json"
const USER_PATH := "res://game/data/animals.json"
const SCENES_DIR := "res://generated/scenes/farm/animals/"
## RpgItemDefinition.Category
const KEY := 5
const MATERIAL := 6
## How fast an animal wanders, in tiles a second.
const SPEED_TILES := 1.25
## The words a pack's own picture of a product is known by (role ITEM, tag `product`).
const PRODUCT_WORDS := {"egg": ["egg", "eggs"], "duck_egg": ["egg", "eggs"], "milk": ["milk"], "goat_milk": ["milk"], "wool": ["wool"]}
const SHELL := Color(0.96, 0.93, 0.85)
const HAY := Color(0.9, 0.78, 0.35)
const TWINE := Color(0.6, 0.42, 0.2)
const PAIL := Color(0.72, 0.75, 0.78)

# ---------------------------------------------------------------- the plan

## The animals of the stored plan (`farm.animals`), or {} for a farm that keeps none.
static func plan() -> Dictionary:
	return JsonUtil.to_dict(FarmBuild.plan().get("animals", {}))

## The kinds of the plan, in its order.
static func kinds() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(plan().get("kinds", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

static func variants(kind: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(kind.get("variants", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

## The animal houses of the farm's own plan as the game needs them (animal_plan.houses_of):
## `{kind, map, yard_map, stalls}`.
static func houses() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmMapRecipe.plan().get("animal_houses", [])):
		var building := JsonUtil.to_dict(raw)
		var room := JsonUtil.to_dict(building.get("interior", {}))
		out.append({
			"kind": JsonUtil.to_str(building.get("kind", "")),
			"map": FarmMapRecipe.room_path(building),
			"yard_map": FarmMapRecipe.FARM_PATH,
			"stalls": JsonUtil.to_array(room.get("stalls", [])).size(),
		})
	return out

static func scene_path(kind_id: String, variant_id: String) -> String:
	return "%s%s__%s.tscn" % [SCENES_DIR, kind_id, variant_id]

static func item_path(item_id: String) -> String:
	return FarmBuild.ITEMS_DIR + item_id + ".tres"

## The items of the plan that are seeded once: id -> what it is (`product`, `large`, `ticket`,
## `feed`) with the kind it belongs to. A product two kinds share is listed once.
static func items() -> Dictionary:
	var out := {}
	var section := plan()
	var feed := JsonUtil.to_dict(section.get("feed", {}))
	if JsonUtil.to_str(feed.get("item", "")) != "" and not kinds().is_empty():
		out[JsonUtil.to_str(feed["item"])] = {"what": "feed", "name": JsonUtil.to_str(feed.get("name", "Feed")), "value": JsonUtil.to_int(feed.get("price", 0))}
	for kind in kinds():
		var title := JsonUtil.to_str(kind.get("product_name", kind.get("product", "")))
		for entry: Array in [["product", "product", title, "price"], ["large", "large", "Large %s" % title.to_lower(), "large_price"], ["ticket", "ticket", JsonUtil.to_str(kind.get("name", "")), "cost"]]:
			var id := JsonUtil.to_str(kind.get(entry[1], ""))
			if id != "" and not out.has(id):
				out[id] = {"what": entry[0], "name": entry[2], "value": JsonUtil.to_int(kind.get(entry[3], 0)), "kind": kind}
		# what its product is taken with (T18.12): a pail, shears; a plan of before has none
		var tool := JsonUtil.to_str(kind.get("tool", ""))
		if tool != "" and not out.has(tool):
			out[tool] = {"what": "tool", "name": "ITEM_%s_NAME" % tool.to_upper(), "value": 0, "kind": kind}
	return out

## The tools the kinds of the plan need (T18.12), each once: what a new game of a farm that has
## them starts with.
static func tools() -> Array[String]:
	var out: Array[String] = []
	for kind in kinds():
		var tool := JsonUtil.to_str(kind.get("tool", ""))
		if tool != "" and not out.has(tool):
			out.append(tool)
	return out

# ---------------------------------------------------------------- the recipe

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	if plan().is_empty():
		return out
	out.append(PLANNED_PATH)
	var seeded: Array = [USER_PATH]
	for kind in kinds():
		for variant in variants(kind):
			out.append(scene_path(JsonUtil.to_str(kind["id"]), JsonUtil.to_str(variant["id"])))
	for item_id: String in items().keys():
		seeded.append(item_path(item_id))
	out.append_array(SeedUtil.missing(seeded))
	return out

func input_hash(ctx: BuildContext) -> String:
	var art := {}
	for kind in kinds():
		for variant in variants(kind):
			for key: String in ["asset", "sleep"]:
				var asset := _asset(ctx, JsonUtil.to_str(variant.get(key, "")))
				if not asset.is_empty():
					art[asset["id"]] = {"sha256": asset.get("sha256", ""), "eff": ctx.catalog.effective(asset)}
	return ctx.stable_hash({"v": RECIPE_VERSION, "animals": plan(), "houses": houses(), "art": art, "tile": FarmBuild.tile(ctx)})

## An asset of the catalog that is in use, or {}.
func _asset(ctx: BuildContext, asset_id: String) -> Dictionary:
	if asset_id == "":
		return {}
	var asset: Dictionary = ctx.catalog.asset(asset_id)
	if asset.is_empty() or asset.get("status", "") in ["UNUSED", "MISSING"]:
		return {}
	return asset

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var section := plan()
	if section.is_empty():
		return issues
	var tile := FarmBuild.tile(ctx)
	var entries: Array = []
	for kind in kinds():
		var kind_id := JsonUtil.to_str(kind["id"])
		var entry := JsonUtil.to_dict(_whole(kind))
		var listed: Array = []
		for variant in variants(kind):
			var shown := JsonUtil.to_dict(_whole(variant))
			var path := scene_path(kind_id, JsonUtil.to_str(variant["id"]))
			var node := _scene(ctx, kind_id, variant, tile)
			shown["scene"] = ""
			if node != null:
				var err := SceneUtil.save_scene(node, path)
				if err != OK:
					issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
				else:
					shown["scene"] = path
			listed.append(shown)
		entry["variants"] = listed
		entries.append(entry)
	var found := items()
	for item_id: String in found.keys():
		var path := item_path(item_id)
		if FileAccess.file_exists(path):
			continue
		var err := SeedUtil.save(_item(ctx, item_id, JsonUtil.to_dict(found[item_id])), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var data := {
		"animals": entries,
		"feed": _whole(section.get("feed", {})),
		"names": JsonUtil.to_array(section.get("names", [])),
		"houses": houses(),
	}
	for path: String in [PLANNED_PATH] + Array(SeedUtil.missing([USER_PATH])):
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		var write_err := JsonUtil.write(path, data)
		if write_err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": write_err}, path))
	return issues

## A number of the plan as the whole number it is (JSON gives floats back), in lists and
## tables too.
static func _whole(value: Variant) -> Variant:
	if value is float:
		var number: float = value
		return int(number) if is_equal_approx(number, roundf(number)) else value
	if value is Array:
		var list: Array = value
		var out: Array = []
		for item: Variant in list:
			out.append(_whole(item))
		return out
	if value is Dictionary:
		var table: Dictionary = value
		var out := {}
		for key: Variant in table.keys():
			out[key] = _whole(table[key])
		return out
	return value

# ---------------------------------------------------------------- the scenes

## The animations of the sheet an animal walks in and, when `sleep` is another sheet, of that
## one too: the walking sheet's own SpriteFrames when it is all there is, else a new one with
## the animations of both (the walking sheet's first). Null when the walking sheet has none.
static func frames_of(walk_id: String, sleep_id: String) -> SpriteFrames:
	var walk := _load_frames(walk_id)
	var sleep := _load_frames(sleep_id) if sleep_id != "" and sleep_id != walk_id else null
	if walk == null or sleep == null:
		return walk
	var out := SpriteFrames.new()
	if out.has_animation("default"):
		out.remove_animation("default")
	for source: SpriteFrames in [walk, sleep]:
		for anim: StringName in source.get_animation_names():
			if out.has_animation(anim):
				continue
			out.add_animation(anim)
			out.set_animation_speed(anim, source.get_animation_speed(anim))
			out.set_animation_loop(anim, source.get_animation_loop(anim))
			for i in source.get_frame_count(anim):
				# a copy: the frame of another file is not shared with it
				out.add_frame(anim, source.get_frame_texture(anim, i).duplicate() as Texture2D, source.get_frame_duration(anim, i))
			if source.has_meta("flip_h_" + anim):
				out.set_meta("flip_h_" + anim, source.get_meta("flip_h_" + anim))
	return out

static func _load_frames(asset_id: String) -> SpriteFrames:
	var path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % asset_id
	return load(path) as SpriteFrames if asset_id != "" and ResourceLoader.exists(path) else null

## The scene of one picture of a kind, or null when its sheet is gone.
func _scene(ctx: BuildContext, kind_id: String, variant: Dictionary, tile: int) -> Node:
	var walk := _asset(ctx, JsonUtil.to_str(variant.get("asset", "")))
	if walk.is_empty():
		return null
	var sleep := _asset(ctx, JsonUtil.to_str(variant.get("sleep", "")))
	var frames := frames_of(JsonUtil.to_str(walk["id"]), JsonUtil.to_str(sleep.get("id", "")))
	if frames == null:
		return null
	var fo := ActorBuild.frame_and_origin(ctx.catalog.effective(walk))
	var frame: Vector2i = fo["frame"]
	var origin: Vector2i = fo["origin"]
	return build_animal(kind_id, frames, frame, origin, tile)

## An RpgFarmAnimal: the body of an NPC with the animal's script and a slow walk, on the layer
## of the interactables (5) alone: `interact` finds it, a fence (the world, 1) holds it, and the
## farmer, who is stopped by NPCs (4), walks through it and is never shut in by its own hens.
static func build_animal(kind_id: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int) -> CharacterBody2D:
	var root := ActorBuild.build("npc", "Animal", frames, frame, origin, tile)
	SceneUtil.attach_script(root, ANIMAL)
	root.collision_layer = 0
	root.set_collision_layer_value(5, true)
	root.set("kind", kind_id)
	root.get_node("Components/Movement").set("speed", tile * SPEED_TILES)
	var visual := root.get_node("Visual") as AnimatedSprite2D
	if frames != null and not frames.has_animation("idle_down"):
		var names := frames.get_animation_names()
		for wanted: String in ["walk_down", String(names[0]) if not names.is_empty() else ""]:
			if wanted != "" and frames.has_animation(wanted):
				visual.animation = wanted
				break
	return root

# ---------------------------------------------------------------- the items

func _item(ctx: BuildContext, item_id: String, info: Dictionary) -> Resource:
	var what := JsonUtil.to_str(info["what"])
	var kind := JsonUtil.to_dict(info.get("kind", {}))
	var item := SeedUtil.make(FarmBuild.ITEM_DEF)
	item.set("id", StringName(item_id))
	item.set("display_name", JsonUtil.to_str(info["name"]))
	item.set("value", JsonUtil.to_int(info["value"]))
	item.set("category", MATERIAL)
	item.set("max_stack", 99)
	match what:
		"feed":
			item.set("description", "Feed for the trough of a coop or a barn.")
			item.set("icon", drawn_icon("hay"))
		"ticket":
			item.set("category", KEY)  # never sold back, never in the bin
			item.set("max_stack", 1)
			item.set("description", "Moves into your %s." % JsonUtil.to_str(kind.get("house", "barn")))
			item.set("icon", _animal_icon(ctx, kind))
		"tool":  # a pail, shears (T18.12): kept like a tool
			item.set("category", KEY)
			item.set("max_stack", 1)
			item.set("description", "Takes %s from an animal that is ready." % JsonUtil.to_str(kind.get("product_name", "its product")).to_lower())
			var own := FarmBuild.first_frame(ctx, tool_asset(ctx, item_id))
			item.set("icon", own if own != null else drawn_icon(item_id))
		_:
			var icon := FarmBuild.first_frame(ctx, product_asset(ctx, JsonUtil.to_str(kind.get("product", item_id))))
			item.set("icon", icon if icon != null else drawn_icon("product"))
	return item

## The first picture of the first variant of a kind, or a drawn one.
func _animal_icon(ctx: BuildContext, kind: Dictionary) -> Texture2D:
	for variant in variants(kind):
		var icon := FarmBuild.first_frame(ctx, _asset(ctx, JsonUtil.to_str(variant.get("asset", ""))))
		if icon != null:
			return icon
	return drawn_icon("product")

## The picture of what an animal gives: a pack's own (an ITEM tagged `product` with a word of
## the product in its file name), else the kit's egg for an egg, or {}.
static func product_asset(ctx: BuildContext, product_id: String) -> Dictionary:
	var words: Array = PRODUCT_WORDS.get(product_id, [product_id])
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var tags: Array = eff.get("tags", [])
		if asset.get("status", "") in ["UNUSED", "MISSING"] or asset.get("pack_id", "") == FarmBuild.KIT_PACK:
			continue
		if eff.get("role", "") != "ITEM" or not tags.has("product") or not ["sprite", "object"].has(JsonUtil.to_str(eff.get("usage", ""))):
			continue
		var file := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower()
		for word: String in words:
			if file.split("_", false).has(word):
				return asset
	return FarmBuild.kit_asset(ctx, "egg") if words.has("egg") else {}

## The words a pack's picture of an animal tool is known by (T18.12).
const TOOL_WORDS := {"pail": [["pail"], ["bucket"], ["milk", "can"]], "shears": [["shears"], ["clippers"]]}

## A pack's picture of a pail (named pail, bucket or milk can) or of shears: a TOOL or an ITEM
## sprite of a pack (not the kit's), or {}.
static func tool_asset(ctx: BuildContext, tool_id: String) -> Dictionary:
	var wanted: Array = TOOL_WORDS.get(tool_id, [[tool_id]])
	for asset in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(asset)
		if asset.get("status", "") in ["UNUSED", "MISSING"] or asset.get("pack_id", "") == FarmBuild.KIT_PACK:
			continue
		if not ["TOOL", "ITEM"].has(JsonUtil.to_str(eff.get("role", ""))) or not ["sprite", "object"].has(JsonUtil.to_str(eff.get("usage", ""))):
			continue
		var words := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower().replace("-", "_").replace(" ", "_").split("_", false)
		for group: Array in wanted:
			if group.all(func(word: String) -> bool: return words.has(word)):
				return asset
	return {}

## A drawn icon of 16 px: a bale of hay (`hay`), a pail (`pail`), shears (`shears`), or
## something pale and round (anything else).
static func drawn_icon(what: String) -> ImageTexture:
	var image := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	if what == "hay":
		image.fill_rect(Rect2i(2, 5, 12, 9), HAY)
		image.fill_rect(Rect2i(2, 5, 12, 1), HAY.lightened(0.25))
		image.fill_rect(Rect2i(5, 5, 1, 9), TWINE)
		image.fill_rect(Rect2i(10, 5, 1, 9), TWINE)
	elif what == "pail":  # a bucket of tin with a handle
		image.fill_rect(Rect2i(4, 6, 8, 8), PAIL)
		image.fill_rect(Rect2i(5, 13, 6, 1), PAIL.darkened(0.3))
		image.fill_rect(Rect2i(4, 6, 8, 1), PAIL.lightened(0.3))
		image.fill_rect(Rect2i(3, 3, 1, 4), PAIL.darkened(0.2))
		image.fill_rect(Rect2i(12, 3, 1, 4), PAIL.darkened(0.2))
		image.fill_rect(Rect2i(4, 2, 8, 1), PAIL.darkened(0.2))
	elif what == "shears":  # two blades and two rings
		image.fill_rect(Rect2i(7, 2, 2, 7), PAIL)
		image.fill_rect(Rect2i(9, 3, 2, 6), PAIL.darkened(0.15))
		image.fill_rect(Rect2i(4, 10, 4, 4), TWINE)
		image.fill_rect(Rect2i(9, 10, 4, 4), TWINE)
		image.fill_rect(Rect2i(5, 11, 2, 2), Color(0, 0, 0, 0))
		image.fill_rect(Rect2i(10, 11, 2, 2), Color(0, 0, 0, 0))
	else:
		image.fill_rect(Rect2i(5, 4, 6, 9), SHELL)
		image.fill_rect(Rect2i(4, 6, 8, 6), SHELL)
		image.fill_rect(Rect2i(6, 5, 2, 2), SHELL.lightened(0.5))
	return ImageTexture.create_from_image(image)
