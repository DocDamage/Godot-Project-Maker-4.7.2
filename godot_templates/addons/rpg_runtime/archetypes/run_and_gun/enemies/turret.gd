class_name RpgGunTurret
extends RpgGunEnemy
## A fixed gun: it fires a fan of bullets at the soldier every `interval` seconds while the
## soldier is in range. A trap of them stops the camera until they are destroyed.

@export var interval: float = 2.0
@export var fan_count: int = 3
@export var fan_deg: float = 30.0
@export var range_tiles: float = 24.0

var _since := 0.0

func _read_wave(data: Dictionary, _index: int) -> void:
	fan_count = maxi(1, RpgUtil.to_int(data.get("fan", fan_count), fan_count))

func think(delta: float) -> void:
	move_x = 0.0
	var side := side_of_soldier()
	if side != 0:
		set_facing(side)
	if tiles_to_soldier() > range_tiles:
		return
	_since += delta
	if _since >= interval:
		_since -= interval
		fan_at_soldier(fan_count, fan_deg)
