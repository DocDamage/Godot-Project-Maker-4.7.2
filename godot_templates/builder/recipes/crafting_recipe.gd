extends RefCounted
## Seeds the starters of the feature `crafting` (1.5.0, T18.14) under game/data/ (written once,
## then yours to edit in the dock's Recipes tab): the potion made by hand from two herbs
## (`recipes/potion.tres`) and the herb (`items/herb.tres`). A farm's workbench and kitchen add
## their own (T18.15, T18.16).
##
## Only a config that has the feature on gets them; a config written before 1.5.0 has no such key,
## so an older project regenerates as it was: no file, and the same hash.

const RECIPE_VERSION := 1

const SeedUtil := preload("../lib/seed_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const RECIPES_DIR := "res://game/data/recipes/"
const ITEMS_DIR := "res://game/data/items/"
const RECIPE_DEF := "res://addons/rpg_runtime/data/recipe.gd"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"
const POTION := "potion"
const HERB := "herb"
## The kinds that have a bag to craft into.
const KINDS: Array[String] = ["turn_based", "arpg", "farm"]
const HERB_COLOR := Color(0.36, 0.66, 0.3)
const HERB_VALUE := 4

## What a farm's workbench makes (T18.15): recipe id -> [ingredients, results, minutes], and the
## items they name: id -> [name, description, value, category (RpgItemDefinition.Category)].
const FARM_RECIPES := {
	"fence_piece": [{"wood": 2}, {"fence_piece": 1}, 10],
	"chest": [{"wood": 8}, {"chest": 1}, 60],
	"sprinkler": [{"stone": 3, "wood": 1}, {"sprinkler": 1}, 60],
	"scarecrow": [{"wood": 4}, {"scarecrow": 1}, 30],
	"path_stone": [{"stone": 1}, {"path_stone": 2}, 10],
	"preserves_jar": [{"wood": 3, "stone": 2}, {"preserves_jar": 1}, 60],
}
const FARM_ITEMS := {
	"wood": ["ITEM_WOOD_NAME", "ITEM_WOOD_DESC", 2, 6],
	"stone": ["ITEM_STONE_NAME", "ITEM_STONE_DESC", 2, 6],
	"fence_piece": ["ITEM_FENCE_PIECE_NAME", "ITEM_PLACE_DESC", 5, 6],
	"chest": ["ITEM_CHEST_NAME", "ITEM_PLACE_DESC", 30, 6],
	"sprinkler": ["ITEM_SPRINKLER_NAME", "ITEM_SPRINKLER_DESC", 40, 6],
	"scarecrow": ["ITEM_SCARECROW_NAME", "ITEM_PLACE_DESC", 20, 6],
	"path_stone": ["ITEM_PATH_STONE_NAME", "ITEM_PLACE_DESC", 2, 6],
	"preserves_jar": ["ITEM_PRESERVES_JAR_NAME", "ITEM_PRESERVES_JAR_DESC", 30, 6],
	"preserves": ["ITEM_PRESERVES_NAME", "ITEM_PRESERVES_DESC", 90, 0],
}
## The dishes of a farm's kitchen (T18.16): [id, name, parts]. A part is `crop:<n>` (the n-th
## crop of the plan), `fish`, `thing` (the first thing to forage), `egg` or `milk` (of an animal
## the farm keeps). Only the dishes whose parts the farm can get are seeded; the first of them is
## known from the start, the others are taught (a friend's heart, a festival).
const DISHES := [
	["salad", "Salad", ["crop:0", "crop:0"]],
	["vegetable_soup", "Vegetable soup", ["crop:0", "crop:1"]],
	["harvest_stew", "Harvest stew", ["crop:0", "crop:1", "crop:2"]],
	["grilled_fish", "Grilled fish", ["fish"]],
	["fish_stew", "Fish stew", ["fish", "crop:0"]],
	["omelette", "Omelette", ["egg", "egg"]],
	["pancakes", "Pancakes", ["egg", "milk"]],
	["warm_milk", "Warm milk", ["milk"]],
	["forest_pie", "Forest pie", ["thing", "crop:0"]],
	["forager_salad", "Forager salad", ["thing", "thing"]],
]
## What a dish restores and is worth beside its parts: their energy and value times this, plus
## the bonus.
const DISH_FACTOR := 1.5
const DISH_ENERGY_BONUS := 10
const KITCHEN_MINUTES := 10
const PART_ENERGY := 10  # an egg or milk, which nobody eats raw
const ITEM_COLOURS := {"wood": Color(0.55, 0.36, 0.2), "stone": Color(0.6, 0.6, 0.58), "preserves": Color(0.75, 0.3, 0.3)}

## English text of the seeded keys (the translations recipe adds them to strings.tsv).
const SEED_STRINGS := {
	"ITEM_WOOD_NAME": "Wood",
	"ITEM_WOOD_DESC": "Cleared from a stump or a branch. The workbench makes things of it.",
	"ITEM_STONE_NAME": "Stone",
	"ITEM_STONE_DESC": "Broken from a rock. The workbench makes things of it.",
	"ITEM_FENCE_PIECE_NAME": "Fence piece",
	"ITEM_CHEST_NAME": "Chest",
	"ITEM_SPRINKLER_NAME": "Sprinkler",
	"ITEM_SPRINKLER_DESC": "Put it down with Use: it waters the four cells round it each morning.",
	"ITEM_SCARECROW_NAME": "Scarecrow",
	"ITEM_PATH_STONE_NAME": "Path stone",
	"ITEM_PRESERVES_JAR_NAME": "Preserves jar",
	"ITEM_PRESERVES_JAR_DESC": "Put it down with Use; a crop put into it is a jar of preserves the next day.",
	"ITEM_PRESERVES_NAME": "Preserves",
	"ITEM_PRESERVES_DESC": "A crop kept in a jar. Worth more than the crop.",
	"ITEM_PLACE_DESC": "Put it down on the tile ahead with Use.",
	"RECIPE_FENCE_PIECE_NAME": "Fence piece",
	"RECIPE_CHEST_NAME": "Chest",
	"RECIPE_SPRINKLER_NAME": "Sprinkler",
	"RECIPE_SCARECROW_NAME": "Scarecrow",
	"RECIPE_PATH_STONE_NAME": "Path stones",
	"RECIPE_PRESERVES_JAR_NAME": "Preserves jar",
	"RECIPE_POTION_NAME": "Potion",
	"RECIPE_POTION_HINT": "Something that heals, made of plants.",
	"ITEM_HERB_NAME": "Herb",
	"ITEM_HERB_DESC": "A plant that heals. Two make a potion.",
}

static func on(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ctx.section("features").get("crafting", false)) and KINDS.has(JsonUtil.to_str(ctx.config.get("archetype", "turn_based")))

static func recipe_path(recipe_id: String) -> String:
	return RECIPES_DIR + recipe_id + ".tres"

static func _farm(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ctx.config.get("archetype", "")) == "farm"

## True when a farm cooks (`starter_map.cooking`, T18.16).
static func cooking_on(ctx: BuildContext) -> bool:
	return _farm(ctx) and JsonUtil.to_bool(ctx.section("starter_map").get("cooking", false))

## The parts a farm can get: `crop:<n>`, `fish`, `thing`, `egg`, `milk` -> {item, energy, value},
## from the stored plan (its crops, its fish and things, the products of its animals).
static func parts() -> Dictionary:
	var out := {}
	var plan := _farm_plan()
	var crops: Array = JsonUtil.to_array(plan.get("crops", []))
	for i in crops.size():
		var crop := JsonUtil.to_dict(crops[i])
		out["crop:%d" % i] = {"item": JsonUtil.to_str(crop.get("produce", "")), "energy": JsonUtil.to_int(crop.get("energy", 0)), "value": JsonUtil.to_int(crop.get("price", 0))}
	var forage := JsonUtil.to_dict(plan.get("forage", {}))
	for pair: Array in [["fish", "fish"], ["thing", "forage"]]:
		var listed := JsonUtil.to_array(forage.get(pair[1], []))
		if not listed.is_empty():
			var first := JsonUtil.to_dict(listed[0])
			out[pair[0]] = {"item": JsonUtil.to_str(first.get("item", "")), "energy": JsonUtil.to_int(first.get("energy", 0)), "value": JsonUtil.to_int(first.get("price", 0))}
	for raw: Variant in JsonUtil.to_array(JsonUtil.to_dict(plan.get("animals", {})).get("kinds", [])):
		var kind := JsonUtil.to_dict(raw)
		for product: String in ["egg", "milk"]:
			if JsonUtil.to_str(kind.get("product", "")) == product and not out.has(product):
				out[product] = {"item": product, "energy": PART_ENERGY, "value": JsonUtil.to_int(kind.get("price", 0))}
	return out

static func _farm_plan() -> Dictionary:
	var path := "res://rpggen/world_plan.json"
	if not FileAccess.file_exists(path):
		return {}
	return JsonUtil.to_dict(JsonUtil.to_dict(JSON.parse_string(FileAccess.get_file_as_string(path))).get("farm", {}))

## The dishes the farm can make: [{id, name, ingredients, energy, value, learn}], the first known.
static func dishes(given: Dictionary = {}) -> Array[Dictionary]:
	var have := given if not given.is_empty() else parts()
	var out: Array[Dictionary] = []
	for row: Array in DISHES:
		var needs: Array = row[2]
		var all := true
		for part: String in needs:
			if not have.has(part) or JsonUtil.to_str(JsonUtil.to_dict(have[part]).get("item", "")) == "":
				all = false
		if not all:
			continue
		var ingredients := {}
		var energy := 0
		var value := 0
		for part: String in needs:
			var got := JsonUtil.to_dict(have[part])
			var item := JsonUtil.to_str(got["item"])
			ingredients[item] = JsonUtil.to_int(ingredients.get(item, 0)) + 1
			energy += JsonUtil.to_int(got["energy"])
			value += JsonUtil.to_int(got["value"])
		out.append({"id": row[0], "name": row[1], "ingredients": ingredients, "energy": roundi(energy * DISH_FACTOR) + DISH_ENERGY_BONUS, "value": maxi(1, roundi(value * DISH_FACTOR)), "learn": "known" if out.is_empty() else "taught"})
	return out

func outputs(ctx: BuildContext) -> PackedStringArray:
	var wanted: Array = []
	if cooking_on(ctx):  # the kitchen's (T18.16), whatever the feature crafting says
		for dish in dishes():
			wanted.append(recipe_path("cook_" + JsonUtil.to_str(dish["id"])))
			wanted.append(ITEMS_DIR + JsonUtil.to_str(dish["id"]) + ".tres")
		wanted.append(ITEMS_DIR + "stove.tres")
	if not on(ctx):
		return SeedUtil.missing(wanted)
	wanted.append_array([recipe_path(POTION), ITEMS_DIR + HERB + ".tres"])
	if _farm(ctx):
		for recipe_id: String in FARM_RECIPES:
			wanted.append(recipe_path(recipe_id))
		for item_id: String in FARM_ITEMS:
			wanted.append(ITEMS_DIR + item_id + ".tres")
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "on": on(ctx), "herb": _herb_asset(ctx).get("id", "")}.merged({"farm": FARM_RECIPES} if on(ctx) and _farm(ctx) else {}).merged({"dishes": dishes()} if cooking_on(ctx) else {}))

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if cooking_on(ctx):
		for dish in dishes():
			var dish_id := JsonUtil.to_str(dish["id"])
			if not FileAccess.file_exists(recipe_path("cook_" + dish_id)):
				_save(ctx, dish_recipe(dish), recipe_path("cook_" + dish_id), issues)
			if not FileAccess.file_exists(ITEMS_DIR + dish_id + ".tres"):
				_save(ctx, dish_item(dish), ITEMS_DIR + dish_id + ".tres", issues)
		if not FileAccess.file_exists(ITEMS_DIR + "stove.tres"):  # sold where the farmhouse has no kitchen
			_save(ctx, stove_item(), ITEMS_DIR + "stove.tres", issues)
	if not on(ctx):
		return issues
	if not FileAccess.file_exists(recipe_path(POTION)):
		_save(ctx, potion_recipe(), recipe_path(POTION), issues)
	if not FileAccess.file_exists(ITEMS_DIR + HERB + ".tres"):
		_save(ctx, herb(ctx), ITEMS_DIR + HERB + ".tres", issues)
	if _farm(ctx):  # the workbench's (T18.15)
		for recipe_id: String in FARM_RECIPES:
			if not FileAccess.file_exists(recipe_path(recipe_id)):
				_save(ctx, farm_recipe(recipe_id), recipe_path(recipe_id), issues)
		for item_id: String in FARM_ITEMS:
			if not FileAccess.file_exists(ITEMS_DIR + item_id + ".tres"):
				_save(ctx, farm_item(item_id), ITEMS_DIR + item_id + ".tres", issues)
	return issues

