class_name RpgSniperEnemy
extends RpgGunEnemy
## Stands, aims and fires one shot at the soldier every `interval` seconds. Before the shot it
## shows that it is coming for `telegraph_s` (its picture flashes).

signal telegraphed

@export var interval: float = 2.5
@export var telegraph_s: float = 0.6
## It fires only at a soldier nearer than this, in tiles.
@export var range_tiles: float = 22.0
const WARNING := Color(1.0, 0.4, 0.4)

var aiming := false
var _since := 0.0

func think(delta: float) -> void:
	move_x = 0.0
	var side := side_of_soldier()
	if side != 0:
		set_facing(side)
	if tiles_to_soldier() > range_tiles:
		_since = 0.0
		_show(false)
		return
	_since += delta
	if not aiming and _since >= interval - telegraph_s:
		_show(true)
		telegraphed.emit()
	if _since >= interval:
		_since -= interval
		_show(false)
		fire_at_soldier()

func _show(on: bool) -> void:
	aiming = on
	if _driver.sprite != null:
		_driver.sprite.modulate = WARNING if on else Color.WHITE
