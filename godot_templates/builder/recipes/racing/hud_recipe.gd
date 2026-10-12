extends RefCounted
## generated/scenes/ui/hud_arcade.tscn for a racing game: a CanvasLayer with RpgRacingHud (the
## arcade HUD with the lap, the place, the speed, what the car carries, the sign in the middle
## of the screen and the map of the track). Boot uses this scene in place of hud_basic.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeHud := preload("../arcade/hud_recipe.gd")
const RaceBuild := preload("racing_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ArcadeHud.OUT_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "kind": "racing"})

## The HUD; `track_map`: with the map of the track in its corner.
static func build_hud(track_map: bool = true) -> CanvasLayer:
	var root := ArcadeHud.build_hud(RaceBuild.HUD_SCRIPT)
	root.set("track_map", track_map)
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var err := SceneUtil.save_scene(build_hud(), ArcadeHud.OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeHud.OUT_PATH, "err": err}, ArcadeHud.OUT_PATH))
	return issues
