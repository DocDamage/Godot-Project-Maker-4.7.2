class_name RpgGunAim
extends RefCounted
## Where a soldier aims: one of eight ways, from what the stick or the arrows say and the way
## the soldier faces. Up and the four diagonals are always there; straight down only in the air
## (on the ground, down is a crouch, and a crouched soldier aims forward).

const NAMES := {
	Vector2i(0, -1): "up",
	Vector2i(1, -1): "up_forward",
	Vector2i(1, 0): "forward",
	Vector2i(1, 1): "down_forward",
	Vector2i(0, 1): "down",
}
const DEAD_ZONE := 0.35

## The aim as a unit vector. `stick` is what is held (each part -1..1), `facing` -1 (left) or 1,
## `on_floor` whether the soldier stands, `crouching` whether it is down.
static func direction(stick: Vector2, facing: int, on_floor: bool, crouching: bool = false) -> Vector2:
	var side := 1.0 if facing >= 0 else -1.0
	if crouching:
		return Vector2(side, 0.0)
	var x := 0.0
	if absf(stick.x) > DEAD_ZONE:
		x = 1.0 if stick.x > 0.0 else -1.0
	var y := 0.0
	if absf(stick.y) > DEAD_ZONE:
		y = 1.0 if stick.y > 0.0 else -1.0
	if y > 0.0 and x == 0.0 and on_floor:
		y = 0.0  # down on the ground is a crouch, not an aim
	if x == 0.0 and y == 0.0:
		return Vector2(side, 0.0)
	return Vector2(x, y).normalized()

## The name of an aim, seen from the soldier: "up", "up_forward", "forward", "down_forward" or
## "down".
static func name_of(aim: Vector2) -> String:
	var key := Vector2i(absi(roundi(signf(snappedf(aim.x, 0.1)))), roundi(signf(snappedf(aim.y, 0.1))))
	var found: String = NAMES.get(key, "forward")
	return found

## The eight aims there are, as unit vectors (to both sides: a held direction turns the soldier).
static func all() -> Array[Vector2]:
	var out: Array[Vector2] = []
	for x: int in [-1, 0, 1]:
		for y: int in [-1, 0, 1]:
			if x != 0 or y != 0:
				out.append(Vector2(x, y).normalized())
	return out
