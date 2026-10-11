class_name RpgShmupAsteroid
extends RpgShmupEnemy
## A rock that drifts through the stage. It fires nothing, but it is in the way: bullets stop
## at it, and a rock that is shot breaks once into two smaller ones that fly apart.

## How it drifts by itself, in px a second (beside scrolling past with the background).
@export var drift: Vector2 = Vector2.ZERO
## A piece of a rock that broke: it does not break again.
@export var fragment: bool = false
const PIECES := 2
const PIECE_SCALE := 0.6
const PIECE_SPEED := 30.0

func _init() -> void:
	in_stage = true

func _read_wave(data: Dictionary, index: int) -> void:
	var raw := RpgUtil.to_array(data.get("drift", []))
	if raw.size() >= 2:
		drift = Vector2(RpgUtil.to_float(raw[0]), RpgUtil.to_float(raw[1]))
	elif drift == Vector2.ZERO:
		# every rock of a wave a little differently, and the same every time
		drift = across() * (10.0 if index % 2 == 0 else -10.0) + travel() * (6.0 + 4.0 * (index % 3))

func _drift() -> Vector2:
	return drift

## The two pieces a rock breaks into (none for a piece).
func pieces() -> Array[RpgShmupAsteroid]:
	var out: Array[RpgShmupAsteroid] = []
	if fragment:
		return out
	for i in PIECES:
		var piece := duplicate() as RpgShmupAsteroid
		if piece == null:
			continue
		piece.fragment = true
		piece.health = 1
		@warning_ignore("integer_division")
		piece.points = maxi(10, points / 2)
		piece.hit_radius = hit_radius * PIECE_SCALE
		piece.scale = scale * PIECE_SCALE
		piece.drop = ""
		piece.drift = drift + across() * (PIECE_SPEED if i == 0 else -PIECE_SPEED)
		piece.auto_advance = auto_advance
		piece.pool_override = pool_override
		piece.area_center = area_center
		out.append(piece)
	return out

func _on_death() -> void:
	var made := pieces()
	var home := stage()
	for i in made.size():
		var at := position + across() * (hit_radius * 0.5 if i == 0 else -hit_radius * 0.5)
		if home != null:
			home.adopt.call_deferred(made[i], at)
		elif get_parent() != null:
			made[i].position = at
			get_parent().add_child.call_deferred(made[i])
		else:
			made[i].free()
