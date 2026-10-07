class_name RpgSwingEffect
extends AnimatedSprite2D
## The generic attack effect for characters without attack animations: a short arc drawn at the
## hitbox position and turned toward the facing direction. Frames come from
## generated/effects/swing_frames.tres (or from a pack effect the swing recipe picked).

const FRAMES_PATH := "res://generated/effects/swing_frames.tres"

func _ready() -> void:
	visible = false
	centered = true
	z_index = 1
	if sprite_frames == null and ResourceLoader.exists(FRAMES_PATH):
		sprite_frames = load(FRAMES_PATH) as SpriteFrames
	animation_finished.connect(_on_finished)

func has_frames() -> bool:
	return sprite_frames != null and not sprite_frames.get_animation_names().is_empty()

## Plays the effect once over `duration` seconds at `at` (owner-local), turned toward `dir`.
func play_at(at: Vector2, dir: Vector2, duration: float = 0.2) -> void:
	if not has_frames():
		return
	var anim := sprite_frames.get_animation_names()[0]
	position = at
	rotation = dir.angle()
	flip_v = dir.x < 0.0
	var seconds := RpgArpgMath.animation_seconds(sprite_frames, anim)
	speed_scale = seconds / duration if seconds > 0.0 and duration > 0.0 else 1.0
	sprite_frames.set_animation_loop(anim, false)
	visible = true
	play(anim)
	frame = 0

func stop_effect() -> void:
	stop()
	visible = false

func _on_finished() -> void:
	visible = false
