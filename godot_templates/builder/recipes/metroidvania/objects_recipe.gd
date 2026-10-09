extends RefCounted
## The scenes of a side-view room that are not characters: the room camera (and, from later
## cards, the save station, the ability pickup and the room exit). Rooms instance them, and they
## are in the editor's dock like every generated scene.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MvBuild := preload("metroidvania_build.gd")

const OUT_DIR := "res://generated/scenes/metroidvania/"
const CAMERA_PATH := OUT_DIR + "side_camera.tscn"
const CAMERA_SCRIPT := MvBuild.DIR + "side_camera.gd"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([CAMERA_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "tile": tile_size(ctx)})

static func tile_size(ctx: BuildContext) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return JsonUtil.to_int(def["tile_size"][0]) if not def.is_empty() else JsonUtil.to_int(ctx.config.get("base_tile_size", 16))

## The camera a room owns (RpgSideCamera), enabled, not yet in a room.
static func build_camera(tile: int) -> Camera2D:
	var camera := Camera2D.new()
	camera.name = "Camera"
	SceneUtil.attach_script(camera, CAMERA_SCRIPT)
	camera.set("tile_size", float(tile))
	camera.enabled = true
	return camera

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := tile_size(ctx)
	_save(ctx, build_camera(tile), CAMERA_PATH, issues)
	return issues

func _save(ctx: BuildContext, node: Node, path: String, issues: Array) -> void:
	var err := SceneUtil.save_scene(node, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
