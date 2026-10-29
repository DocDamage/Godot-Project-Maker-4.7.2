class_name RpgAssist
extends Node
## Follower component of the action RPG (T13.15): a party member that walks behind the player
## (RpgFollowers) helps in a fight. When an enemy is within ENGAGE_TILES of the player the follower
## walks beside it and swings its own RpgHitbox every SWING_EVERY_S with the member's stats. It
## never leaves LEASH_TILES of the player. It can be hit (a hurtbox of the player's team) but it
## cannot die: at 0 HP it is "downed" for DOWNED_S, then it is back at full health.
##
## RpgArpgMode.customize_follower() adds it (attach) to the first MAX_ASSISTS followers. While it
## fights it sets the follower's meta "held", so RpgFollowers leaves the node alone and tells it
## where its place on the trail is (meta "home"); it walks back there before it lets go.

signal downed
signal recovered

const NODE_NAME := "Assist"
const MAX_ASSISTS := 2
const ENGAGE_TILES := 3.0
const LEASH_TILES := 6.0
const SWING_EVERY_S := 1.2
const SWING_ACTIVE_S := 0.15
const DOWNED_S := 5.0
## Tiles per second while it walks to an enemy or back to the trail.
const SPEED_TILES := 5.0
## It swings when its feet are this close to the enemy's (tiles).
const REACH_TILES := 1.5
const INVULN_S := 0.6
const DOWNED_ALPHA := 0.35

## False switches the helping off (the follower only follows).
var enabled := true
var stats: RpgStats
var tile := 16.0
var follower: Node2D
var hitbox: RpgHitbox
var hurtbox: RpgHurtbox
var health: RpgHealth
var target: Node2D = null
var downed_left := 0.0
var cooldown_left := 0.0

var _active_left := 0.0
var _driver := RpgAnimationDriver.new()

## Gives `node` (a follower made by RpgFollowers) the parts of a fighter and the component:
## Stats, Health, Hurtbox (layer 9, the player's team), AttackHitbox (layer 7, mask 10), Assist.
static func attach(node: Node2D, member_stats: RpgStats, tile_px: float) -> RpgAssist:
	var frame := _frame_size(node)
	var stats_node := RpgStatsComponent.new()
	stats_node.name = "Stats"
	stats_node.stats = member_stats
	node.add_child(stats_node)
	var health_node := RpgHealth.new()
	health_node.name = "Health"
	health_node.stats_path = NodePath("../Stats")
	node.add_child(health_node)
	var body := Vector2(clampf(frame.x * 0.5, 6.0, maxf(6.0, tile_px * 0.75)), clampf(frame.y * 0.6, 8.0, maxf(8.0, tile_px * 1.25)))
	var hurt := RpgHurtbox.new()
	hurt.name = "Hurtbox"
	hurt.team = &"player"
	hurt.invuln_s = INVULN_S
	hurt.collision_layer = 0
	hurt.collision_mask = 0
	hurt.set_collision_layer_value(9, true)
	hurt.monitoring = false
	hurt.position = Vector2(0.0, -frame.y * 0.5)
	hurt.add_child(_shape(body, false))
	node.add_child(hurt)
	var hit := RpgHitbox.new()
	hit.name = "AttackHitbox"
	hit.team = &"player"
	hit.center = Vector2(0.0, -frame.y * 0.5)
	var limit := maxf(4.0, tile_px * 0.75)
	hit.reach = Vector2(minf(frame.x * 0.5, limit), minf(frame.y * 0.5, limit))
	hit.collision_layer = 0
	hit.collision_mask = 0
	hit.set_collision_layer_value(7, true)
	hit.set_collision_mask_value(10, true)
	hit.monitorable = false
	hit.position = hit.center
	hit.add_child(_shape(Vector2(tile_px, tile_px), true))
	node.add_child(hit)
	var assist := RpgAssist.new()
	assist.name = NODE_NAME
	assist.stats = member_stats
	assist.tile = tile_px
	assist.follower = node
	assist.hitbox = hit
	assist.hurtbox = hurt
	assist.health = health_node
	assist._driver.sprite = node.get_node_or_null("Visual") as AnimatedSprite2D
	health_node.died.connect(assist.go_down)
	node.add_child(assist)
	if member_stats != null and member_stats.hp <= 0:  # saved while it was down
		assist.go_down()
	return assist

static func _shape(size: Vector2, disabled: bool) -> CollisionShape2D:
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	shape.disabled = disabled
	return shape

static func _frame_size(node: Node2D) -> Vector2:
	var visual := node.get_node_or_null("Visual") as AnimatedSprite2D
	var frames: SpriteFrames = visual.sprite_frames if visual != null else null
	if frames != null:
		for anim in frames.get_animation_names():
			if frames.get_frame_count(anim) > 0 and frames.get_frame_texture(anim, 0) != null:
				return frames.get_frame_texture(anim, 0).get_size()
	return Vector2(16, 16)

