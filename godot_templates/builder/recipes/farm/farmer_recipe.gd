extends RefCounted
## The farmer's tools as items (T17.04): game/data/items/hoe.tres, watering_can.tres,
## sickle.tres, farm_axe.tres and fishing_rod.tres (T17.10), seeded once (they are the user's
## afterwards). An icon is the pack's picture of the tool (role TOOL), else the one of the drawn
## farm kit.
##
## The farmer itself is the player scene of actor_recipes with the parts FarmBuild.augment_player
## adds (the script RpgFarmer, the frame on the tile ahead, the icon of the tool in use).

const RECIPE_VERSION := 2

const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

static func item_path(item_id: String) -> String:
	return FarmBuild.ITEMS_DIR + item_id + ".tres"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var wanted: Array = []
	for tool_id in FarmBuild.TOOL_ORDER:
		wanted.append(item_path(tool_id))
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	var icons := {}
	for tool_id in FarmBuild.TOOL_ORDER:
		icons[tool_id] = FarmBuild.tool_asset(ctx, tool_id).get("id", "")
	return ctx.stable_hash({"v": RECIPE_VERSION, "icons": icons})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for tool_id in FarmBuild.TOOL_ORDER:
		var path := item_path(tool_id)
		if FileAccess.file_exists(path):
			continue
		var err := SeedUtil.save(_tool(ctx, tool_id), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

func _tool(ctx: BuildContext, tool_id: String) -> Resource:
	var item := SeedUtil.make(FarmBuild.ITEM_DEF)
	item.set("id", StringName(tool_id))
	item.set("display_name", "ITEM_%s_NAME" % tool_id.to_upper())
	item.set("description", "ITEM_%s_DESC" % tool_id.to_upper())
	item.set("category", 5)  # RpgItemDefinition.Category.KEY: it is not sold or used up
	item.set("max_stack", 1)
	item.set("value", 0)
	var icon := FarmBuild.first_frame(ctx, FarmBuild.tool_asset(ctx, tool_id))
	item.set("icon", icon if icon != null else FarmBuild.drawn_icon(tool_id))
	return item
