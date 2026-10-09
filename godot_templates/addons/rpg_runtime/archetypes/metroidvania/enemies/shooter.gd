class_name RpgShooterEnemy
extends RpgSideEnemy
## Stands where it is and shoots: a projectile (the shared RpgProjectile) at the player every
## `interval_s` while the player is within `range_tiles` and nothing solid is between them.

@export var range_tiles: float = 8.0
@export var interval_s: float = 1.5
## The shot's speed in px/s at 16 px tiles.
@export var shot_speed: float = 120.0

## Counts the shots fired (tests and the smoke run look at it).
var shots := 0
var last_shot: RpgProjectile = null
var _cooldown := 0.6

## True when the player is in range and no wall is in the way.
func sees(player: Node2D) -> bool:
	if player == null or tiles_to(player) > range_tiles or not is_inside_tree():
		return false
	var query := PhysicsRayQueryParameters2D.create(body_center(), middle_of(player), 1)  # world
	query.exclude = [get_rid()]
	return get_world_2d().direct_space_state.intersect_ray(query).is_empty()

func think(delta: float) -> void:
	move_x = 0.0
	_cooldown = maxf(0.0, _cooldown - delta)
	var player := find_player()
	if player == null:
		return
	var dx := player.global_position.x - global_position.x
	if absf(dx) > 1.0:
		set_facing(1 if dx > 0.0 else -1)
	if _cooldown <= 0.0 and sees(player):
		_cooldown = interval_s
		fire(middle_of(player))

## One shot from the middle of the body toward `target` (a global point), added beside the enemy.
func fire(target: Vector2) -> RpgProjectile:
	var from := body_center()
	var direction := (target - from).normalized() if target.distance_to(from) > 0.5 else Vector2(facing, 0)
	var parent := get_parent()
	var shot := RpgProjectile.create(self, (from - (parent as Node2D).global_position) if parent is Node2D else from, direction, &"enemy", px(shot_speed), range_tiles * tile_size * 1.25)
	shots += 1
	last_shot = shot
	if parent != null:
		parent.add_child(shot)
	play_sound(&"sfx_attack")
	return shot
