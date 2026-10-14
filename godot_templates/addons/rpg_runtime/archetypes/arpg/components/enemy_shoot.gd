class_name RpgEnemyShoot
extends Node
## Enemy component: one shot = windup (stands still and pulses the telegraph tint) -> a projectile
## toward where the player was when the windup started -> cooldown. The state machine in enemy_ai.gd
## drives update(). Used by the "shooter" and "turret" kinds.

const TELEGRAPH_TINT := Color(1.0, 0.8, 0.35)

var windup_s := 0.45
var cooldown_s := 1.6
var speed := 120.0
var range_px := 160.0
var style := "orb"

var actor: RpgActor
var aiming := false
var cooldown_left := 0.0
var target := Vector2.ZERO
## The last projectile fired (tests look at it).
var last_shot: RpgProjectile = null

var _t := 0.0
var _visual: CanvasItem
var _base_tint := Color.WHITE

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor
	if actor != null:
		_visual = actor.get_node_or_null("Visual") as CanvasItem
		if _visual != null:
			_base_tint = _visual.modulate

func _physics_process(delta: float) -> void:
	if cooldown_left > 0.0 and not RpgSequenceRunner.running():
		cooldown_left = maxf(0.0, cooldown_left - delta)

func can_start() -> bool:
	return not aiming and cooldown_left <= 0.0

## Starts the windup, aimed at `at` (a global position). False when it cannot start.
func try_start(at: Vector2) -> bool:
	if not can_start() or actor == null:
		return false
	aiming = true
	target = at
	_t = 0.0
	actor.move_dir(Vector2.ZERO)
	actor.set_facing(RpgAnimationDriver.dir_to_facing(at - RpgUtil.world_position(actor)))
	return true

## Advances the shot. True when it is over (fired, the cooldown has started).
func update(delta: float) -> bool:
	if not aiming:
		return true
	_t += delta
	var k := 0.5 + 0.5 * sin(_t * TAU * 5.0)
	_set_tint(_base_tint.lerp(TELEGRAPH_TINT, k))
	if _t < windup_s:
		return false
	fire()
	_finish()
	return true

## The projectile, from the feet toward `target` (the player's feet): it flies on the ground along
## the line between the two pairs of feet, so it meets the target's footprint whether the shooter is
## shorter or taller than the target, and is drawn at the middle of the shooter's body, where it
## was fired. Added beside the actor.
func fire() -> RpgProjectile:
	if actor == null:
		return null
	var hurtbox := actor.get_node_or_null("Hurtbox") as Node2D
	var from := RpgUtil.world_position(actor)
	var body := RpgUtil.world_position(hurtbox) if hurtbox != null else from
	var direction := target - from
	if direction.length() < 0.01:
		direction = RpgArpgMath.facing_vector(actor.facing)
	var shot := RpgProjectile.create(actor, from, direction, &"enemy", speed, range_px, style)
	shot.set_on_ground(body - from)
	var holder := actor.get_parent()
	if holder != null:
		holder.add_child(shot)
		shot.global_position = from if shot.is_inside_tree() else shot.position
	last_shot = shot
	RpgUtil.emit(&"attack_started", [actor])
	return shot

func cancel() -> void:
	if aiming:
		_finish()

func _finish() -> void:
	aiming = false
	cooldown_left = cooldown_s
	_set_tint(_base_tint)

func _set_tint(c: Color) -> void:
	if _visual != null:
		_visual.modulate = c
