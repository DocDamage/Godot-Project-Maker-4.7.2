extends RefCounted
## Node-building helpers of the metroidvania recipes: the body and the combat parts of a side-view
## character. Shared by player_recipe.gd (the player and the NPCs) and enemy_recipes.gd.
##
## Physics layers (ARCHITECTURE §17): world 1, player 2, enemies 3, npcs 4, interactables 5,
## player hitbox 7 (mask 10), enemy hitbox 8 (mask 9), player hurtbox 9, enemy hurtbox 10, and
## one_way 11 (the platforms a character jumps through from below).

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")

const DIR := "res://addons/rpg_runtime/archetypes/metroidvania/"
const REALTIME_DIR := "res://addons/rpg_runtime/combat/realtime/"
const HEALTH := REALTIME_DIR + "health.gd"
const HURTBOX := REALTIME_DIR + "hurtbox.gd"
const HITBOX := REALTIME_DIR + "hitbox.gd"
const STATS_SCRIPT := "res://addons/rpg_runtime/actors/components/stats_component.gd"

const ONE_WAY_LAYER := 11
const PLAYER_INVULN_S := 0.6
const ENEMY_INVULN_S := 0.15

## The solid part of a character: narrower than its frame, and not taller than a tile and a half.
static func body_size(frame: Vector2i, tile: int) -> Vector2:
	return Vector2(clampf(frame.x * 0.4, 6.0, maxf(6.0, tile * 0.75)), clampf(frame.y * 0.75, 8.0, maxf(8.0, tile * 1.5)))

## Middle of the body, relative to the feet.
static func body_center(frame: Vector2i, tile: int) -> Vector2:
	return Vector2(0.0, -body_size(frame, tile).y * 0.5)

static func rect_shape(size: Vector2, shape_name: String = "Shape", disabled: bool = false) -> CollisionShape2D:
	var shape := CollisionShape2D.new()
	shape.name = shape_name
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	shape.disabled = disabled
	return shape

static func set_layers(node: CollisionObject2D, layers: Array, mask: Array) -> void:
	node.collision_layer = 0
	node.collision_mask = 0
	for l: Variant in layers:
		node.set_collision_layer_value(JsonUtil.to_int(l), true)
	for m: Variant in mask:
		node.set_collision_mask_value(JsonUtil.to_int(m), true)

## A CharacterBody2D with `script_path`, the sprite ("Visual", its origin at the feet) and the
## body shape ("Body"). The caller sets the layers.
static func body(root_name: String, script_path: String, frames: SpriteFrames, frame: Vector2i, origin: Vector2i, tile: int) -> CharacterBody2D:
	var root := CharacterBody2D.new()
	root.name = root_name
	root.motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
	SceneUtil.attach_script(root, script_path)
	root.set("tile_size", float(tile))
	var visual := AnimatedSprite2D.new()
	visual.name = "Visual"
	visual.centered = false
	visual.offset = -Vector2(origin)
	if frames != null:
		visual.sprite_frames = frames
		for anim: String in ["idle_right", "idle_side", "idle", "idle_down", "walk_right", "walk_down"]:
			if frames.has_animation(anim):
				visual.animation = anim
				break
	root.add_child(visual)
	var size := body_size(frame, tile)
	var shape := rect_shape(size, "Body")
	shape.position = Vector2(0.0, -size.y * 0.5)
	root.add_child(shape)
	var components := Node.new()
	components.name = "Components"
	root.add_child(components)
	var stats := Node.new()
	stats.name = "Stats"
	SceneUtil.attach_script(stats, STATS_SCRIPT)
	components.add_child(stats)
	return root

static func add_health(root: Node) -> Node:
	var health := Node.new()
	health.name = "Health"
	SceneUtil.attach_script(health, HEALTH)
	root.add_child(health)
	return health

static func add_hurtbox(root: Node, team: String, layer: int, invuln_s: float, frame: Vector2i, tile: int) -> Area2D:
	var hurtbox := Area2D.new()
	hurtbox.name = "Hurtbox"
	SceneUtil.attach_script(hurtbox, HURTBOX)
	hurtbox.set("team", StringName(team))
	hurtbox.set("invuln_s", invuln_s)
	set_layers(hurtbox, [layer], [])
	hurtbox.monitoring = false
	hurtbox.monitorable = true
	hurtbox.position = body_center(frame, tile)
	hurtbox.add_child(rect_shape(body_size(frame, tile)))
	root.add_child(hurtbox)
	return hurtbox

## The attack area: `reach_x` px from the body's middle toward the facing side.
static func add_hitbox(root: Node, team: String, layer: int, mask: int, frame: Vector2i, tile: int, size: Vector2, reach_x: float) -> Area2D:
	var hitbox := Area2D.new()
	hitbox.name = "AttackHitbox"
	SceneUtil.attach_script(hitbox, HITBOX)
	hitbox.set("team", StringName(team))
	hitbox.set("center", body_center(frame, tile))
	hitbox.set("reach", Vector2(reach_x, 0.0))
	set_layers(hitbox, [layer], [mask])
	hitbox.monitoring = false
	hitbox.monitorable = false
	hitbox.position = body_center(frame, tile) + Vector2(reach_x, 0.0)
	hitbox.add_child(rect_shape(size, "Shape", true))
	root.add_child(hitbox)
	return hitbox
