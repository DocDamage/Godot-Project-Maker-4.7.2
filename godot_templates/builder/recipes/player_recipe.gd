extends RefCounted
## Builds res://generated/scenes/actors/player.tscn from the first PLAYER asset.

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const SceneUtil := preload("../lib/scene_util.gd")

const OUT_PATH := "res://generated/scenes/actors/player.tscn"
const SCRIPT_PATH := "res://addons/rpg_runtime/actors/player_controller.gd"

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func _player_asset(ctx) -> Dictionary:
	var candidates: Array = ctx.catalog.assets_by_role("PLAYER")
	return candidates[0] if candidates.size() > 0 else {}

func input_hash(ctx) -> String:
	var asset := _player_asset(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"id": asset.get("id", ""),
		"sha256": asset.get("sha256", ""),
		"eff": ctx.catalog.effective(asset) if not asset.is_empty() else {},
	})

func build(ctx) -> Array:
	var issues: Array = []
	var asset := _player_asset(ctx)
	if asset.is_empty():
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "player_recipe", "reason": "no asset with role PLAYER in the catalog"}))
		return issues
	var eff: Dictionary = ctx.catalog.effective(asset)
	var frames_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % asset["id"]
	var frames := load(frames_path) as SpriteFrames
	if frames == null:
		issues.append(ctx.make_issue("VAL-002", {"file": frames_path}, frames_path))
		return issues
	var frame: Vector2i = ctx.vec2i(eff.get("frame", [16, 24]))
	var origin: Vector2i = ctx.vec2i(eff.get("origin", [frame.x / 2, frame.y - 1]))

	var root := CharacterBody2D.new()
	root.name = "Player"
	root.set_script(load(SCRIPT_PATH))
	root.motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	root.set_collision_layer_value(2, true)  # player
	for layer in [1, 3, 4]:  # world, enemies, npcs
		root.set_collision_mask_value(layer, true)
	root.add_to_group("player", true)

	var visual := AnimatedSprite2D.new()
	visual.name = "Visual"
	visual.sprite_frames = frames
	visual.centered = false
	visual.offset = -Vector2(origin)  # node origin = feet
	if frames.has_animation("idle_down"):
		visual.animation = "idle_down"
	root.add_child(visual)

	var feet := CollisionShape2D.new()
	feet.name = "Feet"
	var shape := RectangleShape2D.new()
	shape.size = Vector2(frame.x * 0.6, 6.0)
	feet.shape = shape
	feet.position = Vector2(0, -3)
	root.add_child(feet)

	var cam := Camera2D.new()
	cam.name = "Camera"
	cam.enabled = true
	root.add_child(cam)

	var err := SceneUtil.save_scene(root, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues
