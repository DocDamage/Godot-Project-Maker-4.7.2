extends RefCounted
## What a smoke step asks the map instead of the screen (T17.14): where a cell is, how far a
## step is, and which way to hold the pad to get somewhere. A step written with these holds on a
## map of squares and on an isometric one, with either of its control options: it says "walk to
## the door", not "press right and expect x to grow". On a map of squares every answer is the
## arithmetic the steps always had (a cell's middle, a tile to the east), and walking to a place
## that lies along an axis holds the one direction the step used to press.

const MOVES: Array[String] = ["move_right", "move_left", "move_down", "move_up"]
## The pad's eight directions, the four axes first: a place straight along one holds one key.
const PAD: Array[Vector2] = [
	Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1),
	Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1),
]

static func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

## The map that is played: the current scene.
static func map() -> Node:
	return _tree().current_scene

## The length of one step on the map: its tile, or one step from a diamond to the next.
static func tile(scene: Node = null) -> float:
	return float(RpgIso.map_unit(scene if scene != null else map()))

## How far `by` cells are on the screen, on the layer `layer` (or the map's ground).
static func cells(by: Vector2, layer: TileMapLayer = null) -> Vector2:
	var ground := layer if layer != null else RpgIso.ground_layer(map())
	if ground == null:
		return by * 16.0
	var east := ground.map_to_local(Vector2i(1, 0)) - ground.map_to_local(Vector2i.ZERO)
	var south := ground.map_to_local(Vector2i(0, 1)) - ground.map_to_local(Vector2i.ZERO)
	return east * by.x + south * by.y

## The pad's direction that brings a player at `from` nearest to `to` on the map `scene`: what
## the player's input makes of each of the eight is asked (the controls of an isometric map).
static func pad_toward(from: Vector2, to: Vector2, scene: Node = null) -> Vector2:
	var wanted := to - from
	if wanted.length() < 0.001:
		return Vector2.ZERO
	wanted = wanted.normalized()
	var best := Vector2.ZERO
	var best_dot := -2.0
	for input in PAD:
		var moved := RpgIso.move_vector(scene if scene != null else map(), input)
		if moved == Vector2.ZERO:
			continue
		var dot := moved.normalized().dot(wanted)
		if dot > best_dot + 0.0001:
			best_dot = dot
			best = input
	return best

## Holds the pad in a direction (and lets go of the others).
static func hold(input: Vector2) -> void:
	var want: Array[bool] = [input.x > 0.0, input.x < 0.0, input.y > 0.0, input.y < 0.0]
	for i in MOVES.size():
		if want[i]:
			Input.action_press(MOVES[i])
		else:
			Input.action_release(MOVES[i])

static func release() -> void:
	for action in MOVES:
		Input.action_release(action)

## Holds the pad towards `to` for the player `player` (call it every frame of a walk).
static func steer(player: Node2D, to: Vector2) -> void:
	hold(pad_toward(player.global_position, to))

## Walks the player towards `to` for at most `frames` physics frames; `until` (a Callable that
## returns true) ends the walk early. The pad is let go at the end.
## (`player` is asked whether it is still there: a door may have taken its map away.)
static func walk_toward(player: Variant, to: Vector2, frames: int, until: Callable = Callable()) -> void:
	var tree := _tree()
	for i in frames:
		if not is_instance_valid(player):
			break
		var body: Node2D = player
		steer(body, to)
		await tree.physics_frame
		if until.is_valid() and until.call() == true:
			break
	release()
