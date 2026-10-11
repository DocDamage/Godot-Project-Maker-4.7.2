class_name RpgRunnerEnemy
extends RpgGunEnemy
## Charges at the soldier, and jumps at it when it is near or when something is in the way.

## It jumps when the soldier is nearer than this, in tiles.
@export var leap_tiles: float = 3.0
@export var leap_every: float = 1.2

var _since_leap := 1.2

func think(delta: float) -> void:
	_since_leap += delta
	var side := side_of_soldier()
	if side == 0:
		move_x = float(facing)  # nobody to chase: it runs on
		return
	move_x = float(side)
	var blocked := is_on_wall() and is_on_floor()
	if is_on_floor() and _since_leap >= leap_every and (blocked or tiles_to_soldier() <= leap_tiles):
		_since_leap = 0.0
		press_jump()
		jump_held = true
	elif is_on_floor():
		jump_held = false
