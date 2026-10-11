class_name RpgShmupTurret
extends RpgShmupEnemy
## An enemy that sits on the background and scrolls past with it. While it is on the screen it
## fires a fan of bullets at the ship every `interval` seconds.

@export var interval: float = 2.0
@export var fan_count: int = 3
@export var fan_deg: float = 30.0

var _since := 0.0

func _init() -> void:
	in_stage = true

func _read_wave(data: Dictionary, _index: int) -> void:
	fan_count = maxi(1, RpgUtil.to_int(data.get("fan", fan_count), fan_count))
	# a wider fan for more bullets, so that the gaps between them stay passable
	fan_deg = maxf(fan_deg, 12.0 * (fan_count - 1))

func _act(delta: float) -> void:
	if not is_inside_screen():
		return
	_since += delta
	if _since < interval:
		return
	_since -= interval
	var target := ship()
	if target == null:
		return
	var toward := (target.position - position).normalized() if target.position != position else travel()
	fire(RpgShmupEnemyBullet.fan(toward, fan_count, fan_deg, bullet_speed))