## The stove a farmhouse built before the farm cooked gets at the shop: placed with Use, a kitchen.
static func stove_item() -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", &"stove")
	item.set("display_name", "ITEM_STOVE_NAME")
	item.set("description", "ITEM_PLACE_DESC")
	item.set("category", 5)  # RpgItemDefinition.Category.KEY: not sold back
	item.set("max_stack", 1)
	item.set("value", 0)
	var image := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	image.fill_rect(Rect2i(2, 3, 12, 11), Color(0.35, 0.35, 0.38))
	image.fill_rect(Rect2i(4, 7, 8, 4), Color(0.85, 0.4, 0.2))
	item.set("icon", ImageTexture.create_from_image(image))
	return item

## The recipe of a dish, made in the kitchen (station `kitchen`).
static func dish_recipe(dish: Dictionary) -> Resource:
	var made := SeedUtil.make(RECIPE_DEF)
	var dish_id := JsonUtil.to_str(dish["id"])
	made.set("id", StringName("cook_" + dish_id))
	made.set("title", JsonUtil.to_str(dish["name"]))
	made.set("ingredients", JsonUtil.to_dict(dish["ingredients"]).duplicate())
	made.set("results", {dish_id: 1})
	made.set("station", &"kitchen")
	made.set("minutes", KITCHEN_MINUTES)
	made.set("category", "dish")
	made.set("learn", JsonUtil.to_str(dish["learn"]))
	made.set("hint", "A dish somebody of the village may teach you.")
	return made

