class_name RpgEnemyAttack
extends Node
## Enemy component: one attack = windup (stands still and pulses a tint, the telegraph) -> the
## hitbox is live for `active_s` -> cooldown. The state machine in enemy_ai.gd drives update().

enum Phase { NONE, WINDUP, ACTIVE }

const TELEGRAPH_TINT := Color(1.0, 0.45, 0.45)

var windup_s := 0.35
var active_s := 0.15
var cooldown_s := 1.2

var actor: RpgActor
var hitbox: RpgHitbox
var phase := Phase.NONE
var cooldown_left := 0.0

var _t := 0.0
var _driver := RpgAnimationDriver.new()
var _visual: CanvasItem
var _base_tint := Color.WHITE  # the sprite's own tint (the fallback enemy is tinted red)

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor
	if actor != null:
		hitbox = actor.get_node_or_null("AttackHitbox") as RpgHitbox
		_visual = actor.get_node_or_null("Visual") as CanvasItem
		_driver.sprite = _visual as AnimatedSprite2D
		if _visual != null:
			_base_tint = _visual.modulate

func _physics_process(delta: float) -> void:
	if cooldown_left > 0.0:
		cooldown_left = maxf(0.0, cooldown_left - delta)

func is_attacking() -> bool:
	return phase != Phase.NONE

func can_start() -> bool:
	return phase == Phase.NONE and cooldown_left <= 0.0

## Starts the windup toward the actor's facing direction. False when it cannot start.
func try_start() -> bool:
	if not can_start() or actor == null:
		return false
	phase = Phase.WINDUP
	_t = 0.0
	if hitbox != null:
		hitbox.aim(actor.facing)
	actor.move_dir(Vector2.ZERO)
	if _driver.sprite != null and _driver.has_animation("attack", actor.facing):
		_driver.play_exact("attack", actor.facing)
		actor.animation_locked = true
	return true

## Advances the attack. True when it is over (the cooldown has started).
func update(delta: float) -> bool:
	if phase == Phase.NONE:
		return true
	_t += delta
	if phase == Phase.WINDUP:
		_pulse()
		if _t >= windup_s:
			phase = Phase.ACTIVE
			_t = 0.0
			_set_tint(_base_tint)
			if hitbox != null:
				hitbox.active = true
		return false
	if _t >= active_s:
		_finish()
		return true
	return false

## Stops a running attack without starting the cooldown count again from scratch.
func cancel() -> void:
	if phase == Phase.NONE:
		return
	_finish()

func _finish() -> void:
	phase = Phase.NONE
	cooldown_left = cooldown_s
	if hitbox != null:
		hitbox.active = false
	_set_tint(_base_tint)
	if actor != null:
		actor.animation_locked = false

func _pulse() -> void:
	var k := 0.5 + 0.5 * sin(_t * TAU * 6.0)
	_set_tint(_base_tint.lerp(TELEGRAPH_TINT, k))

func _set_tint(c: Color) -> void:
	if _visual != null:
		_visual.modulate = c
