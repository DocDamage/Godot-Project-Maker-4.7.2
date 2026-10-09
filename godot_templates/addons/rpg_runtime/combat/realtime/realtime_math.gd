class_name RpgRealtimeMath
extends RefCounted
## Pure formulas and constants of the real-time combat (the action RPG and the metroidvania).

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
	return maxi(base + 1, RpgUtil.to_int(round(float(base) * HEAVY_DAMAGE_MULT)))

## max(1, attack - defense / 2)
static func base_damage(attack: int, defense: int) -> int:
	return maxi(1, attack - floori(defense / 2.0))

## {amount, crit}. Always draws exactly one number from `rng` (an RpgRng),
## so the sequence of a seeded game does not depend on the outcome.
static func roll_damage(attack: int, defense: int, crit_chance: float, rng: RpgRng) -> Dictionary:
	var amount := base_damage(attack, defense)
	var crit: bool = rng != null and rng.randf() < crit_chance
	if crit:
		amount = RpgUtil.to_int(round(float(amount) * CRIT_MULTIPLIER))
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

## Where `actor` looks, as a unit vector: a top-down actor's facing name, or a side-view actor's
## facing number (-1 left, 1 right).
static func facing_of(actor: Node) -> Vector2:
	var facing: Variant = actor.get("facing") if actor != null else null
	if facing is int or facing is float:
		return Vector2.LEFT if RpgUtil.to_float(facing) < 0.0 else Vector2.RIGHT
	return facing_vector(str(facing))

## The actor `node` belongs to: itself or the nearest ancestor that has components.
static func actor_of(node: Node) -> Node2D:
	var at := node.get_parent() if node != null else null
	while at != null:
		if at is Node2D and at.has_method(&"component"):
			return at as Node2D
		at = at.get_parent()
	return null

## The RpgStats of an actor's Stats component, or null.
static func stats_of(actor: Node) -> RpgStats:
	if actor == null or not actor.has_method(&"component"):
		return null
	var found: Variant = actor.call(&"component", "Stats")
	if found is RpgStatsComponent:
		var comp: RpgStatsComponent = found
		return comp.stats
	return null

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
		for v: Variant in stored:
			out.append(RpgUtil.to_int(v))
	if out.is_empty():
		out = default_active_frames(frames.get_frame_count(anim))
	return out
