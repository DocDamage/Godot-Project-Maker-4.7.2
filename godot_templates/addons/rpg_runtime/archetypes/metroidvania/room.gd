class_name RpgRoom
extends RpgMapRoot
## A room of a metroidvania: a map seen from the side, one or more screens large. Its layers are
## Background (parallax), Ground, Platforms, Hazards, Decoration and Foreground; its exits
## (RpgRoomExit) are on its edges; it owns the camera (RpgSideCamera) and keeps it inside the room.
##
## Rooms are joined by exits, not by doors: crossing one changes the room without a fade, the
## player keeps its speed, and the camera slides in.

## True for every room: the dock stands dropped objects on the floor instead of Y-sorting them.
@export var side_view: bool = true
## The size of the room in tiles and the size of a tile in px (set by the recipe).
@export var room_size: Vector2i = Vector2i(40, 23)
@export var tile_size: int = 16
## Where the room lies on the world's grid of screens (the room map draws it there).
@export var grid_cell: Vector2i = Vector2i.ZERO
## What the room is in the plan: start, corridor, shaft, guardian, pickup or end.
@export var kind: String = "corridor"

const CAMERA_NODE := "Camera"
const SLIDE_S := 0.25
## A player who has just arrived does not leave again through the exit it stands in.
const ARRIVAL_GRACE_MS := 250

var arrived_at_ms := -100000

func _ready() -> void:
	super._ready()
	var view := camera()
	if view != null:
		view.set_limits(bounds())
	RpgAbilities.apply_broken_cells(self, String(map_id))
	_first_view.call_deferred()

## The camera starts on the player, unless the player has just come in through an exit: then the
## view is sliding in and is left to it.
func _first_view() -> void:
	if not just_arrived():
		player_placed(null)

## The room's rectangle in global px.
func bounds() -> Rect2:
	return Rect2(global_position if is_inside_tree() else position, Vector2(room_size * tile_size))

func camera() -> RpgSideCamera:
	return get_node_or_null(CAMERA_NODE) as RpgSideCamera

## Every exit of the room, in tree order.
func exits() -> Array[RpgRoomExit]:
	var out: Array[RpgRoomExit] = []
	for node in find_children("*", "Area2D", true, false):
		if node is RpgRoomExit:
			out.append(node)
	return out

func exit_named(id: String) -> RpgRoomExit:
	for found in exits():
		if found.exit_id == id:
			return found
	return null

## True for a moment after the player arrived: exits do not fire then.
func just_arrived() -> bool:
	return Time.get_ticks_msec() - arrived_at_ms < ARRIVAL_GRACE_MS

## Called by the scene router whenever it has put the player somewhere in this room (a spawn
## point, a loaded position): the camera goes there at once.
func player_placed(_player: Node) -> void:
	var view := camera()
	if view != null and is_inside_tree():
		view.target = null
		view.snap_to_target()

## The player comes in through the exit `exit_id` (the scene router calls this after a room
## change). `carry` is what it brought along: {velocity, facing, on_ladder, offset}. `offset` is
## where it was relative to the exit it left through, so a jump across the edge goes on at its
## height. The camera slides in from the side the player came from.
func arrive(exit_id: String, carry: Dictionary = {}) -> void:
	arrived_at_ms = Time.get_ticks_msec()
	var player := get_player()
	if player == null:
		return
	var spawn := get_spawn(StringName(exit_id))
	var at := spawn.global_position if spawn != null else player.global_position
	var through := exit_named(exit_id)
	var offset: Vector2 = carry.get("offset", Vector2.ZERO)
	if through != null and through.is_side():
		at.y += minf(0.0, offset.y)  # in the air above the floor of the opening
	player.global_position = at
	if player is CharacterBody2D and carry.has("velocity"):
		(player as CharacterBody2D).velocity = carry["velocity"]
	if carry.has("facing") and player.has_method(&"apply_facing"):
		player.call(&"apply_facing", carry["facing"])
	elif spawn != null and player.has_method(&"apply_facing"):
		player.call(&"apply_facing", spawn.facing)
	if carry.has("on_ladder") and "on_ladder" in player:
		player.set("on_ladder", carry["on_ladder"])
	if player.has_method(&"refresh_layers"):
		player.call(&"refresh_layers")
	var view := camera()
	if view == null:
		return
	view.target = null
	view.snap_to_target()
	if through != null:
		# from the side the player came from: the room that was left slides out of view
		view.slide_in(through.outward(), SLIDE_S)
