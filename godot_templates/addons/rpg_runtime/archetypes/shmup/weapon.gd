class_name RpgShmupWeapon
extends Node
## The ship's weapon: a kind (straight, spread, laser, homing), a level from 1 to 3 and a rate.
## A level means more bullets, a wider spread or a thicker laser. It fires into a bullet pool
## while the ship asks it to.

signal fired(bullets: int)

const KINDS: Array[String] = ["straight", "spread", "laser", "homing"]
const MAX_LEVEL := 3
## Px between two bullets that fly side by side.
const LANE := 6.0
## How far the outermost bullets of a spread lean, in degrees, by level.
const SPREAD_DEG: Array[float] = [12.0, 22.0, 32.0]

@export var kind: String = "straight"
@export var level: int = 1
## Shots a second.
@export var rate: float = 8.0
## Px a second.
@export var bullet_speed: float = 260.0
@export var damage: int = 1

var _cooldown := 0.0

## The bullets of one shot of `kind` at `level`: {side (px to the right of the muzzle, seen along
## the way the ship looks), lean (degrees to the right), width (a factor of the bullet's size)}.
static func shots(weapon_kind: String, weapon_level: int) -> Array[Dictionary]:
	var lvl := clampi(weapon_level, 1, MAX_LEVEL)
	var out: Array[Dictionary] = []
	match weapon_kind:
		"spread":
			var count := 1 + 2 * lvl  # 3, 5, 7
			var reach := SPREAD_DEG[lvl - 1]
			for i in count:
				out.append({"side": 0.0, "lean": lerpf(-reach, reach, i / float(count - 1)), "width": 1.0})
		"laser":
			out.append({"side": 0.0, "lean": 0.0, "width": float(lvl)})
		"homing":
			for i in lvl:
				out.append({"side": (i - (lvl - 1) * 0.5) * LANE * 2.0, "lean": 0.0, "width": 1.0})
		_:
			for i in lvl:
				out.append({"side": (i - (lvl - 1) * 0.5) * LANE, "lean": 0.0, "width": 1.0})
	return out

## How many bullets one shot has.
static func bullet_count(weapon_kind: String, weapon_level: int) -> int:
	return shots(weapon_kind, weapon_level).size()

## The picture a bullet of this kind uses in the pool.
static func bullet_kind(weapon_kind: String) -> String:
	match weapon_kind:
		"laser":
			return "laser"
		"homing":
			return "missile"
	return "bullet"

## One level up, to MAX_LEVEL and no further. True when it rose.
func level_up() -> bool:
	if level >= MAX_LEVEL:
		return false
	level += 1
	return true

## Another kind, at the level the weapon has.
func set_kind(weapon_kind: String) -> void:
	if KINDS.has(weapon_kind):
		kind = weapon_kind

## What a death costs: back to the first level.
func reset() -> void:
	level = 1
	_cooldown = 0.0

## One step. While `firing`, a shot leaves `muzzle` toward `forward` (a unit vector) every
## 1/rate seconds, into `pool`. Returns the bullets fired in this step.
func advance(delta: float, firing: bool, pool: RpgArcadeBulletPool, muzzle: Vector2, forward: Vector2) -> int:
	_cooldown = maxf(0.0, _cooldown - delta)
	if not firing or pool == null or _cooldown > 0.0:
		return 0
	_cooldown += 1.0 / maxf(0.1, rate)
	return shoot(pool, muzzle, forward)

## One shot now, whatever the rate.
func shoot(pool: RpgArcadeBulletPool, muzzle: Vector2, forward: Vector2) -> int:
	var right := Vector2(-forward.y, forward.x)
	var sent := 0
	for shot in shots(kind, level):
		var lean := deg_to_rad(RpgUtil.to_float(shot["lean"]))
		var width := RpgUtil.to_float(shot["width"], 1.0)
		var at := muzzle + right * RpgUtil.to_float(shot["side"])
		var hit := damage * (level if kind == "laser" else 1)
		if pool.fire(RpgArcadeBulletPool.Team.PLAYER, at, forward.rotated(lean) * bullet_speed, hit,
				2.0 * width, bullet_kind(kind), kind == "homing", kind == "laser") >= 0:
			sent += 1
	if sent > 0:
		fired.emit(sent)
	return sent
