extends RefCounted
## Builds the bootstrap scene that switches to the game's first scene.

const RECIPE_VERSION := 4

const SceneUtil := preload("../lib/scene_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const OUT_PATH := "res://generated/scenes/bootstrap/boot.tscn"
const SCRIPT_PATH := "res://addons/rpg_runtime/core/boot.gd"
const FIRST_SCENE := "res://generated/scenes/ui/title_screen.tscn"
## Built by the archetype's recipes (builder/recipes/<archetype>/); absent until one exists.
const COMBAT_SCENE := "res://generated/scenes/combat/combat_mode.tscn"
## The archetype's own HUD (builder/recipes/<archetype>/hud_recipe.gd); hud_basic otherwise.
const ARCHETYPE_HUD := "res://generated/scenes/ui/hud_arpg.tscn"
const ARCHETYPE_HUD_NAME := "hud_arpg"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "first_scene": FIRST_SCENE, "combat": _combat_scene(), "debug": _debug_tools(ctx), "hud": _hud_scene()})

func _combat_scene() -> String:
	return COMBAT_SCENE if FileAccess.file_exists(COMBAT_SCENE) else ""

func _hud_scene() -> String:
	return ARCHETYPE_HUD_NAME if FileAccess.file_exists(ARCHETYPE_HUD) else "hud_basic"

func _debug_tools(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ctx.section("features").get("debug_tools", false))

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Boot"
	root.set_script(load(SCRIPT_PATH))
	root.set("first_scene", FIRST_SCENE)
	root.set("combat_scene", _combat_scene())
	root.set("debug_tools", _debug_tools(ctx))
	root.set("hud_scene", _hud_scene())
	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
