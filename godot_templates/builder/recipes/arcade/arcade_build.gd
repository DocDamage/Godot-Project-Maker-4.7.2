extends RefCounted
## Node-building helpers of the arcade recipes, shared by the three arcade kinds (the shoot-em-up,
## the run and gun, the racing game): where the framework's scripts are, where a stage's scene
## goes, the combat mode's scene and a drawn stand-in for a thing that has no art.

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const DIR := "res://addons/rpg_runtime/archetypes/arcade/"
const STAGE_SCRIPT := DIR + "stage.gd"
const SCROLLER_SCRIPT := DIR + "scroller.gd"
const BOSS_SCRIPT := DIR + "boss_base.gd"
const MODE_SCRIPT := DIR + "arcade_mode.gd"
const HUD_SCRIPT := DIR + "ui/arcade_hud.gd"
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"

const STAGES_PATH := "res://game/data/stages.json"
const STAGES_DIR := "res://generated/scenes/stages/"
const MODE_PATH := "res://generated/scenes/combat/combat_mode.tscn"

## The scene of the stage `index` (0 is the first): stage_01.tscn, stage_02.tscn, ...
static func stage_path(index: int) -> String:
	return STAGES_DIR + "stage_%02d.tscn" % (index + 1)

## The id of the stage `index` as a map: "stage_01".
static func stage_id(index: int) -> String:
	return "stage_%02d" % (index + 1)

## A rectangle of one colour, `size` px, its middle on the origin: what stands in for an enemy or
## a boss that has no picture.
static func stand_in(node_name: String, size: Vector2, color: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	var half := size * 0.5
	shape.polygon = PackedVector2Array([Vector2(-half.x, -half.y), Vector2(half.x, -half.y), Vector2(half.x, half.y), Vector2(-half.x, half.y)])
	shape.color = color
	return shape

## The combat mode's scene: a node "Combat" with `script_path` (the mode of the kind, which
## extends RpgArcadeMode; the framework's own by default). Returns the issues.
static func save_mode(ctx: BuildContext, script_path: String = MODE_SCRIPT) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Combat"
	if not SceneUtil.attach_script(root, script_path):
		issues.append(ctx.make_issue("VAL-002", {"file": script_path}, script_path))
	root.set("stages_path", STAGES_PATH)
	var err := SceneUtil.save_scene(root, MODE_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": MODE_PATH, "err": err}, MODE_PATH))
	return issues
