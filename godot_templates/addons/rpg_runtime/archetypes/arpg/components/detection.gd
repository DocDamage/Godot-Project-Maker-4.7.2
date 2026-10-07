class_name RpgDetection
extends Node
## Enemy component: finds the player. The player is seen when it is within `vision_px` and a line
## of sight from the enemy to the player (RayCast2D "Sight" on the world layer) hits nothing.

var vision_px := 96.0

var actor: RpgActor
var sight: RayCast2D
## Tests set this to stand in for the player's position.
var fake_player_position: Variant = null

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor
	if actor != null:
		sight = actor.get_node_or_null("Sight") as RayCast2D

## Global position of a node; the local one while it is not in the tree (unit tests).
static func position_of(node: Node2D) -> Vector2:
	return node.global_position if node.is_inside_tree() else node.position

func actor_position() -> Vector2:
	return position_of(actor)

func player() -> Node2D:
	if not is_inside_tree():
		return null
	return get_tree().get_first_node_in_group("player") as Node2D

## The player is there and still standing.
func player_alive() -> bool:
	if fake_player_position != null:
		return true
	var p := player()
	if p == null:
		return false
	var health := p.get_node_or_null("Health") as RpgHealth
	return health == null or not health.is_dead()

func player_position() -> Vector2:
	if fake_player_position != null:
		return fake_player_position
	var p := player()
	return position_of(p) if p != null else actor_position()

func distance_to_player() -> float:
	return actor_position().distance_to(player_position())

## True when nothing on the world layer lies between the enemy and `target` (global position).
func line_of_sight_clear(target: Vector2) -> bool:
	if sight == null or not sight.is_inside_tree():
		return true
	sight.target_position = target - sight.global_position
	sight.force_raycast_update()
	return not sight.is_colliding()

func can_see_player() -> bool:
	if actor == null or not player_alive():
		return false
	if distance_to_player() > vision_px:
		return false
	return line_of_sight_clear(player_position())
