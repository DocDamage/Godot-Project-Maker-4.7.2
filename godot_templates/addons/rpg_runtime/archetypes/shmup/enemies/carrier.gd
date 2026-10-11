class_name RpgShmupCarrier
extends RpgShmupEnemy
## The big, slow, tough enemy: it comes a third of the way into the screen, stays there weaving
## from side to side, and releases a small enemy every few seconds. When it has stayed long
## enough it flies on. It always leaves a power-up when it is shot.

## The small enemy it releases (a popcorn scene).
@export var escort_scene: PackedScene = null
@export var release_every: float = 2.5
@export var max_escorts: int = 4
## Seconds it stays before it flies on.
@export var stay_s: float = 18.0
@export var sway: float = 40.0

var released := 0
var _since := 0.0
var _hold_at := 0.0
var _held_s := 0.0
var _home := Vector2.ZERO

func _start() -> void:
	_home = _rel
	# a third of the way into the screen, measured from the edge it comes from
	var half := view.dot(travel().abs()) * 0.5
	_hold_at = half - view.dot(travel().abs()) / 3.0

func is_holding() -> bool:
	return _placed and _held_s > 0.0 and _held_s < stay_s

func _fly(rel: Vector2, delta: float) -> Vector2:
	var depth := rel.dot(travel())
	if depth < -_hold_at or _held_s >= stay_s:
		return rel + travel() * speed * delta
	_held_s += delta
	var along := travel() * rel.dot(travel())
	return along + across() * (_home.dot(across()) + sin(_held_s * 1.2) * sway)

func _act(delta: float) -> void:
	if escort_scene == null or released >= max_escorts or not is_holding():
		return
	_since += delta
	if _since < release_every:
		return
	_since -= release_every
	var escort := escort_scene.instantiate() as Node2D
	if escort == null:
		return
	released += 1
	var at := position + travel() * hit_radius
	var home := stage()
	if home != null:
		home.adopt(escort, at)
	elif get_parent() != null:
		escort.position = at
		get_parent().add_child(escort)
	else:
		escort.free()
