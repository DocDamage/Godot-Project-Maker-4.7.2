class_name RpgWander
extends Node
## Enemy component: strolls around its home point. Uses its own seeded generator (from the entity
## id), never GameState.rng, so wandering does not disturb the seeded combat rolls.

const MAX_WALK_S := 3.0

var radius_px := 32.0
var pause_range := Vector2(1.0, 2.5)
var speed := 45.0
var home := Vector2.ZERO
var target := Vector2.ZERO
var rng := RpgRng.new()

var actor: RpgActor
var _walk_time := 0.0

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor

func seed_from(text: String) -> void:
	rng.seed_value(hash(text))

func pause_seconds() -> float:
	return rng.randf_range(pause_range.x, maxf(pause_range.x, pause_range.y))

func pick_target() -> void:
	target = home + Vector2(rng.randf_range(-radius_px, radius_px), rng.randf_range(-radius_px, radius_px))
	_walk_time = 0.0

func head_home() -> void:
	target = home
	_walk_time = 0.0

## Walks toward the target. True once it arrived (or the way is blocked for too long).
func step(delta: float) -> bool:
	if actor == null:
		return true
	var movement := actor.component("Movement") as RpgMovement
	if movement != null:
		movement.speed = speed
	_walk_time += delta
	var to_target := target - RpgDetection.position_of(actor)
	if to_target.length() < 1.5 or _walk_time > MAX_WALK_S:
		actor.move_dir(Vector2.ZERO)
		return true
	actor.move_dir(to_target.normalized())
	return false
