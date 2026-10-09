class_name RpgRoomExit
extends Area2D
## An exit on the edge of a room. The area lies just outside the room: a player who walks (or
## climbs, or jumps) out through the opening touches it and is taken to `target_exit` of
## `target_room`, with its speed, without a fade. The player arrives at the spawn point of the
## target room whose id is `target_exit`, a tile and a half inside that room.
##
## Layers: triggers (6), looking for the player (2).

signal used(player: Node)

## This exit's id: the partner's `target_exit`, and the id of the spawn point beside it.
@export var exit_id: String = ""
## The edge of the room it is on: "N", "E", "S" or "W".
@export var edge: String = "E"
## The room it leads to (a scene) and the exit of that room the player comes in through.
@export_file("*.tscn") var target_room: String = ""
@export var target_exit: String = ""

const OUTWARD := {"N": Vector2.UP, "E": Vector2.RIGHT, "S": Vector2.DOWN, "W": Vector2.LEFT}

func _ready() -> void:
	body_entered.connect(_on_body_entered)

## The direction out of the room through this exit.
func outward() -> Vector2:
	return OUTWARD.get(edge, Vector2.RIGHT)

## True for an exit in a side wall (the player walks through it); false for a ladder's.
func is_side() -> bool:
	return edge == "E" or edge == "W"

## The room this exit is in (an RpgRoom), found by what it can do: the room's script names this
## one, and with a reference back Godot reported both as still in use when a validation run quit
## (VAL-013).
func _room() -> Node:
	var node := get_parent()
	while node != null:
		if node.has_method(&"just_arrived"):
			return node
		node = node.get_parent()
	return null

func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		use(body)

## What the player takes along into the next room.
func carry_of(player: Node) -> Dictionary:
	var out := {}
	if player is CharacterBody2D:
		out["velocity"] = (player as CharacterBody2D).velocity
	if player is Node2D:
		out["offset"] = (player as Node2D).global_position - global_position
	if "facing" in player:
		out["facing"] = player.get("facing")
	if "on_ladder" in player:
		out["on_ladder"] = player.get("on_ladder")
	return out

## Takes the player to the target room. False when the exit leads nowhere, when a cutscene runs,
## or in the moment after the player arrived through this room's exits.
func use(player: Node) -> bool:
	if target_room == "":
		push_warning("[RPG-WORLD] the exit %s has no target_room" % name)
		return false
	var room := _room()
	if (room != null and RpgUtil.to_bool(room.call(&"just_arrived"))) or RpgSequenceRunner.running():
		return false
	var router := RpgUtil.router()
	if router == null:
		push_error("[RPG-WORLD] SceneRouter autoload is missing")
		return false
	if router.is_busy():
		return false
	used.emit(player)
	router.go_to_room(target_room, target_exit, carry_of(player))
	return true
