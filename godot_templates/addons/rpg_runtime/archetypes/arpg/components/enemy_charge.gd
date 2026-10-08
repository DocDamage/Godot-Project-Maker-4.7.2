class_name RpgEnemyCharge
extends Node
## Enemy component: one charge = windup (stands, pulses the telegraph tint) -> a dash in a straight
## line toward where the player was, with the attack hitbox live, for `dash_s` or until a wall stops
## it -> a recovery in which it stands still (the moment to hit it) -> cooldown. The state machine in
## enemy_ai.gd drives update(). Used by the "charger" kind.

enum Phase { NONE, WINDUP, DASH, RECOVER }

const TELEGRAPH_TINT := Color(1.0, 0.45, 0.45)
## A dash that has gone less than this share of its speed for a few frames hit a wall.
const BLOCKED_SHARE := 0.25

var windup_s := 0.5
var dash_s := 0.45
var speed := 180.0
var recover_s := 0.6
var cooldown_s := 1.5

var actor: RpgActor
var hitbox: RpgHitbox
var phase := Phase.NONE
var cooldown_left := 0.0
var direction := Vector2.RIGHT

var _t := 0.0
var _blocked_frames := 0
var _visual: CanvasItem
var _base_tint := Color.WHITE
var _saved_speed := -1.0

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor
	if actor != null:
		hitbox = actor.get_node_or_null("AttackHitbox") as RpgHitbox
		_visual = actor.get_node_or_null("Visual") as CanvasItem
		if _visual != null:
			_base_tint = _visual.modulate

func _physics_process(delta: float) -> void:
	if cooldown_left > 0.0 and not RpgSequenceRunner.running():
		cooldown_left = maxf(0.0, cooldown_left - delta)

func is_charging() -> bool:
	return phase != Phase.NONE

func can_start() -> bool:
	return phase == Phase.NONE and cooldown_left <= 0.0

## Starts the windup toward `at` (a global position). False when it cannot start.
func try_start(at: Vector2) -> bool:
	if not can_start() or actor == null:
		return false
	var d := at - RpgUtil.world_position(actor)
	direction = d.normalized() if d.length() > 0.01 else RpgArpgMath.facing_vector(actor.facing)
	phase = Phase.WINDUP
	_t = 0.0
	actor.move_dir(Vector2.ZERO)
	actor.set_facing(RpgAnimationDriver.dir_to_facing(direction))
	return true

## Advances the charge. True when it is over (the cooldown has started).
func update(delta: float) -> bool:
	if phase == Phase.NONE:
		return true
	_t += delta
	match phase:
		Phase.WINDUP:
			var k := 0.5 + 0.5 * sin(_t * TAU * 6.0)
			_set_tint(_base_tint.lerp(TELEGRAPH_TINT, k))
			if _t >= windup_s:
				_begin_dash()
		Phase.DASH:
			actor.move_dir(direction)
			if actor.is_inside_tree() and _t > 0.1 and actor.get_real_velocity().length() < speed * BLOCKED_SHARE:
				_blocked_frames += 1
			else:
				_blocked_frames = 0
			if _t >= dash_s or _blocked_frames >= 3:
				_begin_recover()
		Phase.RECOVER:
			actor.move_dir(Vector2.ZERO)
			if _t >= recover_s:
				_finish()
				return true
	return false

func _begin_dash() -> void:
	phase = Phase.DASH
	_t = 0.0
	_blocked_frames = 0
	_set_tint(_base_tint)
	var movement := actor.component("Movement") as RpgMovement
	if movement != null:
		_saved_speed = movement.speed
		movement.speed = speed
	actor.facing_locked = true
	actor.move_dir(direction)
	if hitbox != null:
		hitbox.aim(actor.facing)
		hitbox.active = true
	RpgUtil.emit(&"attack_started", [actor])

func _begin_recover() -> void:
	phase = Phase.RECOVER
	_t = 0.0
	_end_dash()

func _end_dash() -> void:
	actor.move_dir(Vector2.ZERO)
	actor.facing_locked = false
	var movement := actor.component("Movement") as RpgMovement
	if movement != null and _saved_speed >= 0.0:
		movement.speed = _saved_speed
	_saved_speed = -1.0
	if hitbox != null:
		hitbox.active = false

func cancel() -> void:
	if phase == Phase.NONE:
		return
	if phase == Phase.DASH:
		_end_dash()
	_finish()

func _finish() -> void:
	phase = Phase.NONE
	cooldown_left = cooldown_s
	_set_tint(_base_tint)

func _set_tint(c: Color) -> void:
	if _visual != null:
		_visual.modulate = c
