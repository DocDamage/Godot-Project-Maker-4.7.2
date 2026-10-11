extends RefCounted
## generated/scenes/ui/hud_arcade.tscn for a shoot-em-up: a CanvasLayer with RpgShmupHud (the
## arcade HUD with the bombs, the weapon and the high score). A game that scrolls up gets the
## side panels. Boot uses this scene in place of hud_basic.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeHud := preload("../arcade/hud_recipe.gd")
const ShmupBuild := preload("shmup_build.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([ArcadeHud.OUT_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "kind": "shmup", "orientation": ShmupBuild.orientation(ctx)})

static func build_hud(way: String) -> CanvasLayer:
	var root := ArcadeHud.build_hud(ArcadeHud.script_for("shmup"))
	root.set("panels", way != "horizontal")
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var err := SceneUtil.save_scene(build_hud(ShmupBuild.orientation(ctx)), ArcadeHud.OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeHud.OUT_PATH, "err": err}, ArcadeHud.OUT_PATH))
	return issues
