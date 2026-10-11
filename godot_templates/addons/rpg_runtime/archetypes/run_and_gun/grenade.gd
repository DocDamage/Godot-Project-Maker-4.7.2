class_name RpgGrenade
extends Node2D
## A thrown grenade: it flies an arc, and goes off when it lands, when it reaches something it
## can hurt, or when its fuse runs out. The blast hurts every target within its radius.

signal exploded(targets_hit: int)

@export var velocity: Vector2 = Vector2.ZERO
## Px a second squared.
@export var gravity: float = 600.0
@export var fuse_s: float = 1.5
@export var blast_radius: float = 40.0
@export var damage: int = 5
## The physics layers the grenade lands on.
@export_flags_2d_physics var wall_mask: int = 1
@export var explosion_scene: PackedScene = null
@export var sound: StringName = &"sfx_grenade"

## False for a test that steps the grenade by hand.
var auto_advance := true
var age := 0.0
var _done := false

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## The targets a blast at `at` (a global point) would hurt: the nodes of the pool's target
## group within `blast_radius` (a target's own radius counts).
func targets_at(at: Vector2) -> Array[Node2D]:
	var out: Array[Node2D] = []
	if not is_inside_tree():
		return out
	for node in get_tree().get_nodes_in_group(RpgArcadeBulletPool.TARGET_GROUP):
		if not (node is Node2D) or node.is_queued_for_deletion() or not node.has_method(&"take_hit"):
			continue
		var target := node as Node2D
		var reach := blast_radius + RpgUtil.to_float(target.get(&"hit_radius"), 0.0)
		if target.global_position.distance_squared_to(at) <= reach * reach:
			out.append(target)
	return out

func _landed() -> bool:
	if wall_mask == 0 or not is_inside_tree():
		return false
	var world := get_world_2d()
	if world == null:
		return false
	var query := PhysicsPointQueryParameters2D.new()
	query.position = global_position
	query.collision_mask = wall_mask
	query.collide_with_areas = false
	return not world.direct_space_state.intersect_point(query, 1).is_empty()

## One step of the flight.
func advance(delta: float) -> void:
	if _done:
		return
	age += delta
	velocity.y += gravity * delta
	position += velocity * delta
	if age >= fuse_s or _landed() or (is_inside_tree() and _touching()):
		explode()

## True when the grenade itself touches a target (not just its blast).
func _touching() -> bool:
	for node in get_tree().get_nodes_in_group(RpgArcadeBulletPool.TARGET_GROUP):
		if node is Node2D:
			var reach := RpgUtil.to_float(node.get(&"hit_radius"), 0.0)
			if (node as Node2D).global_position.distance_squared_to(global_position) <= reach * reach:
				return true
	return false

## The blast: every target in the radius takes the damage, and the grenade is gone.
func explode() -> void:
	if _done:
		return
	_done = true
	var hit := targets_at(global_position)
	for target in hit:
		target.call(&"take_hit", damage)
	if explosion_scene != null and get_parent() != null:
		var burst := explosion_scene.instantiate() as Node2D
		if burst != null:
			burst.position = position
			burst.set(&"sound", sound)
			get_parent().add_child(burst)
	exploded.emit(hit.size())
	queue_free()
