extends RefCounted
## Node-building helpers of the action-RPG recipes: the combat parts of the player and of the enemies.
## Shared by builder/recipes/actor_recipes.gd (player) and arpg/enemy_recipes.gd (enemies).
##
## Physics layers (ARCHITECTURE §17): player hitbox 7 (mask 10), enemy hitbox 8 (mask 9), player
## hurtbox 9, enemy hurtbox 10; enemies 3 (they look at world 1 and the player 2).

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")

const DIR := "res://addons/rpg_runtime/archetypes/arpg/"
const HEALTH := DIR + "health.gd"
const HURTBOX := DIR + "hurtbox.gd"
const HITBOX := DIR + "hitbox.gd"
const PLAYER_COMBAT := DIR + "player_combat.gd"
const SWING_EFFECT := DIR + "swing_effect.gd"
const ENEMY_AI := DIR + "enemy_ai.gd"
const DETECTION := DIR + "components/detection.gd"
const CHASE := DIR + "components/chase.gd"
const WANDER := DIR + "components/wander.gd"
const ENEMY_ATTACK := DIR + "components/enemy_attack.gd"
const LOOT_DROP := DIR + "components/loot_drop.gd"

const PLAYER_INVULN_S := 0.6
const ENEMY_INVULN_S := 0.15

## Size of the hurtbox: the body of the character, not the whole frame.
static func body_size(frame: Vector2i, tile: int) -> Vector2:
	return Vector2(clampf(frame.x * 0.5, 6.0, maxf(6.0, tile * 0.75)), clampf(frame.y * 0.6, 8.0, maxf(8.0, tile * 1.25)))

## Middle of the body, relative to the feet.
static func body_center(frame: Vector2i) -> Vector2:
	return Vector2(0.0, -frame.y * 0.5)

## How far the attack area sits from the body center toward the facing direction.
static func reach(frame: Vector2i, tile: int) -> Vector2:
	var limit := maxf(4.0, tile * 0.75)
	return Vector2(minf(frame.x * 0.5, limit), minf(frame.y * 0.5, limit))

static func _shape(size: Vector2, disabled: bool = false) -> CollisionShape2D:
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	shape.disabled = disabled
	return shape

static func _layers(area: CollisionObject2D, layer: int, mask: Array) -> void:
	area.collision_layer = 0
	area.collision_mask = 0
	area.set_collision_layer_value(layer, true)
	for m: Variant in mask:
		area.set_collision_mask_value(JsonUtil.to_int(m), true)

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
	_layers(hurtbox, layer, [])
	hurtbox.monitoring = false
	hurtbox.monitorable = true
	hurtbox.position = body_center(frame)
	hurtbox.add_child(_shape(body_size(frame, tile)))
	root.add_child(hurtbox)
	return hurtbox

## `size_factor` scales the tile-sized shape (the player 0.9, enemies a little more because their
## reach is measured between feet).
static func add_hitbox(root: Node, team: String, layer: int, mask: int, frame: Vector2i, tile: int, size_factor: float) -> Area2D:
	var hitbox := Area2D.new()
	hitbox.name = "AttackHitbox"
	SceneUtil.attach_script(hitbox, HITBOX)
	hitbox.set("team", StringName(team))
	hitbox.set("center", body_center(frame))
	hitbox.set("reach", reach(frame, tile))
	_layers(hitbox, layer, [mask])
	hitbox.monitoring = false
	hitbox.monitorable = false
	hitbox.position = body_center(frame)
	hitbox.add_child(_shape(Vector2(tile, tile) * size_factor, true))
	root.add_child(hitbox)
	return hitbox

## Health, Hurtbox, AttackHitbox, SwingEffect and PlayerCombat on a player actor.
static func augment_player(root: Node, frame: Vector2i, _origin: Vector2i, tile: int) -> void:
	add_health(root)
	add_hurtbox(root, "player", 9, PLAYER_INVULN_S, frame, tile)
	add_hitbox(root, "player", 7, 10, frame, tile, 0.9)
	var swing := AnimatedSprite2D.new()
	swing.name = "SwingEffect"
	SceneUtil.attach_script(swing, SWING_EFFECT)
	root.add_child(swing)
	var combat := Node.new()
	combat.name = "PlayerCombat"
	SceneUtil.attach_script(combat, PLAYER_COMBAT)
	root.add_child(combat)

## The enemy parts. `root` is an actor built by ActorBuild ("base") that already has the enemy
## script; `agent` keeps the NavigationAgent2D enabled (nav_mode "agent").
static func augment_enemy(root: CharacterBody2D, frame: Vector2i, tile: int, agent: bool) -> void:
	root.collision_layer = 0
	root.set_collision_layer_value(3, true)  # enemies
	root.collision_mask = 0
	root.set_collision_mask_value(1, true)  # world
	root.set_collision_mask_value(2, true)  # player
	var components := root.get_node("Components")
	for part: Array in [["Detection", DETECTION], ["Chase", CHASE], ["Wander", WANDER], ["EnemyAttack", ENEMY_ATTACK], ["LootDrop", LOOT_DROP]]:
		var node := Node.new()
		node.name = part[0]
		var part_script: String = part[1]
		SceneUtil.attach_script(node, part_script)
		components.add_child(node)
	add_health(root)
	add_hurtbox(root, "enemy", 10, ENEMY_INVULN_S, frame, tile)
	add_hitbox(root, "enemy", 8, 9, frame, tile, 1.1)
	var sight := RayCast2D.new()
	sight.name = "Sight"
	sight.position = Vector2(0, -2)
	sight.collision_mask = 1  # world
	sight.collide_with_areas = false
	sight.collide_with_bodies = true
	sight.exclude_parent = true
	root.add_child(sight)
	var nav := NavigationAgent2D.new()
	nav.name = "Navigation"
	nav.path_desired_distance = 4.0
	nav.target_desired_distance = maxf(4.0, tile * 0.5)
	if not agent:
		nav.process_mode = Node.PROCESS_MODE_DISABLED
	root.add_child(nav)
	var alert := Label.new()
	alert.name = "Alert"
	alert.text = "!"
	alert.visible = false
	alert.z_index = 2
	alert.modulate = Color(1.0, 0.35, 0.3)
	alert.position = Vector2(-3, -frame.y - 14)
	root.add_child(alert)
