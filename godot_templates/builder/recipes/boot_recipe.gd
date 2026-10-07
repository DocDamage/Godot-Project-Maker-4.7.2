extends RefCounted
## Builds the bootstrap scene that switches to the game's first scene.

const RECIPE_VERSION := 2

const SceneUtil := preload("../lib/scene_util.gd")

const OUT_PATH := "res://generated/scenes/bootstrap/boot.tscn"
const SCRIPT_PATH := "res://addons/rpg_runtime/core/boot.gd"
const FIRST_SCENE := "res://generated/scenes/ui/title_screen.tscn"

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func input_hash(ctx) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "first_scene": FIRST_SCENE, "debug": _debug_tools(ctx)})

func _debug_tools(ctx) -> bool:
	return bool(ctx.config.get("features", {}).get("debug_tools", false))

func build(ctx) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Boot"
	root.set_script(load(SCRIPT_PATH))
	root.set("first_scene", FIRST_SCENE)
	root.set("debug_tools", _debug_tools(ctx))
	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
