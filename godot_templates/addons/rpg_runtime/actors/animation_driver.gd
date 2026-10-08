class_name RpgAnimationDriver
extends RefCounted
## Picks and plays "<base>_<facing>" animations on an AnimatedSprite2D, with fallbacks.

var sprite: AnimatedSprite2D

static func dir_to_facing(d: Vector2) -> String:
	# Vertical wins exact diagonal ties (classic RPG feel).
	if absf(d.x) > absf(d.y):
		return "right" if d.x > 0.0 else "left"
	return "down" if d.y >= 0.0 else "up"

static func _mirror(facing: String) -> String:
	match facing:
		"left":
			return "right"
		"right":
			return "left"
		_:
			return ""

## Resolves "<base>_<facing>" directly, or via the mirrored counterpart with flip_h.
## Returns {"anim": String, "flip": bool} or an empty dictionary when neither exists.
func _resolve(frames: SpriteFrames, base: String, facing: String) -> Dictionary:
	var direct := "%s_%s" % [base, facing]
	if frames.has_animation(direct):
		return {"anim": direct, "flip": RpgUtil.to_bool(frames.get_meta("flip_h_" + direct, false))}
	var other := _mirror(facing)
	if other != "":
		var mirrored := "%s_%s" % [base, other]
		if frames.has_animation(mirrored):
			return {"anim": mirrored, "flip": not RpgUtil.to_bool(frames.get_meta("flip_h_" + mirrored, false))}
	return {}

## True when "<base>_<facing>" (or its mirrored counterpart) exists, with no fallback to other
## directions.
func has_animation(base: String, facing: String) -> bool:
	if sprite == null or sprite.sprite_frames == null:
		return false
	return not _resolve(sprite.sprite_frames, base, facing).is_empty()

## Plays "<base>_<facing>" exactly (direct or mirrored) from its first frame. Returns the animation
## name, or "" when it does not exist.
func play_exact(base: String, facing: String) -> String:
	if not has_animation(base, facing):
		return ""
	var found := _resolve(sprite.sprite_frames, base, facing)
	sprite.flip_h = found["flip"]
	var anim: StringName = found["anim"]
	sprite.play(anim)
	sprite.frame = 0
	sprite.frame_progress = 0.0
	return found["anim"]

## Plays "<base>_<facing>". Falls back in order:
## 1. "<base>_<facing>"  2. mirrored counterpart with flip_h (left<->right)
## 3. "<base>_down"  4. "walk_<facing>" frame 0 (paused) when base == "idle"
## Does nothing if sprite or sprite_frames is null.
func play(base: String, facing: String) -> void:
	if sprite == null or sprite.sprite_frames == null:
		return
	var frames: SpriteFrames = sprite.sprite_frames
	var found := _resolve(frames, base, facing)
	var paused := false
	if found.is_empty():
		found = _resolve(frames, base, "down")
	if found.is_empty() and base == "idle":
		found = _resolve(frames, "walk", facing)
		if found.is_empty():
			found = _resolve(frames, "walk", "down")
		paused = not found.is_empty()
	if found.is_empty():
		return
	var anim: String = found["anim"]
	sprite.flip_h = found["flip"]
	if paused:
		sprite.animation = anim
		sprite.frame = 0
		sprite.stop()
		return
	# Do not restart an animation that is already playing.
	if sprite.animation != anim or not sprite.is_playing():
		sprite.play(anim)
