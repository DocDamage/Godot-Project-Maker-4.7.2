class_name RpgShmupPopcorn
extends RpgShmupEnemy
## The small enemy that comes in numbers: it flies a path and is gone, and fires nothing or one
## shot at the ship. The enemies of a formation fly the same path from the same moment, so the
## formation moves as one: a line that sweeps, a V that dives, a circle that closes.
##
## Paths: `straight`, `sine` (weaving), `swoop` (in, then away to the side it came from),
## `sweep` (slowly, from side to side), `dive` (fast) and `close` (the formation draws together).

const PATHS: Array[String] = ["straight", "sine", "swoop", "sweep", "dive", "close"]
## The path a formation flies when its wave names none.
const FORMATION_PATHS := {"line": "sweep", "v": "dive", "circle": "close", "column": "swoop", "sine": "sine"}
const SHOT_AT_S := 1.0

@export var path: String = "straight"
## Fires one shot at the ship, a second after it appeared.
@export var shoots: bool = false
## How far a weaving or sweeping path goes to each side, in px.
@export var sway: float = 24.0

var _middle := Vector2.ZERO
var _side := 1.0
var _shot := false

func _read_wave(data: Dictionary, _index: int) -> void:
	var wanted := RpgUtil.to_str(data.get("path", FORMATION_PATHS.get(formation, "straight")))
	path = wanted if PATHS.has(wanted) else "straight"
	shoots = RpgUtil.to_bool(data.get("shoots", shoots))

func _start() -> void:
	_middle = _rel - formation_offset
	var lateral := _middle.dot(across())
	_side = -1.0 if lateral < 0.0 else 1.0

## Where the middle of the formation is `time_s` after it appeared, relative to where it began,
## and how far the formation is drawn together (1 is as it was laid out).
func path_at(time_s: float) -> Array:
	var along := speed * time_s
	var aside := 0.0
	var spread := 1.0
	match path:
		"sine":
			aside = sin(time_s * 3.0) * sway
		"sweep":
			along *= 0.6
			aside = sin(time_s * 1.5) * sway * 2.0
		"dive":
			along *= 1.8
		"swoop":
			var turn_at := view.dot(travel().abs()) * 0.45 / maxf(1.0, speed)
			var late := maxf(0.0, time_s - turn_at)
			aside = _side * late * late * speed * 1.5
			along -= late * late * speed * 0.3
		"close":
			spread = maxf(0.35, 1.0 - 0.25 * time_s)
	return [travel() * along + across() * aside, spread]

func _fly(_rel_now: Vector2, _delta: float) -> Vector2:
	var at := path_at(age)
	var moved: Vector2 = at[0]
	var spread: float = at[1]
	return _middle + moved + formation_offset * spread

func _act(_delta: float) -> void:
	if not shoots or _shot or age < SHOT_AT_S:
		return
	_shot = true
	var target := ship()
	if target != null:
		fire(RpgShmupEnemyBullet.aimed(position, target.position, bullet_speed))
