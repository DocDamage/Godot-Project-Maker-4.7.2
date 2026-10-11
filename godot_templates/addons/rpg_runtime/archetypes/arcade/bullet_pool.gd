class_name RpgArcadeBulletPool
extends Node2D
## Every bullet of an arcade stage (shared by the kinds that shoot): 400 of the player's and
## 1,000 of the enemies', made once and used again. A bullet is a row of numbers, not a node: the pool moves them, draws them and finds
## what they hit, so a screen full of bullets costs one canvas item.
##
## A player's bullet hits the nodes of the group `arcade_targets` (each has a `hit_radius` and a
## method `take_hit(damage)`); an enemy's bullet hits the ship (the group `player`, with a
## `hit_radius` and a method `hit()`). What is hit is a circle around the node, or around
## `hit_center()` when the node has that method (a soldier who crouches). A bullet that leaves
## the screen goes back to the pool; so does one whose time is up (`life_s`, the range of a gun)
## and, with a `wall_mask`, one that flies into the ground.

signal player_bullet_hit(target: Node2D, damage: int)

enum Team { PLAYER, ENEMY }

const PLAYER_CAP := 400
const ENEMY_CAP := 1000
const TARGET_GROUP := &"arcade_targets"
const SHIP_GROUP := &"player"
## A bullet lives this far outside the screen before it is taken back, in px.
const MARGIN := 16.0
## How fast a homing bullet turns, in radians a second.
const HOMING_TURN := 4.0

## The picture of a bullet by its kind ("bullet", "laser", "missile", "enemy"); a kind without
## one is drawn as a small square.
@export var textures: Dictionary = {}

## The physics layers that stop a bullet (the ground of a side-view stage); 0 stops none.
@export_flags_2d_physics var wall_mask: int = 0

## False for a test that steps the pool by hand.
var auto_advance := true
## The size of the screen when it is not the viewport's (a test whose window is another size).
var view_size := Vector2.ZERO

var _caps: Array[int] = [PLAYER_CAP, ENEMY_CAP]
var _live: Array[PackedByteArray] = [PackedByteArray(), PackedByteArray()]
var _pos: Array[PackedVector2Array] = [PackedVector2Array(), PackedVector2Array()]
var _vel: Array[PackedVector2Array] = [PackedVector2Array(), PackedVector2Array()]
var _damage: Array[PackedInt32Array] = [PackedInt32Array(), PackedInt32Array()]
var _radius: Array[PackedFloat32Array] = [PackedFloat32Array(), PackedFloat32Array()]
## Bit 1: homing. Bit 2: goes through what it hits.
var _flags: Array[PackedByteArray] = [PackedByteArray(), PackedByteArray()]
var _kind: Array[PackedStringArray] = [PackedStringArray(), PackedStringArray()]
## Seconds a bullet still flies; 0 flies until it leaves the screen.
var _life: Array[PackedFloat32Array] = [PackedFloat32Array(), PackedFloat32Array()]
var _free: Array[PackedInt32Array] = [PackedInt32Array(), PackedInt32Array()]
var _count: Array[int] = [0, 0]

func _init() -> void:
	for team in 2:
		var cap := _caps[team]
		_live[team].resize(cap)
		_pos[team].resize(cap)
		_vel[team].resize(cap)
		_damage[team].resize(cap)
		_radius[team].resize(cap)
		_flags[team].resize(cap)
		_kind[team].resize(cap)
		_life[team].resize(cap)
		_free[team].resize(cap)
		for i in cap:
			_free[team][i] = cap - 1 - i  # the lowest number is taken first

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta, view_rect())

## The part of the stage the camera shows, in the pool's own coordinates.
func view_rect() -> Rect2:
	var viewport := get_viewport()
	if viewport == null:
		return Rect2()
	var size := view_size if view_size != Vector2.ZERO else viewport.get_visible_rect().size
	var camera := viewport.get_camera_2d()
	var center := camera.get_screen_center_position() if camera != null else size * 0.5
	return Rect2(to_local(center - size * 0.5), size)

func capacity(team: int) -> int:
	return _caps[team]

## How many bullets of `team` are flying.
func active(team: int) -> int:
	return _count[team]

