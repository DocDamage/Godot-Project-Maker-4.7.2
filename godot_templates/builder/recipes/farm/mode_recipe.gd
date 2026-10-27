extends RefCounted
## The farm's mode scene: boot adds it under SceneRouter as `combat`. It is RpgFarmMode (which
## asks for the calendar and makes the energy, the hotbar and the end of the day) with two
## children that hud_recipe.gd makes (T17.11): the farm's HUD (`Hud`: the hotbar's ten slots and
## the energy bar at the bottom of the screen, the time, the date, the weather and the money in
## its top-left corner) and the weather with the pictures of its overlay (`Weather`). The option
## `starter_map.pass_out_loss` is the mode's property of that name, and so are the two of the
## calendar (T17.16): `days_per_season`, and `minute_s` from `starter_map.day_length`. A value
## that is the mode's own default is not written into the scene, so the mode of a farm with the
## default options is the scene it was. `festivals` (T17.25) is the mode's property of that
## name: true in a farm with `starter_map.festivals` on whose plan has its festivals, and not
## written (nor in the hash) in any other, whose mode is the scene it was. `fights` (T17.24)
## the same for a farm that fights (FarmBuild.fights), whose HUD has the farmer's health too.
## `courting` (T17.26) is the same for marriage: true in a farm with `starter_map.courtable`
## above 0 whose plan has somebody to court. `exhaustion_ends_day` (T18.11) the same for the
## option `starter_map.exhaustion`, which a farm made before the card lacks.

const RECIPE_VERSION := 5
## The folder of the files that are the user's once they exist (crops.json, people.json, ...).
const DATA_DIR := "res://game/data"

const SceneUtil := preload("../../lib/scene_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")
const HudRecipe := preload("hud_recipe.gd")
const ActorRecipes := preload("../actor_recipes.gd")
const JsonUtil := preload("../../lib/json_util.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([FarmBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	var hashed := {"v": RECIPE_VERSION, "pass_out_loss": FarmBuild.pass_out_loss(ctx), "days": FarmBuild.days_per_season(ctx), "minute_s": FarmBuild.minute_s(ctx), "hud": HudRecipe.mode_hash(ctx)}
	if FarmBuild.festivals(ctx):  # only a farm with festivals has the key (T17.25)
		hashed["festivals"] = true
	if FarmBuild.fights(ctx):  # only a farm that fights has the key (T17.24)
		hashed["fights"] = true
	if FarmBuild.courting(ctx):  # only a farm with marriage has the key (T17.26)
		hashed["courting"] = true
	if FarmBuild.exhaustion(ctx):  # only a farm with the option has the key (T18.11)
		hashed["exhaustion"] = true
	if FarmBuild.crafts(ctx):  # only a farm that crafts has the key (T18.15)
		hashed["crafting"] = true
	if FarmBuild.children(ctx):  # only a farm with children has the key (T18.17)
		hashed["children"] = {"scene": child_scene(ctx)}
	if FarmBuild.cooking(ctx):  # only a farm that cooks has the keys (T18.16)
		hashed["cooking"] = {"stove": stove_for_sale(ctx)}
	return ctx.stable_hash(hashed)

## The scene of a child of the packs (the character scene of its NPC), or "" (the spouse's own,
## smaller, stands in).
static func child_scene(ctx: BuildContext) -> String:
	var asset := FarmBuild.child_asset(ctx)
	if asset.is_empty():
		return ""
	return ActorRecipes.character_scene_path(JsonUtil.to_str(asset["id"]))

## True when the farmhouse room exists and was built without a kitchen (before the farm cooked):
## its shop then sells a stove. A room that is not there yet is built with one.
static func stove_for_sale(_ctx: BuildContext) -> bool:
	var room := "res://game/maps/farm_house.tscn"
	return FileAccess.file_exists(room) and not FileAccess.get_file_as_string(room).contains("station_id = &\"kitchen\"")

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Combat"
	if not SceneUtil.attach_script(root, FarmBuild.MODE):
		issues.append(ctx.make_issue("VAL-002", {"file": FarmBuild.MODE}, FarmBuild.MODE))
	root.set("pass_out_loss", FarmBuild.pass_out_loss(ctx))
	root.set("days_per_season", FarmBuild.days_per_season(ctx))
	root.set("minute_s", FarmBuild.minute_s(ctx))
	root.set("data_dir", DATA_DIR)
	if FarmBuild.festivals(ctx):
		root.set("festivals", true)
	if FarmBuild.fights(ctx):
		root.set("fights", true)
	if FarmBuild.courting(ctx):
		root.set("courting", true)
	if FarmBuild.exhaustion(ctx):
		root.set("exhaustion_ends_day", true)
	if FarmBuild.crafts(ctx):
		root.set("crafting", true)
	if FarmBuild.children(ctx):
		root.set("children", true)
		root.set("child_scene", child_scene(ctx))
	if FarmBuild.cooking(ctx):
		root.set("cooking", true)
		if stove_for_sale(ctx):
			root.set("stove_for_sale", true)
	root.add_child(HudRecipe.build_hud(ctx, FarmBuild.fights(ctx)))
	root.add_child(HudRecipe.build_weather(ctx))
	var err := SceneUtil.save_scene(root, FarmBuild.MODE_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FarmBuild.MODE_PATH, "err": err}, FarmBuild.MODE_PATH))
	return issues