## The enemy the follower helps against: the living one nearest to the player within `radius`, or
## null. `enemies` are nodes with a "health" (RpgEnemyAi).
static func nearest_enemy(player_at: Vector2, enemies: Array[Node2D], radius: float) -> Node2D:
	var best: Node2D = null
	var best_d := radius
	for enemy in enemies:
		if not is_instance_valid(enemy) or enemy.is_queued_for_deletion():
			continue
		var found: Object = enemy.get("health")
		var enemy_health := found as RpgHealth
		if enemy_health != null and enemy_health.is_dead():
			continue
		var d := RpgUtil.world_position(enemy).distance_to(player_at)
		if d <= best_d:
			best = enemy
			best_d = d
	return best

## `point`, pulled back to `radius` around `center` when it is further away.
static func leashed(point: Vector2, center: Vector2, radius: float) -> Vector2:
	var away := point - center
	return point if away.length() <= radius else center + away.normalized() * radius

func is_downed() -> bool:
	return downed_left > 0.0

func is_held() -> bool:
	return follower != null and RpgUtil.to_bool(follower.get_meta("held", false))

func _physics_process(delta: float) -> void:
	var router := RpgUtil.router()
	if follower == null or router == null or router.current_map == null:
		return
	var player: Node2D = router.current_map.get_player()
	if player == null:
		return
	var enemies: Array[Node2D] = []
	if not router.is_busy() and not RpgSequenceRunner.running():
		for node in follower.get_parent().get_children():
			if node is RpgEnemyAi:
				enemies.append(node as Node2D)
	step(delta, RpgUtil.world_position(player), enemies)

## One frame: recover, pick the enemy, walk beside it and swing, or walk back to the trail.
func step(delta: float, player_at: Vector2, enemies: Array[Node2D]) -> void:
	cooldown_left = maxf(0.0, cooldown_left - delta)
	if _active_left > 0.0:
		_active_left -= delta
		if _active_left <= 0.0:
			hitbox.active = false
	if is_downed():
		downed_left -= delta
		if downed_left <= 0.0:
			get_up()
		return
	target = nearest_enemy(player_at, enemies, ENGAGE_TILES * tile) if enabled else null
	if target == null:
		_walk_home(delta)
		return
	follower.set_meta("held", true)
	var me := _at()
	var enemy_at := RpgUtil.world_position(target)
	var side := me - enemy_at
	if side.length() < 0.01:
		side = player_at - enemy_at if player_at.distance_to(enemy_at) > 0.01 else Vector2.LEFT
	# Small sprites can share a map with larger native tiles. Stop within the actual
	# swing area instead of assuming that one tile is always within reach.
	var swing_shape := (hitbox.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D
	var swing_radius := minf(hitbox.reach.x + swing_shape.size.x * 0.5, hitbox.reach.y + swing_shape.size.y * 0.5)
	var stand_distance := minf(tile, maxf(1.0, swing_radius - 0.5))
	var stand := leashed(enemy_at + side.normalized() * stand_distance, player_at, LEASH_TILES * tile)
	var moved := _move_toward(stand, delta)
	var facing := RpgAnimationDriver.dir_to_facing(enemy_at - _at())
	follower.set_meta("facing", facing)
	if _at().distance_to(enemy_at) <= REACH_TILES * tile and cooldown_left <= 0.0:
		swing(facing)
	_driver.play("walk" if moved else "idle", facing, enemy_at - _at())

## Starts one swing toward `facing` with the member's attack.
func swing(facing: String) -> void:
	var state := RpgUtil.state()
	if stats != null:
		hitbox.damage = roundi(state.effective_stat(stats, &"attack")) if state != null else stats.attack
	hitbox.active = false
	hitbox.aim(facing)
	hitbox.active = true
	_active_left = SWING_ACTIVE_S
	cooldown_left = SWING_EVERY_S

## 0 HP: out of the fight for DOWNED_S. The member stays in the party.
func go_down() -> void:
	downed_left = DOWNED_S
	target = null
	hitbox.active = false
	_active_left = 0.0
	follower.set_meta("held", false)
	follower.modulate.a = DOWNED_ALPHA
	downed.emit()

func get_up() -> void:
	downed_left = 0.0
	health.revive()
	follower.modulate.a = 1.0
	recovered.emit()

func _at() -> Vector2:
	return RpgUtil.world_position(follower)

func _put(at: Vector2) -> void:
	if follower.is_inside_tree():
		follower.global_position = at
	else:
		follower.position = at

## Walks toward `point`; true while there is still a way to go.
func _move_toward(point: Vector2, delta: float) -> bool:
	var me := _at()
	var left := me.distance_to(point)
	if left <= 0.5:
		return false
	_put(me.move_toward(point, SPEED_TILES * tile * delta))
	return true

## Back to its place on the trail (meta "home", set by RpgFollowers), then RpgFollowers has it again.
func _walk_home(delta: float) -> void:
	if not is_held():
		return
	if not follower.has_meta("home"):
		follower.set_meta("held", false)
		return
	var home: Vector2 = follower.get_meta("home")
	if not _move_toward(home, delta) or _at().distance_to(home) <= 2.0:
		follower.set_meta("held", false)
		return
	var facing := RpgAnimationDriver.dir_to_facing(home - _at())
	follower.set_meta("facing", facing)
	_driver.play("walk", facing, home - _at())
