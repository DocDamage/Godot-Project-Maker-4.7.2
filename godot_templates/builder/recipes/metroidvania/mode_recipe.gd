extends RefCounted
## The metroidvania's combat mode scene: boot adds it under SceneRouter as `combat`. It holds the
## defeat policy and the rules of saving (RpgMetroidvaniaMode).

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const OUT_PATH := "res://generated/scenes/combat/combat_mode.tscn"
const SCRIPT_PATH := "res://addons/rpg_runtime/archetypes/metroidvania/metroidvania_mode.gd"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Combat"
	if not SceneUtil.attach_script(root, SCRIPT_PATH):
		issues.append(ctx.make_issue("VAL-002", {"file": SCRIPT_PATH}, SCRIPT_PATH))
	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
