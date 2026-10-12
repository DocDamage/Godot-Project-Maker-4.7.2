extends RefCounted
## The combat mode's scene of a racing game: boot adds it under SceneRouter as `combat`. It is
## RpgRacingMode with the paths of the lists of tracks and whether a player can be put out of
## the championship.

const RECIPE_VERSION := 2

const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const RaceBuild := preload("racing_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ArcadeBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "kind": "racing", "elimination": RaceBuild.elimination(ctx)})

func build(ctx: BuildContext) -> Array:
	return ArcadeBuild.save_mode(ctx, RaceBuild.MODE_SCRIPT, {"elimination": RaceBuild.elimination(ctx)})
