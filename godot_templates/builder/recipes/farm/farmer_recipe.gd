extends RefCounted
## The farmer's tools as items (T17.04): game/data/items/hoe.tres, watering_can.tres,
## sickle.tres, farm_axe.tres and fishing_rod.tres (T17.10), seeded once (they are the user's
## afterwards). An icon is the pack's picture of the tool (role TOOL), else the one of the drawn
## farm kit.
##
## The farmer itself is the player scene of actor_recipes with the parts FarmBuild.augment_player
## adds (the script RpgFarmer, the frame on the tile ahead, the icon of the tool in use).
##
## A farm that fights (T17.24, FarmBuild.fights) has its weapon too: game/data/items/farm_sword.tres,
## seeded once, a thing that is kept like a tool (it is not sold back or used up) whose
## `modifiers` say what it adds to the attack. Its icon is a pack's ITEM with `sword` in its name,
## else drawn. A farm that does not fight has neither the file nor anything of it in the hash.

const RECIPE_VERSION := 2
const WEAPON_WORDS: Array[String] = ["sword", "blade", "dagger"]

const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

static func item_path(item_id: String) -> String:
	return FarmBuild.ITEMS_DIR + item_id + ".tres"

func outputs(ctx: BuildContext) -> PackedStringArray:
	var wanted: Array = []
	for tool_id in FarmBuild.TOOL_ORDER:
		wanted.append(item_path(tool_id))
	if FarmBuild.fights(ctx):
		wanted.append(item_path(FarmBuild.WEAPON))
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	var icons := {}
	for tool_id in FarmBuild.TOOL_ORDER:
		icons[tool_id] = FarmBuild.tool_asset(ctx, tool_id).get("id", "")
	var hashed := {"v": RECIPE_VERSION, "icons": icons}
	if FarmBuild.fights(ctx):  # only a farm that fights has the key (T17.24)
		hashed["weapon"] = {"icon": weapon_asset(ctx).get("id", ""), "bonus": FarmBuild.WEAPON_BONUS}
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for tool_id in FarmBuild.TOOL_ORDER:
		var path := item_path(tool_id)
		if FileAccess.file_exists(path):
			continue
		var err := SeedUtil.save(_tool(ctx, tool_id), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var weapon_path := item_path(FarmBuild.WEAPON)
	if FarmBuild.fights(ctx) and not FileAccess.file_exists(weapon_path):
		var err := SeedUtil.save(weapon(ctx), weapon_path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": weapon_path, "err": err}, weapon_path))
	return issues

## A pack's picture of a blade (an ITEM with one of WEAPON_WORDS in its file name), or {}.
static func weapon_asset(ctx: BuildContext) -> Dictionary:
	for asset in ctx.catalog.assets_by_role("ITEM"):
		var eff: Dictionary = ctx.catalog.effective(asset)
		if not FarmBuild._usable(asset) or not ["sprite", "object"].has(JsonUtil.to_str(eff.get("usage", ""))):
			continue
		var file := JsonUtil.to_str(asset.get("path", "")).get_file().get_basename().to_lower()
		for word in WEAPON_WORDS:
			if file.replace("-", "_").split("_", false).has(word):
				return asset
	return {}

## The weapon of a farm that fights (T17.24): kept like a tool, +WEAPON_BONUS to the attack.
static func weapon(ctx: BuildContext) -> Resource:
	var item := SeedUtil.make(FarmBuild.ITEM_DEF)
	item.set("id", StringName(FarmBuild.WEAPON))
	item.set("display_name", "ITEM_FARM_SWORD_NAME")
	item.set("description", "ITEM_FARM_SWORD_DESC")
	item.set("category", 5)  # RpgItemDefinition.Category.KEY: it is not sold back or used up
	item.set("max_stack", 1)
	item.set("value", 0)
	var mods: Array[Dictionary] = [{"stat": "attack", "add": FarmBuild.WEAPON_BONUS, "mul": 1.0}]
	item.set("modifiers", mods)
	var icon := FarmBuild.first_frame(ctx, weapon_asset(ctx))
	item.set("icon", icon if icon != null else FarmBuild.drawn_icon(FarmBuild.WEAPON))
	return item

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
