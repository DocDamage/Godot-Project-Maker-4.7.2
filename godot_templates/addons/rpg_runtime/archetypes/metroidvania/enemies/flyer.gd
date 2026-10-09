class_name RpgFlyerEnemy
extends RpgSideEnemy
## Flies: no gravity. It hovers around the place it was put (its anchor), comes for a player
## within `chase_tiles`, and goes back to its anchor when the player is gone.

@export var chase_tiles: float = 5.0
## How far it bobs up and down, in px, and how fast (cycles per second).
@export var hover_px: float = 4.0
@export var hover_hz: float = 0.5

var anchor := Vector2.ZERO
var chasing := false
var _time := 0.0
var _has_anchor := false

func _ready() -> void:
	super._ready()
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	set_anchor(global_position if is_inside_tree() else position)

func set_anchor(at: Vector2) -> void:
	anchor = at
	_has_anchor = true

## Where it wants to be now: at the player, or bobbing at its anchor.
func goal() -> Vector2:
	var player := find_player()
	chasing = player != null and tiles_to(player) <= chase_tiles
	if chasing:
		return middle_of(player) + Vector2(0.0, body_height() * 0.5)
	return anchor + Vector2(0.0, sin(_time * TAU * hover_hz) * hover_px)

func think(delta: float) -> void:
	_time += delta
	var at := global_position if is_inside_tree() else position
	var to := goal() - at
	var speed := px(run_speed)
	velocity = to.normalized() * minf(speed, to.length() / maxf(delta, 0.001)) if to.length() > 0.5 else Vector2.ZERO
	if absf(to.x) > 1.0:
		set_facing(1 if to.x > 0.0 else -1)

## A flyer moves by its own velocity: no floor, no gravity.
func move(_delta: float) -> void:
	if is_stunned():
		velocity = velocity.move_toward(Vector2.ZERO, px(run_speed) * 0.2)
	move_and_slide()
	_animate()

func _animate() -> void:
	if animation_locked or _driver.sprite == null:
		return
	_driver.sprite.speed_scale = 1.0
	_play_first(["fly", "idle", "run"])
