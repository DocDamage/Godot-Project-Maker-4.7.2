class_name RpgSideCamera
extends Camera2D
## The camera of a side-view room. The room owns it (the player scene has none): it follows the
## player a little ahead of where the player looks and never shows past the edges of the room.

## How far ahead of the player the camera looks, in tiles.
@export var look_ahead_tiles: float = 1.5
## How far above the feet the camera aims, in tiles.
@export var lift_tiles: float = 1.5
## How fast it closes in on its target (higher is snappier).
@export var follow_speed: float = 8.0
@export var tile_size: float = 16.0

var target: Node2D = null
var _slide: Tween = null
var _gliding := false  # slide_from is moving the camera itself: the follow waits

func _ready() -> void:
	enabled = true
	position_smoothing_enabled = false  # this script does the smoothing, in physics time
	process_callback = Camera2D.CAMERA2D_PROCESS_PHYSICS

## The rectangle of the room (global px): the camera does not show past it.
func set_limits(rect: Rect2) -> void:
	limit_left = floori(rect.position.x)
	limit_top = floori(rect.position.y)
	limit_right = ceili(rect.end.x)
	limit_bottom = ceili(rect.end.y)

func limits() -> Rect2:
	return Rect2(limit_left, limit_top, limit_right - limit_left, limit_bottom - limit_top)

## The player of the room this camera is in.
func find_target() -> Node2D:
	if is_instance_valid(target) and target.is_inside_tree():
		return target
	target = null
	if not is_inside_tree():
		return null
	var room := get_parent()
	for node in get_tree().get_nodes_in_group("player"):
		if node is Node2D and (room == null or room.is_ancestor_of(node)):
			target = node
			break
	return target

## Where the camera wants to be: ahead of the player and a little above the feet.
func wanted() -> Vector2:
	var who := find_target()
	if who == null:
		return global_position
	var facing: Variant = who.get("facing")
	var side := 0.0
	if facing is int or facing is float:
		side = signf(RpgUtil.to_float(facing))
	return who.global_position + Vector2(side * look_ahead_tiles * tile_size, -lift_tiles * tile_size)

## Jumps to the target at once (a loaded game, a new room without a slide).
func snap_to_target() -> void:
	if _slide != null and _slide.is_valid():
		_slide.kill()
	_gliding = false
	global_position = wanted()
	reset_smoothing()

## Glides from the point `from` to the target in `seconds` (a room change: no fade).
func slide_from(from: Vector2, seconds: float = 0.25) -> void:
	if _slide != null and _slide.is_valid():
		_slide.kill()
	global_position = from
	reset_smoothing()
	if not is_inside_tree() or seconds <= 0.0:
		snap_to_target()
		return
	_slide = create_tween()
	_slide.set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)
	_gliding = true
	_slide.tween_method(_slide_step.bind(from), 0.0, 1.0, seconds)
	_slide.tween_callback(set.bind(&"_gliding", false))

func _slide_step(amount: float, from: Vector2) -> void:
	global_position = from.lerp(wanted(), amount)

func sliding() -> bool:
	return _slide != null and _slide.is_valid() and _slide.is_running()

## The view glides in from `from` (a direction: the side the player came from) over `seconds`,
## after a room change. For that time the camera may show past the room's edge on that side:
## what was the last room slides out of view.
func slide_in(from: Vector2, seconds: float = 0.25, tiles: float = 6.0) -> void:
	if _slide != null and _slide.is_valid():
		_slide.kill()
	_gliding = false
	offset = Vector2.ZERO
	if not is_inside_tree() or seconds <= 0.0 or from == Vector2.ZERO:
		return
	var kept := limits()
	var push := from.normalized() * tiles * tile_size
	set_limits(kept.merge(Rect2(kept.position + push, kept.size)))
	offset = push
	_slide = create_tween()
	_slide.set_process_mode(Tween.TWEEN_PROCESS_PHYSICS)
	_slide.tween_property(self, "offset", Vector2.ZERO, seconds).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	_slide.tween_callback(set_limits.bind(kept))

func _physics_process(delta: float) -> void:
	if find_target() == null or (_gliding and sliding()):
		return
	global_position = global_position.lerp(wanted(), clampf(follow_speed * delta, 0.0, 1.0))
