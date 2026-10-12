extends RefCounted
## The crops of a farm (T17.05), from the stored plan (`rpggen/world_plan.json`, the section
## `farm`, planned by rpggen/core/crop_plan.py):
## * generated/scenes/farm/crops/<id>.tscn, an RpgCrop: a Sprite2D over the growth strip of the
##   packs, one frame a stage, or the drawn stand-in (a stem that grows, and what is harvested
##   on it when it is ripe);
## * generated/data/crops.json, the plan with the scenes, on every build;
## * game/data/crops.json, the same, once: it is the user's afterwards, and the game takes from
##   the generated file only the crops the user's does not list;
## * game/data/items/seed_<id>.tres and crop_<id>.tres, the seeds and what is harvested, once.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

const PLANNED_PATH := "res://generated/data/crops.json"
const USER_PATH := "res://game/data/crops.json"
## What only the planner needs of a crop: not in the files the game reads.
const PLAN_ONLY: Array[String] = ["asset", "color"]

static func scene_path(crop_id: String) -> String:
	return FarmBuild.CROPS_DIR + crop_id + ".tscn"

static func item_path(item_id: String) -> String:
	return FarmBuild.ITEMS_DIR + item_id + ".tres"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([PLANNED_PATH])
	var seeded: Array = [USER_PATH]
	for crop in FarmBuild.crops():
		out.append(scene_path(JsonUtil.to_str(crop["id"])))
		seeded.append(item_path(JsonUtil.to_str(crop["seed"])))
		seeded.append(item_path(JsonUtil.to_str(crop["produce"])))
	out.append_array(SeedUtil.missing(seeded))
	return out

func input_hash(ctx: BuildContext) -> String:
	var strips := {}
	for crop in FarmBuild.crops():
		var asset := _strip(ctx, crop)
		strips[crop["id"]] = {"sha256": asset.get("sha256", ""), "eff": ctx.catalog.effective(asset) if not asset.is_empty() else {}}
	return ctx.stable_hash({"v": RECIPE_VERSION, "crops": FarmBuild.crops(), "strips": strips, "tile": FarmBuild.tile(ctx)})

## The growth strip of a crop of the plan, or {} for a drawn crop or a strip that is gone.
func _strip(ctx: BuildContext, crop: Dictionary) -> Dictionary:
	var asset_id := JsonUtil.to_str(crop.get("asset", ""))
	if asset_id == "":
		return {}
	var asset: Dictionary = ctx.catalog.asset(asset_id)
	if asset.is_empty() or asset.get("status", "") in ["UNUSED", "MISSING"]:
		return {}
	return asset

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := FarmBuild.tile(ctx)
	var entries: Array = []
	for crop in FarmBuild.crops():
		var crop_id := JsonUtil.to_str(crop["id"])
		var strip := _strip(ctx, crop)
		var err := SceneUtil.save_scene(_scene(ctx, crop, strip, tile), scene_path(crop_id))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": scene_path(crop_id), "err": err}, scene_path(crop_id)))
		_seed_item(ctx, _seeds(crop), item_path(JsonUtil.to_str(crop["seed"])), issues)
		_seed_item(ctx, _produce(ctx, crop, strip), item_path(JsonUtil.to_str(crop["produce"])), issues)
		var entry := {}
		for key: String in crop.keys():
			if not PLAN_ONLY.has(key):
				entry[key] = _whole(crop[key])
		entry["scene"] = scene_path(crop_id)
		entries.append(entry)
	var data := {"crops": entries}
	for path: String in [PLANNED_PATH] + Array(SeedUtil.missing([USER_PATH])):
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		var write_err := JsonUtil.write(path, data)
		if write_err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": write_err}, path))
	return issues

## A number of the plan as the whole number it is (JSON gives floats back).
static func _whole(value: Variant) -> Variant:
	if value is float:
		var number: float = value
		if is_equal_approx(number, roundf(number)):
			return int(number)
	return value

