extends RefCounted
## generated/scenes/ui/hud_arcade.tscn: the HUD of the arcade kinds, a CanvasLayer with
## RpgArcadeHud (lives, score, multiplier, the stage, a boss's health). Boot uses this scene in
## place of hud_basic. The rows of a kind (bombs, the weapon, the lap) are added by its own code.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("arcade_build.gd")

const OUT_PATH := "res://generated/scenes/ui/hud_arcade.tscn"
## The HUD script of a kind that has rows of its own; the framework's otherwise.
const KIND_SCRIPTS := {
	"shmup": "res://addons/rpg_runtime/archetypes/shmup/ui/shmup_hud.gd",
	"run_and_gun": "res://addons/rpg_runtime/archetypes/run_and_gun/ui/run_and_gun_hud.gd",
}

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

static func script_for(archetype: String) -> String:
	var own: String = KIND_SCRIPTS.get(archetype, "")
	return own if own != "" else ArcadeBuild.HUD_SCRIPT

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "script": script_for(str(ctx.config.get("archetype", "")))})

static func build_hud(script_path: String = ArcadeBuild.HUD_SCRIPT) -> CanvasLayer:
	var root := CanvasLayer.new()
	root.name = "HudArcade"
	SceneUtil.attach_script(root, script_path)
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var err := SceneUtil.save_scene(build_hud(script_for(str(ctx.config.get("archetype", "")))), OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
