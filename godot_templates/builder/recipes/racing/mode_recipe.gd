extends RefCounted
## The combat mode's scene of a racing game: boot adds it under SceneRouter as `combat`. It is
## RpgRacingMode with the paths of the lists of tracks.

const RECIPE_VERSION := 1

const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const RaceBuild := preload("racing_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ArcadeBuild.MODE_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "kind": "racing"})

func build(ctx: BuildContext) -> Array:
	return ArcadeBuild.save_mode(ctx, RaceBuild.MODE_SCRIPT, {})