func _seed_item(ctx: BuildContext, item: Resource, path: String, issues: Array) -> void:
	if FileAccess.file_exists(path):
		return
	var err := SeedUtil.save(item, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

# ---------------------------------------------------------------- the scene

func _scene(ctx: BuildContext, crop: Dictionary, strip: Dictionary, tile: int) -> Area2D:
	var root := Area2D.new()
	root.name = "Crop"
	SceneUtil.attach_script(root, FarmBuild.CROP)
	root.set("crop_id", JsonUtil.to_str(crop["id"]))
	root.collision_layer = 0
	root.collision_mask = 0
	root.set_collision_layer_value(5, true)  # interactables: a ripe crop is picked with `interact`
	root.monitoring = false
	root.monitorable = true
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile, tile) * 0.8
	shape.shape = rect
	shape.position = Vector2(0.0, -tile * 0.5)
	shape.disabled = true
	root.add_child(shape)
	root.add_child(_strip_sprite(ctx, strip) if not strip.is_empty() else _drawn(crop, tile))
	return root

## The growth strip as a Sprite2D whose frames are the stages; its foot is the origin.
func _strip_sprite(ctx: BuildContext, strip: Dictionary) -> Sprite2D:
	var eff: Dictionary = ctx.catalog.effective(strip)
	var size: Array = eff.get("size", [16, 16])
	var frame: Array = eff.get("frame", size)
	var cell := Vector2i(maxi(1, JsonUtil.to_int(frame[0])), maxi(1, JsonUtil.to_int(frame[1])))
	var origin: Array = eff.get("origin", [cell.x / 2, cell.y - 1])
	var sprite := Sprite2D.new()
	sprite.name = "Visual"
	sprite.texture = load("res://" + JsonUtil.to_str(strip["path"])) as Texture2D
	sprite.hframes = maxi(1, JsonUtil.to_int(size[0]) / cell.x)
	sprite.vframes = maxi(1, JsonUtil.to_int(size[1]) / cell.y)
	sprite.centered = false
	sprite.offset = -Vector2(JsonUtil.to_float(origin[0]), JsonUtil.to_float(origin[1]))
	return sprite

## The stand-in: a green stem the script scales with the stage, and a square of the crop's
## colour on it that is shown when the crop is ripe.
func _drawn(crop: Dictionary, tile: int) -> Node2D:
	var visual := Node2D.new()
	visual.name = "Visual"
	visual.add_child(FarmBuild.stand_in("Stem", Vector2(tile * 0.25, tile * 0.9), FarmBuild.LEAF))
	var fruit := FarmBuild.stand_in("Fruit", Vector2(tile * 0.45, tile * 0.45), FarmBuild.crop_colour(crop))
	fruit.position = Vector2(0.0, -tile * 0.55)
	visual.add_child(fruit)
	return visual

# ---------------------------------------------------------------- the items

func _item(item_id: String, title: String, value: int) -> Resource:
	var item := SeedUtil.make(FarmBuild.ITEM_DEF)
	item.set("id", StringName(item_id))
	item.set("display_name", title)
	item.set("max_stack", 99)
	item.set("value", value)
	return item

func _seeds(crop: Dictionary) -> Resource:
	var item := _item(JsonUtil.to_str(crop["seed"]), "%s seeds" % JsonUtil.to_str(crop["name"]), JsonUtil.to_int(crop.get("seed_price", 0)))
	item.set("category", 6)  # RpgItemDefinition.Category.MATERIAL
	item.set("icon", FarmBuild.drawn_icon("seed", FarmBuild.crop_colour(crop)))
	return item

## What is harvested: its icon is the last picture of the strip (the ripe crop), else drawn.
func _produce(ctx: BuildContext, crop: Dictionary, strip: Dictionary) -> Resource:
	var item := _item(JsonUtil.to_str(crop["produce"]), JsonUtil.to_str(crop["name"]), JsonUtil.to_int(crop.get("price", 0)))
	var icon: Texture2D = null
	if not strip.is_empty():
		icon = FarmBuild.frame_texture(ctx, strip, JsonUtil.to_int(crop.get("stages", 1)) - 1)
	item.set("icon", icon if icon != null else FarmBuild.drawn_icon("produce", FarmBuild.crop_colour(crop)))
	return item
