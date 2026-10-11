class_name RpgGun
extends Node
## A soldier's gun: a rate, how many bullets a shot has and how far they spread, their speed,
## their range and their damage. It fires into the stage's bullet pool along the soldier's aim.
## The four weapons of the kind (weapons/) are guns with other numbers: the machine gun, the
## spread, the laser and the flame.

signal fired(direction: Vector2, bullets: int)

## The name of the weapon ("machine_gun", "spread", "laser", "flame").
@export var weapon: String = "machine_gun"
## Shots a second.
@export var rate: float = 6.0
@export var bullets_per_shot: int = 1
## The angle the bullets of one shot are spread over, in degrees.
@export var spread_deg: float = 0.0
## Tiles a second.
@export var speed_tiles: float = 15.0
## How far a bullet flies, in tiles; 0 flies until it leaves the screen.
@export var range_tiles: float = 0.0
@export var damage: int = 1
@export var bullet_kind: String = "bullet"
@export var pierce: bool = false
## The size of a tile in px (set by the soldier).
@export var tile: float = 16.0

var _cooldown := 0.0

## Px a second.
func bullet_speed() -> float:
	return speed_tiles * tile

## How far a bullet flies, in px (0: until it leaves the screen).
func range_px() -> float:
	return range_tiles * tile

## The velocities of the bullets of one shot along `direction` (a unit vector).
func volley(direction: Vector2) -> PackedVector2Array:
	var out := PackedVector2Array()
	var count := maxi(1, bullets_per_shot)
	var half := deg_to_rad(spread_deg) * 0.5
	for i in count:
		var lean := 0.0 if count == 1 else lerpf(-half, half, i / float(count - 1))
		out.append(direction.rotated(lean) * bullet_speed())
	return out

## One step. While `firing`, a shot leaves `muzzle` along `direction` every 1/rate seconds, into
## `pool`. Returns the bullets fired in this step.
func advance(delta: float, firing: bool, pool: RpgArcadeBulletPool, muzzle: Vector2, direction: Vector2) -> int:
	_cooldown = maxf(0.0, _cooldown - delta)
	if not firing or pool == null or _cooldown > 0.0:
		return 0
	_cooldown += 1.0 / maxf(0.1, rate)
	return shoot(pool, muzzle, direction)

## One shot now, whatever the rate.
func shoot(pool: RpgArcadeBulletPool, muzzle: Vector2, direction: Vector2) -> int:
	var sent := 0
	var life := range_px() / maxf(1.0, bullet_speed()) if range_tiles > 0.0 else 0.0
	for velocity in volley(direction):
		if pool.fire(RpgArcadeBulletPool.Team.PLAYER, muzzle, velocity, damage, 2.0, bullet_kind, false, pierce, life) >= 0:
			sent += 1
	if sent > 0:
		fired.emit(direction, sent)
	return sent
