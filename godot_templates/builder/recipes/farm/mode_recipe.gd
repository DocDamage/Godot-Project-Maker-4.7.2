extends RefCounted
## The farm's mode scene: boot adds it under SceneRouter as `combat`. It is RpgFarmMode (which
## asks for the calendar and makes the energy, the hotbar and the end of the day) with two
## children that hud_recipe.gd makes (T17.11): the farm's HUD (`Hud`: the hotbar's ten slots and
## the energy bar at the bottom of the screen, the time, the date, the weather and the money in
## its top-left corner) and the weather with the pictures of its overlay (`Weather`). The option
## `starter_map.pass_out_loss` is the mode's property of that name, and so are the two of the
## calendar (T17.16): `days_per_season`, and `minute_s` from `starter_map.day_length`. A value
## that is the mode's own default is not written into the scene, so the mode of a farm with the
## default options is the scene it was.

const RECIPE_VERSION := 5
## The folder of the files that are the user's once they exist (crops.json, people.json, ...).
const DATA_DIR := "res://game/data"

const SceneUtil := preload("../../lib/scene_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")
const HudRecipe := preload("hud_recipe.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([FarmBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "pass_out_loss": FarmBuild.pass_out_loss(ctx), "days": FarmBuild.days_per_season(ctx), "minute_s": FarmBuild.minute_s(ctx), "hud": HudRecipe.mode_hash(ctx)})

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
	root.add_child(HudRecipe.build_hud(ctx))
	root.add_child(HudRecipe.build_weather(ctx))
	var err := SceneUtil.save_scene(root, FarmBuild.MODE_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FarmBuild.MODE_PATH, "err": err}, FarmBuild.MODE_PATH))
	return issues
