class_name RpgScreenFeedback
extends RefCounted
## What a landed heavy attack looks like: a two-frame hit-stop and a short camera shake. Both are
## purely visual (nothing in the game state depends on them) and both follow the "Screen shake"
## setting of the Settings menu.

const HIT_STOP_FRAMES := 2
const SHAKE_STRENGTH := 3.0
const SHAKE_SECONDS := 0.12
const SHAKE_STEPS := 5

static var _stopped := false

static func enabled() -> bool:
	var settings := RpgUtil.settings()
	return settings == null or bool(settings.get("screen_shake"))

## Freezes the game for `frames` physics frames (60 per second), unless one hit-stop is running.
static func hit_stop(frames: int = HIT_STOP_FRAMES) -> void:
	var tree := RpgUtil.tree()
	if not enabled() or tree == null or _stopped or frames <= 0:
		return
	_stopped = true
	var previous := Engine.time_scale
	Engine.time_scale = 0.0
	# a timer that ignores the time scale, so that it can end the stop
	await tree.create_timer(float(frames) / 60.0, true, false, true).timeout
	Engine.time_scale = previous
	_stopped = false

## Shakes `camera` (its offset) a few times and settles it back.
static func shake(camera: Camera2D, strength: float = SHAKE_STRENGTH, seconds: float = SHAKE_SECONDS) -> void:
	if not enabled() or camera == null or not camera.is_inside_tree():
		return
	var rng := RandomNumberGenerator.new()  # visual only: never the game's seeded RNG
	rng.randomize()
	var tween := camera.create_tween()
	for i in SHAKE_STEPS:
		var falloff := 1.0 - float(i) / SHAKE_STEPS
		tween.tween_property(camera, "offset", Vector2(rng.randf_range(-1.0, 1.0), rng.randf_range(-1.0, 1.0)) * strength * falloff, seconds / SHAKE_STEPS)
	tween.tween_property(camera, "offset", Vector2.ZERO, 0.02)

## The heavy attack landed: stop, then shake.
static func heavy_hit(camera: Camera2D) -> void:
	shake(camera)
	hit_stop()
