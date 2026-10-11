class_name RpgGrapple
extends Node2D
## The grapple arm of a soldier (the child "Grapple"): a hook that is fired along the aim (up,
## the two upper diagonals, forward) and flies until it hits something to hold on to, or until
## its reach ends. What it holds on to is any solid tile or plank; with `tagged_only`, only
## tiles with the custom data `grapple`.
##
## A hook that holds **swings** the soldier: the rope is reeled in to `reel` of its length (so
## the feet leave the ground) and the soldier hangs on it as a pendulum (RpgPlatformMath.
## swing_step), pushed a little by left and right. Letting go keeps the speed of the swing. A
## hook that holds straight above **hoists**: the soldier climbs the rope, and when the tile it
## hangs from has room to stand on (a plank, the edge of a ledge) it climbs on to it; else it
## hangs under the tile until it lets go.
##
## The soldier tells it what to do (`fire`, `fly`, `move`, `release`) and it moves the body it
## is given; it does not know the soldier's class.

signal hooked(at: Vector2)
signal missed
signal hoisted
signal let_go

enum State { IDLE, FLYING, SWING, HOIST, HANG }

## Nearer than this to straight above (rad) a hook that holds hoists instead of swinging.
const HOIST_ANGLE := 0.2
## How much of the pull of the rope a held direction adds.
const PUMP := 0.5
## A swing that is stopped by something for this long lets go by itself.
const STUCK_S := 0.3
const LINK := Color(0.75, 0.78, 0.82)

@export var tile: float = 16.0
## How far the hook flies, in tiles.
@export var reach_tiles: float = 7.0
## Tiles a second.
@export var speed_tiles: float = 45.0
## The rope of a swing is this much of the way to the hook.
@export var reel: float = 0.6
## How fast the rope is reeled in, and how fast a hoist climbs: tiles a second.
@export var reel_tiles: float = 14.0
@export var hoist_tiles: float = 9.0
@export var tagged_only: bool = false
## The hook, drawn pointing up; a drawn one without it.
@export var hook_texture: Texture2D = null

var state := State.IDLE
## Where the hook is and where it holds, as global points.
var hook := Vector2.ZERO
var anchor := Vector2.ZERO
## The rope now and the rope of the swing, in px.
var length := 0.0
var swing_length := 0.0
## The swing: the angle from straight down (rad, to the right is positive) and its speed.
var angle := 0.0
var omega := 0.0

var _dir := Vector2.UP
var _flown := 0.0
var _hand := Vector2.ZERO  # relative to the body
var _ledge := false
var _ledge_top := Vector2.ZERO
var _stuck := 0.0

func is_idle() -> bool:
	return state == State.IDLE

func is_flying() -> bool:
	return state == State.FLYING

## True while the hook holds (a swing, a hoist or hanging).
func is_attached() -> bool:
	return state == State.SWING or state == State.HOIST or state == State.HANG

func reach_px() -> float:
	return reach_tiles * tile

## The way a hook can be fired for an aim: up, an upper diagonal or forward. An aim downward
## fires forward.
static func direction(aim: Vector2, facing: int) -> Vector2:
	if aim.y > 0.01 or aim == Vector2.ZERO:
		return Vector2(1.0 if facing >= 0 else -1.0, 0.0)
	return aim.normalized()

## Fires the hook from the global point `from` along `dir`. False while one is out.
func fire(from: Vector2, dir: Vector2) -> bool:
	if state != State.IDLE or dir == Vector2.ZERO:
		return false
	state = State.FLYING
	hook = from
	_dir = dir.normalized()
	_flown = 0.0
	queue_redraw()
	return true

## What the hook can hold on to at the global point `at`: {} for nothing, else `layer`, `cell`
## and `one_way`.
func hold_at(layers: Array[TileMapLayer], at: Vector2) -> Dictionary:
	for layer in layers:
		if not is_instance_valid(layer) or layer.tile_set == null:
			continue
		var cell := RpgSideTiles.cell_at(layer, at)
		var data := layer.get_cell_tile_data(cell)
		if data == null:
			continue
		var solid := layer.tile_set.get_physics_layers_count() > 0 and data.get_collision_polygons_count(0) > 0
		var one_way := RpgSideTiles.one_way_at([layer], at)
		if not solid and not one_way:
			continue
		if tagged_only and not RpgSideTiles.cell_has(layer, cell, "grapple"):
			continue
		return {"layer": layer, "cell": cell, "one_way": one_way and not solid}
	return {}

static func _solid_at(layers: Array[TileMapLayer], at: Vector2) -> bool:
	for layer in layers:
		if not is_instance_valid(layer) or layer.tile_set == null or layer.tile_set.get_physics_layers_count() <= 0:
			continue
		var data := layer.get_cell_tile_data(RpgSideTiles.cell_at(layer, at))
		if data != null and data.get_collision_polygons_count(0) > 0:
			return true
	return false

## One step of a hook in the air. `body` is who fired it, `hand` where its end of the rope is
## (relative to the body). True when the hook took hold in this step.
func fly(delta: float, body: CharacterBody2D, hand: Vector2, layers: Array[TileMapLayer]) -> bool:
	if state != State.FLYING:
		return false
	_hand = hand
	var left := speed_tiles * tile * delta
	var piece := maxf(1.0, tile * 0.25)
	while left > 0.0:
		var move := minf(piece, left)
		left -= move
		var next := hook + _dir * move
		_flown += move
		var held := hold_at(layers, next)
		if not held.is_empty():
			_take_hold(body, held, layers)
			return true
		hook = next
		if _flown >= reach_px():
			state = State.IDLE
			missed.emit()
			queue_redraw()
			return false
	queue_redraw()
	return false

func _take_hold(body: CharacterBody2D, held: Dictionary, layers: Array[TileMapLayer]) -> void:
	anchor = hook
	var from := body.global_position + _hand
	var rope := from - anchor
	length = rope.length()
	angle = atan2(rope.x, rope.y)
	_stuck = 0.0
	var layer: TileMapLayer = held["layer"]
	var cell: Vector2i = held["cell"]
	if anchor.y < from.y and absf(atan2(absf(rope.x), absf(rope.y))) <= HOIST_ANGLE:
		state = State.HOIST
		omega = 0.0
		var middle := RpgSideTiles.cell_center(layer, cell)
		var size := Vector2(layer.tile_set.tile_size)
		_ledge_top = Vector2(middle.x, middle.y - size.y * 0.5)
		# room to stand on the tile: the two cells above it are not solid
		_ledge = not _solid_at(layers, _ledge_top + Vector2(0.0, -size.y * 0.5)) and not _solid_at(layers, _ledge_top + Vector2(0.0, -size.y * 1.5))
	else:
		state = State.SWING
		swing_length = maxf(tile, length * reel)
		# what the body was doing goes on along the swing
		omega = body.velocity.dot(Vector2(cos(angle), -sin(angle))) / maxf(1.0, length)
	hooked.emit(anchor)
	queue_redraw()

## One step of a body on the rope: the swing or the hoist. `gravity_px` is the body's own,
## `steer` what is held to the left (-1) or the right (1).
func move(body: CharacterBody2D, delta: float, gravity_px: float, steer: float = 0.0) -> void:
	match state:
		State.SWING:
			_swing(body, delta, gravity_px, steer)
		State.HOIST:
			_hoist(body, delta)
		State.HANG:
			body.velocity = Vector2.ZERO
	queue_redraw()

func _swing(body: CharacterBody2D, delta: float, gravity_px: float, steer: float) -> void:
	length = move_toward(length, swing_length, reel_tiles * tile * delta)
	omega += clampf(steer, -1.0, 1.0) * PUMP * gravity_px / maxf(1.0, length) * delta
	var next := RpgPlatformMath.swing_step(angle, omega, length, gravity_px, delta)
	angle = next.x
	omega = next.y
	var from := body.global_position + _hand
	var to := anchor + Vector2(sin(angle), cos(angle)) * length
	var hit := body.move_and_collide(to - from)
	if hit != null:
		var rope := body.global_position + _hand - anchor
		angle = atan2(rope.x, rope.y)
		omega = 0.0
		_stuck += delta
		if _stuck >= STUCK_S and is_equal_approx(length, swing_length):
			body.velocity = Vector2.ZERO
			release()
			return
	else:
		_stuck = 0.0
	body.velocity = swing_velocity()

func _hoist(body: CharacterBody2D, delta: float) -> void:
	var from := body.global_position + _hand
	var up := minf(hoist_tiles * tile * delta, maxf(0.0, from.y - anchor.y))
	var hit := body.move_and_collide(Vector2(clampf(anchor.x - from.x, -up, up), -up))
	body.velocity = Vector2.ZERO
	length = maxf(0.0, body.global_position.y + _hand.y - anchor.y)
	if hit == null and length > 0.5:
		return
	if _ledge:
		body.global_position = _ledge_top + Vector2.UP  # a pixel above it: it lands on it
		state = State.IDLE
		hoisted.emit()
	else:
		state = State.HANG

## The speed of a body on the swing now, px a second.
func swing_velocity() -> Vector2:
	return Vector2(cos(angle), -sin(angle)) * length * omega if state == State.SWING else Vector2.ZERO

## Lets go of what the hook holds (or takes back a hook in the air).
func release() -> void:
	if state == State.IDLE:
		return
	state = State.IDLE
	omega = 0.0
	let_go.emit()
	queue_redraw()

func _draw() -> void:
	if state == State.IDLE:
		return
	var from := _hand
	var to := to_local(hook if state == State.FLYING else anchor)
	var rope := to - from
	var step := maxf(2.0, tile * 0.25)
	var links := int(rope.length() / step)
	for i in links:
		draw_circle(from + rope * (float(i) + 0.5) / maxf(1.0, float(links)), maxf(1.0, tile * 0.06), LINK)
	var turn := rope.angle() + PI * 0.5 if rope != Vector2.ZERO else 0.0
	draw_set_transform(to, turn)
	if hook_texture != null:
		draw_texture(hook_texture, -Vector2(hook_texture.get_size()) * 0.5)
	else:
		var s := maxf(2.0, tile * 0.2)
		draw_line(Vector2(-s, 0.0), Vector2(s, 0.0), LINK, 2.0)
		draw_line(Vector2(-s, 0.0), Vector2(-s, s), LINK, 2.0)
		draw_line(Vector2(s, 0.0), Vector2(s, s), LINK, 2.0)
	draw_set_transform(Vector2.ZERO, 0.0)
