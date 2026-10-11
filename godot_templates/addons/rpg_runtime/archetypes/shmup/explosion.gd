class_name RpgShmupExplosion
extends AnimatedSprite2D
## An explosion: plays its animation once and is gone. Without frames it is gone at once.

@export var sound: StringName = &"sfx_explosion"

func _ready() -> void:
	var router := RpgUtil.router()
	if router != null and router.audio != null:
		router.audio.call(&"play", sound)
	if sprite_frames == null or sprite_frames.get_animation_names().is_empty():
		queue_free()
		return
	var first := StringName(sprite_frames.get_animation_names()[0])
	sprite_frames.set_animation_loop(first, false)
	animation_finished.connect(queue_free)
	play(first)
