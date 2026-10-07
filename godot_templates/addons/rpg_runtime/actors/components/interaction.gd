class_name RpgInteraction
extends Area2D
## Sits on the player in front of the feet and finds the nearest thing that can be interacted with.
## Collision mask: interactables (5) + npcs (4).

@export var tile_size: float = 16.0

var actor: RpgActor
var _shape: CollisionShape2D

func _ready() -> void:
	actor = _find_actor()
	collision_layer = 0
	collision_mask = 0
	set_collision_mask_value(4, true)
	set_collision_mask_value(5, true)
	monitorable = true  # an Area2D only detects StaticBody2D when it is monitorable too
	_shape = get_node_or_null("Shape") as CollisionShape2D
	if _shape == null:
		_shape = CollisionShape2D.new()
		_shape.name = "Shape"
		add_child(_shape)
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile_size * 0.75, tile_size * 0.75)
	_shape.shape = rect
	if actor != null:
		actor.facing_changed.connect(_on_facing_changed)
		_reposition(actor.facing)

func _find_actor() -> RpgActor:
	var node := get_parent()
	while node != null:
		if node is RpgActor:
			return node
		node = node.get_parent()
	return null

func _on_facing_changed(f: String) -> void:
	_reposition(f)

func _reposition(f: String) -> void:
	var dir := Vector2.DOWN
	match f:
		"up":
			dir = Vector2.UP
		"left":
			dir = Vector2.LEFT
		"right":
			dir = Vector2.RIGHT
	position = dir * tile_size * 0.6

func _has_interact(node: Node) -> bool:
	return node != actor and node.has_method("interact")

## The overlapping body/area with an `interact(actor)` method that is nearest to the feet.
func find_target() -> Node:
	var best: Node = null
	var best_dist := INF
	var feet := actor.global_position if actor != null else global_position
	var candidates: Array = []
	candidates.append_array(get_overlapping_bodies())
	candidates.append_array(get_overlapping_areas())
	for c in candidates:
		if not _has_interact(c):
			continue
		var d := feet.distance_to((c as Node2D).global_position)
		if d < best_dist:
			best_dist = d
			best = c
	return best

## Calls `interact(actor)` on the target. Returns false when nothing is in reach.
func try_interact() -> bool:
	var target := find_target()
	if target == null:
		return false
	RpgUtil.emit(&"interaction_started", [target])
	target.call("interact", actor)
	RpgUtil.emit(&"interaction_finished", [target])
	return true