## A dish: eaten, it gives back its energy (`use_effect` heal: what a farm's eating reads).
static func dish_item(dish: Dictionary) -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", StringName(JsonUtil.to_str(dish["id"])))
	item.set("display_name", JsonUtil.to_str(dish["name"]))
	item.set("description", "A dish. It gives %d energy." % JsonUtil.to_int(dish["energy"]))
	item.set("category", 0)  # RpgItemDefinition.Category.CONSUMABLE
	item.set("max_stack", 99)
	item.set("value", JsonUtil.to_int(dish["value"]))
	item.set("use_effect", &"heal")
	item.set("effect_amount", JsonUtil.to_int(dish["energy"]))
	var image := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	image.fill_rect(Rect2i(2, 9, 12, 4), Color(0.92, 0.92, 0.88))
	image.fill_rect(Rect2i(4, 6, 8, 4), Color(0.85, 0.55, 0.3))
	item.set("icon", ImageTexture.create_from_image(image))
	return item

## A recipe of the farm's workbench, known from the start.
static func farm_recipe(recipe_id: String) -> Resource:
	var row: Array = FARM_RECIPES[recipe_id]
	var made := SeedUtil.make(RECIPE_DEF)
	made.set("id", StringName(recipe_id))
	made.set("title", "RECIPE_%s_NAME" % recipe_id.to_upper())
	made.set("ingredients", JsonUtil.to_dict(row[0]).duplicate())
	made.set("results", JsonUtil.to_dict(row[1]).duplicate())
	made.set("station", &"workbench")
	made.set("minutes", JsonUtil.to_int(row[2]))
	made.set("category", "farm")
	made.set("learn", "known")
	return made

