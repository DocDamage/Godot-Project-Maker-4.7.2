class_name RpgJumperEnemy
extends RpgGunEnemy
## Hops toward the soldier: a jump every `hop_every` seconds, moving only while it is in the air.

@export var hop_every: float = 1.0

var hops := 0
var _since := 0.5

func think(delta: float) -> void:
	_since += delta
	var side := side_of_soldier()
	if is_on_floor():
		move_x = 0.0
		if side != 0:
			set_facing(side)
		if _since >= hop_every:
			_since = 0.0
			hops += 1
			press_jump()
			jump_held = true
			move_x = float(side if side != 0 else facing)
	else:
		move_x = float(side if side != 0 else facing)
