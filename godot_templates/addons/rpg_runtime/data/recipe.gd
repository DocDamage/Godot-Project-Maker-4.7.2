@tool
class_name RpgRecipe
extends Resource
## A recipe of crafting (1.5.0, T18.14): what it takes, what it makes, where and how long.
## Files live in game/data/recipes/<id>.tres; RpgRecipeBook loads them and RpgCrafting uses them.

## How a recipe becomes known: from the start, when somebody teaches it (the dialogue event
## `learn_recipe:<id>`, a gift, a festival), or found by itself once every ingredient has been
## held at least once.
const KNOWN := "known"
const TAUGHT := "taught"
const FOUND := "found"
const LEARN_WAYS: Array[String] = [KNOWN, TAUGHT, FOUND]

@export var id: StringName
@export var title: String  # a tr() key
## {item id: how many} taken, and {item id: how many} given.
@export var ingredients: Dictionary = {}
@export var results: Dictionary = {}
## The station it is made at (an RpgStation's `station_id`: workbench, stove, forge...); &"":
## by hand, anywhere.
@export var station: StringName = &""
## Game minutes it takes (seconds in a game without a calendar); 0: at once.
@export var minutes: int = 0
@export var category: String = ""
@export_enum("known", "taught", "found") var learn: String = KNOWN
## What a recipe not yet known says of itself (a tr() key or text), shown with its silhouette.
@export var hint: String = ""

## [{item_id, qty}] of a table {item: qty} times `amount` (what Inventory.transact takes).
static func rows(table: Dictionary, amount: int = 1) -> Array:
	var out: Array = []
	var keys := table.keys()
	keys.sort()
	for item_id: Variant in keys:
		out.append({"item_id": StringName(str(item_id)), "qty": maxi(1, RpgUtil.to_int(table[item_id])) * maxi(1, amount)})
	return out

## The item ids it names (ingredients and results).
func items() -> Array[String]:
	var out: Array[String] = []
	for table: Dictionary in [ingredients, results]:
		for item_id: Variant in table:
			if not out.has(str(item_id)):
				out.append(str(item_id))
	return out

## What is wrong with it, one sentence each (VAL-034 adds the items and stations nobody has).
func problems() -> Array[String]:
	var out: Array[String] = []
	if id == &"":
		out.append("the recipe has no id")
	if ingredients.is_empty():
		out.append("the recipe takes nothing")
	if results.is_empty():
		out.append("the recipe makes nothing")
	for table: Dictionary in [ingredients, results]:
		for item_id: Variant in table:
			if RpgUtil.to_int(table[item_id]) < 1:
				out.append("'%s' is listed with %s, not 1 or more" % [item_id, table[item_id]])
	if not LEARN_WAYS.has(learn):
		out.append("it is learned '%s': known, taught or found" % learn)
	if minutes < 0:
		out.append("it takes %d minutes" % minutes)
	return out

## The recipe as plain data, and back (the dock's JSON export and import).
func to_dict() -> Dictionary:
	return {"id": String(id), "title": title, "ingredients": ingredients.duplicate(), "results": results.duplicate(), "station": String(station), "minutes": minutes, "category": category, "learn": learn, "hint": hint}

static func from_dict(data: Dictionary) -> RpgRecipe:
	var made := RpgRecipe.new()
	made.id = StringName(str(data.get("id", "")))
	made.title = str(data.get("title", ""))
	for key: String in ["ingredients", "results"]:
		var table := {}
		var given := RpgUtil.to_dict(data.get(key, {}))
		for item_id: Variant in given:
			table[str(item_id)] = RpgUtil.to_int(given[item_id], 1)
		made.set(key, table)
	made.station = StringName(str(data.get("station", "")))
	made.minutes = maxi(0, RpgUtil.to_int(data.get("minutes", 0)))
	made.category = str(data.get("category", ""))
	made.learn = str(data.get("learn", KNOWN))
	made.hint = str(data.get("hint", ""))
	return made
