class_name RpgArpgMath
extends RefCounted
## Pure formulas and constants of the real-time combat.

const CRIT_MULTIPLIER := 1.5
const DEFAULT_CRIT_CHANCE := 0.05
const PLAYER_INVULN_S := 0.6
const ENEMY_INVULN_S := 0.15
## The heavy attack (secondary_attack): slower, stronger, knocks back further.
const HEAVY_DAMAGE_MULT := 1.75
const HEAVY_KNOCKBACK_MULT := 1.5
const HEAVY_DURATION_MULT := 1.6
const HEAVY_ANIM_SPEED := 0.7

## Damage of a heavy attack whose light version would deal `base` (always more than `base`).
static func heavy_damage(base: int) -> int:
	return maxi(base + 1, int(round(float(base) * HEAVY_DAMAGE_MULT)))

## max(1, attack - defense / 2)
static func base_damage(attack: int, defense: int) -> int:
	return maxi(1, attack - floori(defense / 2.0))

## {amount, crit}. Always draws exactly one number from `rng` (an RpgRng or RandomNumberGenerator),
## so the sequence of a seeded game does not depend on the outcome.
static func roll_damage(attack: int, defense: int, crit_chance: float, rng: Variant) -> Dictionary:
	var amount := base_damage(attack, defense)
	var crit: bool = rng != null and rng.randf() < crit_chance
	if crit:
		amount = int(round(float(amount) * CRIT_MULTIPLIER))
	return {"amount": amount, "crit": crit}

## Unit vector of a facing name ("up", "down", "left", "right").
static func facing_vector(facing: String) -> Vector2:
	match facing:
		"up":
			return Vector2.UP
		"left":
			return Vector2.LEFT
		"right":
			return Vector2.RIGHT
	return Vector2.DOWN

## The middle third of an attack animation with `frame_count` frames (used when the animation has no
## active_frames): 4 frames -> [1, 2], 3 -> [1], 1 -> [0].
static func default_active_frames(frame_count: int) -> Array[int]:
	var out: Array[int] = []
	if frame_count <= 0:
		return out
	var first := floori(frame_count / 3.0)
	var last := maxi(first, ceili(frame_count * 2.0 / 3.0) - 1)
	for i in range(first, last + 1):
		out.append(i)
	return out

## Seconds an animation takes to play once.
static func animation_seconds(frames: SpriteFrames, anim: String) -> float:
	if frames == null or not frames.has_animation(anim):
		return 0.0
	var total := 0.0
	for i in frames.get_frame_count(anim):
		total += frames.get_frame_duration(anim, i)
	var speed := frames.get_animation_speed(anim)
	return total / speed if speed > 0.0 else 0.0

## The frame indices of `anim` in which an attack hitbox is live: the animation's active_frames
## (stored as the SpriteFrames meta "active_frames_<anim>"), else the middle third.
static func active_frames_of(frames: SpriteFrames, anim: String) -> Array[int]:
	if frames == null or not frames.has_animation(anim):
		return []
	var stored: Variant = frames.get_meta("active_frames_" + anim) if frames.has_meta("active_frames_" + anim) else null
	var out: Array[int] = []
	if stored is Array or stored is PackedInt32Array or stored is PackedInt64Array:
		for v in stored:
			out.append(int(v))
	if out.is_empty():
		out = default_active_frames(frames.get_frame_count(anim))
	return out
