extends RefCounted
## The fish and the forage of a farm (T17.10), from the stored plan (`rpggen/world_plan.json`,
## `farm.forage`, planned by rpggen/core/forage_plan.py):
## * generated/data/forage.json, on every build: the things to forage and the fish of the plan,
##   the places of the farm's map (`spots`, cells of the map `map`: what a farm map made before
##   it had markers goes by) and whether the rod is sold (`fishing`);
## * game/data/forage.json, the things and the fish, once: it is the user's afterwards, and the
##   game takes from the generated file only the entries the user's does not list;
## * game/data/items/<item>.tres for every thing and every fish, once: what is picked up and
##   caught, with the picture of the packs (an `ITEM` tagged `forage` or `fish`), else the one
##   of the drawn farm kit, else a drawn icon.
##
## The rod is a tool (farmer_recipe.gd makes its item) and the places are markers of the farm's
## map (`add_places`, which farm_map_recipe.gd calls while it builds the map).

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

const PLANNED_PATH := "res://generated/data/forage.json"
const USER_PATH := "res://game/data/forage.json"
const FARM_MAP_ID := "farm"
## The node of a map whose children are its places (RpgForage.HOLDER, SPOT_PREFIX).
const HOLDER := "Forage"
const SPOT_PREFIX := "Spot"
const KINDS: Array[String] = ["forage", "fish"]
## What only the planner needs of an entry: not in the files the game reads.
const PLAN_ONLY: Array[String] = ["asset", "color"]

static func item_path(item_id: String) -> String:
	return FarmBuild.ITEMS_DIR + item_id + ".tres"

## The entries of a kind of the plan (`forage` or `fish`), in its order.
static func entries(kind: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmBuild.forage().get(kind, [])):
		out.append(JsonUtil.to_dict(raw))
	return out

## The places of the plan, as cells of the farm's map.
static func spots() -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for raw: Variant in JsonUtil.to_array(FarmBuild.forage().get("spots", [])):
		var pair := JsonUtil.to_array(raw)
		if pair.size() == 2:
			out.append(Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])))
	return out

## Writes the places of the plan into a map that is being built: `Forage/Spot1` ... in the
## middle of their cells. A plan without places adds nothing.
static func add_places(root: Node2D, tile_px: int) -> void:
	var cells := spots()
	if cells.is_empty():
		return
	var holder := Node2D.new()
	SceneUtil.add(root, holder, root, HOLDER)
	for i in cells.size():
		MapUtil.add_marker(holder, root, "%s%d" % [SPOT_PREFIX, i + 1], MapUtil.tile_center(cells[i], tile_px))

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([PLANNED_PATH])
	var seeded: Array = [USER_PATH]
	for kind in KINDS:
		for entry in entries(kind):
			seeded.append(item_path(JsonUtil.to_str(entry["item"])))
	out.append_array(SeedUtil.missing(seeded))
	return out

func input_hash(ctx: BuildContext) -> String:
	var art := {}
	for kind in KINDS:
		for entry in entries(kind):
			var asset := _asset(ctx, entry)
			art[entry["id"]] = {"sha256": asset.get("sha256", ""), "eff": ctx.catalog.effective(asset) if not asset.is_empty() else {}}
	return ctx.stable_hash({"v": RECIPE_VERSION, "plan": FarmBuild.forage(), "art": art})

## The picture of an entry of the plan, or {} for a drawn one or a picture that is gone.
func _asset(ctx: BuildContext, entry: Dictionary) -> Dictionary:
	var asset_id := JsonUtil.to_str(entry.get("asset", ""))
	if asset_id == "":
		return {}
	var asset: Dictionary = ctx.catalog.asset(asset_id)
	if asset.is_empty() or asset.get("status", "") in ["UNUSED", "MISSING"]:
		return {}
	return asset

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var plan := FarmBuild.forage()
	if plan.is_empty():
		print("[rpggen] INFO forage: the project has no plan of its fish and forage (rpggen/world_plan.json, farm.forage)")
	var listed := {}
	for kind in KINDS:
		var rows: Array = []
		for entry in entries(kind):
			var path := item_path(JsonUtil.to_str(entry["item"]))
			if not FileAccess.file_exists(path):
				var err := SeedUtil.save(_item(ctx, entry, kind), path)
				if err != OK:
					issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
			var row := {}
			for key: String in entry.keys():
				if not PLAN_ONLY.has(key):
					row[key] = _whole(entry[key])
			rows.append(row)
		listed[kind] = rows
	var planned := listed.duplicate()
	var cells: Array = []
	for cell in spots():
		cells.append([cell.x, cell.y])
	planned["spots"] = cells
	planned["map"] = FARM_MAP_ID
	planned["fishing"] = FarmBuild.fishing()
	for pair: Array in [[PLANNED_PATH, planned]] + ([[USER_PATH, listed]] if not FileAccess.file_exists(USER_PATH) else []):
		var path: String = pair[0]
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		var write_err := JsonUtil.write(path, pair[1])
		if write_err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": write_err}, path))
	return issues

## A number of the plan as the whole number it is (JSON gives floats back); a speed stays one.
static func _whole(value: Variant) -> Variant:
	if value is float:
		var number: float = value
		if is_equal_approx(number, roundf(number)):
			return int(number)
	return value

## What is picked up or caught: an item that is sold and can be eaten or given.
func _item(ctx: BuildContext, entry: Dictionary, kind: String) -> Resource:
	var item := SeedUtil.make(FarmBuild.ITEM_DEF)
	item.set("id", StringName(JsonUtil.to_str(entry["item"])))
	item.set("display_name", JsonUtil.to_str(entry.get("name", entry["item"])))
	item.set("max_stack", 99)
	item.set("value", JsonUtil.to_int(entry.get("price", 0)))
	var icon := FarmBuild.first_frame(ctx, _asset(ctx, entry))
	if icon == null:
		var given := JsonUtil.to_str(entry.get("color", ""))
		var colour := Color.html(given) if given != "" else FarmBuild.crop_colour(entry)
		icon = FarmBuild.drawn_icon("fish" if kind == "fish" else "produce", colour)
	item.set("icon", icon)
	return item
