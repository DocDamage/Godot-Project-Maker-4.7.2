class_name RpgPatrolEnemy
extends RpgSideEnemy
## Walks its platform back and forth: it turns at a wall and at an edge (a ray ahead of its feet
## finds no floor), and hurts on contact.

## The side it walks to first: -1 left, 1 right.
@export var start_direction: int = -1

var direction := -1
var _ledge: RayCast2D = null

func _ready() -> void:
	super._ready()
	direction = -1 if start_direction < 0 else 1
	set_facing(direction)
	_ledge = RayCast2D.new()
	_ledge.name = "Ledge"
	_ledge.collision_mask = 0
	_ledge.set_collision_mask_value(1, true)  # world
	_ledge.set_collision_mask_value(RpgSideTiles.ONE_WAY_LAYER, true)
	_ledge.hit_from_inside = true
	_ledge.target_position = Vector2(0.0, tile_size * 0.75)
	add_child(_ledge)

## True when there is floor a step ahead of the feet.
func floor_ahead() -> bool:
	if _ledge == null:
		return true
	_ledge.position = Vector2(direction * (body_width() * 0.5 + 3.0), -2.0)
	_ledge.force_raycast_update()
	return _ledge.is_colliding()

func turn() -> void:
	direction = -direction
	set_facing(direction)

func think(_delta: float) -> void:
	if is_on_floor() and ((is_on_wall() and signf(get_wall_normal().x) == -float(direction)) or not floor_ahead()):
		turn()
	move_x = float(direction)
