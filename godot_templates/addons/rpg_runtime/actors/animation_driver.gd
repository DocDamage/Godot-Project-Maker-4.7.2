class_name RpgAnimationDriver
extends RefCounted
## Picks and plays "<base>_<facing>" animations on an AnimatedSprite2D, with fallbacks.
##
## A facing is one of four directions (down, up, left, right). A sprite can also have animations
## for the four diagonals (down_left, down_right, up_left, up_right): `play` uses them when it is
## given the direction of travel, and a sprite that has only some directions shows the nearest.

## tan(22.5 degrees): a direction closer than this to an axis counts as that axis.
const DIAGONAL_SLOPE := 0.41421356
## The directions 45 degrees to either side of a direction, in the order they are tried.
const NEIGHBOURS: Dictionary = {
	"down": ["down_left", "down_right"],
	"up": ["up_left", "up_right"],
	"left": ["down_left", "up_left"],
	"right": ["down_right", "up_right"],
	"down_left": ["down", "left"],
	"down_right": ["down", "right"],
	"up_left": ["up", "left"],
	"up_right": ["up", "right"],
}

var sprite: AnimatedSprite2D

static func dir_to_facing(d: Vector2) -> String:
	# Vertical wins exact diagonal ties (classic RPG feel).
	if absf(d.x) > absf(d.y):
		return "right" if d.x > 0.0 else "left"
	return "down" if d.y >= 0.0 else "up"

## One of eight directions: a diagonal when `d` is more than 22.5 degrees away from both axes.
static func dir_to_facing8(d: Vector2) -> String:
	var ax := absf(d.x)
	var ay := absf(d.y)
	if ay <= ax * DIAGONAL_SLOPE or ax <= ay * DIAGONAL_SLOPE:
		return dir_to_facing(d)
	return ("down" if d.y > 0.0 else "up") + ("_right" if d.x > 0.0 else "_left")

static func _mirror(facing: String) -> String:
	match facing:
		"left":
			return "right"
		"right":
			return "left"
		"down_left":
			return "down_right"
		"down_right":
			return "down_left"
		"up_left":
			return "up_right"
		"up_right":
			return "up_left"
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

## "<base>_<facing>" (direct or mirrored), else the direction next to it that exists: a sprite
## with only diagonal animations shows one of them for "down", and one with only four directions
## shows "down" or "right" for "down_right".
func _nearest(frames: SpriteFrames, base: String, facing: String) -> Dictionary:
	var found := _resolve(frames, base, facing)
	if not found.is_empty():
		return found
	var neighbours: Array = NEIGHBOURS.get(facing, [])
	for other: String in neighbours:
		found = _resolve(frames, base, other)
		if not found.is_empty():
			return found
	return {}

## The animation for `facing`, or for the diagonal `dir` points along when the sprite has it and
## it agrees with `facing` (moving down and right while facing down or right).
func _pick(frames: SpriteFrames, base: String, facing: String, dir: Vector2) -> Dictionary:
	if dir != Vector2.ZERO:
		var fine := dir_to_facing8(dir)
		if fine != facing and facing in fine.split("_"):
			var found := _resolve(frames, base, fine)
			if not found.is_empty():
				return found
	return _nearest(frames, base, facing)

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

# ---------------------------------------------------------------- side view (T14.03)

## Other names a side-view animation goes by: packs call the same thing "run" or "walk".
const SIDE_ALIASES: Dictionary = {"run": ["run", "walk"], "walk": ["walk", "run"]}
## The endings looked for, in order, for a character that faces right. A strip without a direction
## in its name is stored as "<base>_down" by the adapters, so that counts as "no direction".
const SIDE_SUFFIXES: Array[String] = ["_right", "_side", "", "_down"]

## The animation that shows `base` for a side-view facing (-1 left, 1 right) as {"anim", "flip"},
## or an empty dictionary. "<base>_left" is used for the left when the sprite has it; otherwise
## the right-facing animation is mirrored. A sprite with only "<base>_left" is mirrored for the right.
func resolve_side(frames: SpriteFrames, base: String, side: int) -> Dictionary:
	var names: Array = SIDE_ALIASES.get(base, [base])
	for anim_base: String in names:
		var left := anim_base + "_left"
		var has_left := frames.has_animation(left)
		if side < 0 and has_left:
			return {"anim": left, "flip": RpgUtil.to_bool(frames.get_meta("flip_h_" + left, false))}
		for suffix in SIDE_SUFFIXES:
			var anim := anim_base + suffix
			if frames.has_animation(anim):
				var stored := RpgUtil.to_bool(frames.get_meta("flip_h_" + anim, false))
				return {"anim": anim, "flip": stored != (side < 0)}
		if has_left:
			return {"anim": left, "flip": not RpgUtil.to_bool(frames.get_meta("flip_h_" + left, false))}
	return {}

## True when the sprite has an animation for `base` seen from the side.
func has_side(base: String) -> bool:
	if sprite == null or sprite.sprite_frames == null:
		return false
	return not resolve_side(sprite.sprite_frames, base, 1).is_empty()

## Plays `base` for a side-view facing (see resolve_side). `restart` begins it from its first
## frame; otherwise an animation that is already playing goes on. Returns the animation's name, or
## "" when the sprite has none for `base`.
func play_side(base: String, side: int, restart: bool = false) -> String:
	if sprite == null or sprite.sprite_frames == null:
		return ""
	var found := resolve_side(sprite.sprite_frames, base, side)
	if found.is_empty():
		return ""
	var anim: String = found["anim"]
	sprite.flip_h = found["flip"]
	if restart:
		sprite.play(anim)
		sprite.frame = 0
		sprite.frame_progress = 0.0
	elif sprite.animation != anim or not sprite.is_playing():
		sprite.play(anim)
	return anim

## Plays "<base>_<facing>". Falls back in order:
## 1. "<base>_<facing>"  2. mirrored counterpart with flip_h (left<->right)
## 3. the direction 45 degrees next to it  4. "<base>_down"
## 5. "walk_<facing>" frame 0 (paused) when base == "idle"
## With `dir` (the direction of travel) a diagonal animation such as "walk_down_left" is used
## when the sprite has one. Does nothing if sprite or sprite_frames is null.
func play(base: String, facing: String, dir: Vector2 = Vector2.ZERO) -> void:
	if sprite == null or sprite.sprite_frames == null:
		return
	var frames: SpriteFrames = sprite.sprite_frames
	var found := _pick(frames, base, facing, dir)
	var paused := false
	if found.is_empty():
		found = _nearest(frames, base, "down")
	if found.is_empty() and base == "idle":
		found = _pick(frames, "walk", facing, dir)
		if found.is_empty():
			found = _nearest(frames, "walk", "down")
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