## Where the flying bullets of `team` are (for tests and for effects that look at them).
func positions(team: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in _caps[team]:
		if _live[team][i] == 1:
			out.append(_pos[team][i])
	return out

## A bullet of `team` starts at `at` with `velocity` (px a second). Returns its number, or -1
## when every bullet of the team is flying (nothing is fired then).
func fire(team: int, at: Vector2, velocity: Vector2, damage: int = 1, radius: float = 2.0,
		kind: String = "bullet", homing: bool = false, pierce: bool = false, life_s: float = 0.0) -> int:
	var free := _free[team]
	if free.is_empty():
		return -1
	var index := free[free.size() - 1]
	free.resize(free.size() - 1)
	_free[team] = free
	_live[team][index] = 1
	_pos[team][index] = at
	_vel[team][index] = velocity
	_damage[team][index] = damage
	_radius[team][index] = radius
	_flags[team][index] = (1 if homing else 0) | (2 if pierce else 0)
	_kind[team][index] = kind
	_life[team][index] = life_s
	_count[team] += 1
	queue_redraw()
	return index

func _release(team: int, index: int) -> void:
	if _live[team][index] == 0:
		return
	_live[team][index] = 0
	_free[team].append(index)
	_count[team] -= 1

## Every flying bullet of `team` goes back to the pool (a bomb, the end of a stage). Returns how
## many there were.
func clear(team: int) -> int:
	var cleared := _count[team]
	for i in _caps[team]:
		if _live[team][i] == 1:
			_release(team, i)
	queue_redraw()
	return cleared

## One step: the bullets move, those outside `view` (grown by MARGIN) go back to the pool, and
## hits are found. An empty `view` keeps every bullet.
func advance(delta: float, view: Rect2) -> void:
	var keep := view.grow(MARGIN)
	var bounded := view.size != Vector2.ZERO
	var targets := _targets()
	var ship := _ship()
	for team in 2:
		if _count[team] == 0:
			continue
		for i in _caps[team]:
			if _live[team][i] == 0:
				continue
			if _flags[team][i] & 1:
				_vel[team][i] = _steer(_pos[team][i], _vel[team][i], targets, delta)
			var at := _pos[team][i] + _vel[team][i] * delta
			_pos[team][i] = at
			if bounded and not keep.has_point(at):
				_release(team, i)
				continue
			if _life[team][i] > 0.0:
				_life[team][i] -= delta
				if _life[team][i] <= 0.0:
					_release(team, i)
					continue
			if wall_mask != 0 and _in_wall(at):
				_release(team, i)
				continue
			if team == Team.PLAYER:
				_hit_targets(i, at, targets)
			elif ship != null and _touches(at, _radius[team][i], ship):
				_release(team, i)
				ship.call(&"hit")
	queue_redraw()

func _targets() -> Array[Node2D]:
	var out: Array[Node2D] = []
	if not is_inside_tree():
		return out
	for node in get_tree().get_nodes_in_group(TARGET_GROUP):
		if node is Node2D and not node.is_queued_for_deletion():
			out.append(node as Node2D)
	return out

func _ship() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(SHIP_GROUP):
		if node is Node2D and node.has_method(&"hit"):
			return node as Node2D
	return null

func _touches(at: Vector2, radius: float, body: Node2D) -> bool:
	var reach := radius + RpgUtil.to_float(body.get(&"hit_radius"), 4.0)
	var center := body.global_position
	if body.has_method(&"hit_center"):
		var own: Variant = body.call(&"hit_center")
		if own is Vector2:
			center = own
	return to_local(center).distance_squared_to(at) <= reach * reach

## True when `at` (in the pool's coordinates) is inside something solid of `wall_mask`.
func _in_wall(at: Vector2) -> bool:
	var world := get_world_2d()
	if world == null or not is_inside_tree():
		return false
	var query := PhysicsPointQueryParameters2D.new()
	query.position = to_global(at)
	query.collision_mask = wall_mask
	query.collide_with_areas = false
	return not world.direct_space_state.intersect_point(query, 1).is_empty()

func _hit_targets(index: int, at: Vector2, targets: Array[Node2D]) -> void:
	var team := Team.PLAYER
	for target in targets:
		if not is_instance_valid(target) or target.is_queued_for_deletion():
			continue
		if not _touches(at, _radius[team][index], target):
			continue
		var damage := _damage[team][index]
		if target.has_method(&"take_hit"):
			target.call(&"take_hit", damage)
		player_bullet_hit.emit(target, damage)
		if _flags[team][index] & 2 == 0:
			_release(team, index)
			return

## A homing bullet turns toward the nearest target and keeps its speed.
func _steer(at: Vector2, velocity: Vector2, targets: Array[Node2D], delta: float) -> Vector2:
	var best: Node2D = null
	var best_d := INF
	for target in targets:
		if not is_instance_valid(target):
			continue
		var d := to_local(target.global_position).distance_squared_to(at)
		if d < best_d:
			best_d = d
			best = target
	if best == null:
		return velocity
	var wanted := (to_local(best.global_position) - at).angle()
	var now := velocity.angle()
	var turned := now + clampf(angle_difference(now, wanted), -HOMING_TURN * delta, HOMING_TURN * delta)
	return Vector2.from_angle(turned) * velocity.length()

func _draw() -> void:
	for team in 2:
		if _count[team] == 0:
			continue
		for i in _caps[team]:
			if _live[team][i] == 0:
				continue
			var texture: Texture2D = textures.get(_kind[team][i])
			var radius := _radius[team][i]
			if texture == null:
				var color := Color(1.0, 0.95, 0.5) if team == Team.PLAYER else Color(1.0, 0.4, 0.5)
				draw_rect(Rect2(_pos[team][i] - Vector2(radius, radius), Vector2(radius, radius) * 2.0), color)
				continue
			# a picture is drawn with its top toward where the bullet flies
			draw_set_transform(_pos[team][i], _vel[team][i].angle() + PI * 0.5)
			draw_texture(texture, -texture.get_size() * 0.5)
	draw_set_transform(Vector2.ZERO, 0.0)
