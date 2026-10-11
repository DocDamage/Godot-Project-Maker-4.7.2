class_name RpgShmupEnemyBullet
extends RefCounted
## The patterns enemies and bosses shoot in: each is a small function that says how the bullets
## of one volley fly (their velocities, in px a second), and `fire` puts a volley into the pool.

## One bullet at the target.
static func aimed(from: Vector2, target: Vector2, speed: float) -> PackedVector2Array:
	var way := (target - from).normalized() if target != from else Vector2.DOWN
	return PackedVector2Array([way * speed])

## `count` bullets all around, the first at `phase` radians.
static func ring(count: int, speed: float, phase: float = 0.0) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := maxi(1, count)
	for i in n:
		out.append(Vector2.from_angle(phase + TAU * i / n) * speed)
	return out

## `count` bullets spread evenly over `spread_deg` degrees around `toward` (a unit vector).
static func fan(toward: Vector2, count: int, spread_deg: float, speed: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := maxi(1, count)
	var half := deg_to_rad(spread_deg) * 0.5
	for i in n:
		var lean := 0.0 if n == 1 else lerpf(-half, half, i / float(n - 1))
		out.append(toward.rotated(lean) * speed)
	return out

## The volley number `step` of a spiral with `arms` arms that turns `turn_deg` degrees a volley.
static func spiral(step: int, arms: int, speed: float, turn_deg: float = 12.0) -> PackedVector2Array:
	return ring(arms, speed, deg_to_rad(turn_deg) * step)

## Puts a volley into `pool` at `from`. Returns how many bullets the pool had room for.
static func fire(pool: RpgArcadeBulletPool, from: Vector2, velocities: PackedVector2Array,
		damage: int = 1, radius: float = 2.0) -> int:
	var sent := 0
	if pool == null:
		return sent
	for velocity in velocities:
		if pool.fire(RpgArcadeBulletPool.Team.ENEMY, from, velocity, damage, radius, "enemy") >= 0:
			sent += 1
	return sent
