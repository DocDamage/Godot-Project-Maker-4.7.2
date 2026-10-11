extends RefCounted
## The combat mode's scene of a shoot-em-up: boot adds it under SceneRouter as `combat`. It is
## RpgShmupMode with the orientation of the options and the path of the stage list.

const RECIPE_VERSION := 1

const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const ShmupBuild := preload("shmup_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ArcadeBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "orientation": ShmupBuild.orientation(ctx)})

func build(ctx: BuildContext) -> Array:
	return ArcadeBuild.save_mode(ctx, ShmupBuild.MODE_SCRIPT, {"orientation": ShmupBuild.orientation(ctx)})
