extends RefCounted
## Builds the bootstrap scene that switches to the game's first scene.

const RECIPE_VERSION := 1

const SceneUtil := preload("../lib/scene_util.gd")

const OUT_PATH := "res://generated/scenes/bootstrap/boot.tscn"
const SCRIPT_PATH := "res://addons/rpg_runtime/core/boot.gd"
# M6 changes this to the title screen.
const FIRST_SCENE := "res://game/maps/starter_map.tscn"

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func input_hash(ctx) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "first_scene": FIRST_SCENE})

func build(ctx) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Boot"
	root.set_script(load(SCRIPT_PATH))
	root.set("first_scene", FIRST_SCENE)
	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