## An item of the farm's crafting, with a drawn icon.
static func farm_item(item_id: String) -> Resource:
	var row: Array = FARM_ITEMS[item_id]
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", StringName(item_id))
	item.set("display_name", JsonUtil.to_str(row[0]))
	item.set("description", JsonUtil.to_str(row[1]))
	item.set("value", JsonUtil.to_int(row[2]))
	item.set("category", JsonUtil.to_int(row[3]))
	item.set("max_stack", 99)
	var image := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	var colour: Color = ITEM_COLOURS.get(item_id, Color(0.55, 0.42, 0.3))
	image.fill_rect(Rect2i(3, 4, 10, 9), colour)
	image.fill_rect(Rect2i(3, 4, 10, 1), colour.lightened(0.3))
	item.set("icon", ImageTexture.create_from_image(image))
	return item

func _save(ctx: BuildContext, res: Resource, path: String, issues: Array) -> void:
	var err := SeedUtil.save(res, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## Two herbs make a potion, by hand, known from the start.
static func potion_recipe() -> Resource:
	var made := SeedUtil.make(RECIPE_DEF)
	made.set("id", StringName(POTION))
	made.set("title", "RECIPE_POTION_NAME")
	made.set("ingredients", {HERB: 2})
	made.set("results", {POTION: 1})
	made.set("category", "medicine")
	made.set("learn", "known")
	made.set("hint", "RECIPE_POTION_HINT")
	return made

## The herb: a pack's ITEM with `herb` (or `leaf`, `plant`) in its name, else a drawn sprig.
static func herb(ctx: BuildContext) -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", StringName(HERB))
	item.set("display_name", "ITEM_HERB_NAME")
	item.set("description", "ITEM_HERB_DESC")
	item.set("category", 6)  # RpgItemDefinition.Category.MATERIAL
	item.set("max_stack", 99)
	item.set("value", HERB_VALUE)
	var asset := _herb_asset(ctx)
	if not asset.is_empty():
		var eff: Dictionary = ctx.catalog.effective(asset)
		var size: Array = eff.get("frame", eff.get("size", [16, 16]))
		item.set("icon", TextureUtil.region_texture("res://" + JsonUtil.to_str(asset["path"]), Rect2i(0, 0, JsonUtil.to_int(size[0]), JsonUtil.to_int(size[1]))))
	else:
		item.set("icon", drawn_herb())
	return item

static func _herb_asset(ctx: BuildContext) -> Dictionary:
	for asset in ctx.catalog.assets_by_role("ITEM"):
		var eff: Dictionary = ctx.catalog.effective(asset)
		if asset.get("status", "") in ["UNUSED", "MISSING"] or not ["sprite", "object"].has(JsonUtil.to_str(eff.get("usage", ""))):
			continue
		var words := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower().replace("-", "_").split("_", false)
		for word: String in ["herb", "herbs", "leaf", "plant"]:
			if words.has(word):
				return asset
	return {}

## A sprig of three leaves, 16 px.
static func drawn_herb() -> ImageTexture:
	var image := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	image.fill_rect(Rect2i(7, 6, 2, 8), HERB_COLOR.darkened(0.3))
	image.fill_rect(Rect2i(4, 3, 4, 4), HERB_COLOR)
	image.fill_rect(Rect2i(9, 4, 4, 4), HERB_COLOR)
	image.fill_rect(Rect2i(5, 8, 3, 3), HERB_COLOR.lightened(0.15))
	return ImageTexture.create_from_image(image)
