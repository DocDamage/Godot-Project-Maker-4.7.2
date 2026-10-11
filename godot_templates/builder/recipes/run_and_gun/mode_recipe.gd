extends RefCounted
## The combat mode's scene of a run and gun: boot adds it under SceneRouter as `combat`. It is
## RpgRunAndGunMode with the lives of the options and the paths of the stage lists.

const RECIPE_VERSION := 1

const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const RngBuild := preload("run_and_gun_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ArcadeBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "kind": "run_and_gun", "lives": RngBuild.lives(ctx)})

func build(ctx: BuildContext) -> Array:
	return ArcadeBuild.save_mode(ctx, RngBuild.MODE_SCRIPT, {"start_lives": RngBuild.lives(ctx)})
