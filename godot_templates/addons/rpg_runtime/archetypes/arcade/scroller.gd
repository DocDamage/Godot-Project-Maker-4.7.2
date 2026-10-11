class_name RpgArcadeScroller
extends Node
## Moves the camera of a stage at a set speed along one axis (up, right, or not at all) and stops
## while somebody holds it: a wave that must be cleared, a boss. `progress` is how far the stage
## has come, in px; spawners and the end of the stage read it.

signal stopped
signal resumed
signal reached_end

const AXES: Array[String] = ["up", "right", "none"]

@export var axis: String = "up"
## Px per second.
@export var speed: float = 40.0
## Where the scrolling ends, in px; 0 never ends.
@export var length: float = 0.0
@export var camera_path: NodePath = NodePath("../Camera")

var progress := 0.0
## Where the camera was when the stage began.
var origin := Vector2.ZERO
var _holders: Array[int] = []
var _origin_known := false
var _ended := false

## The way the camera moves (a unit vector; zero for "none").
func direction() -> Vector2:
	match axis:
		"up":
			return Vector2.UP
		"right":
			return Vector2.RIGHT
	return Vector2.ZERO

## How far the camera is from where it began.
func offset() -> Vector2:
	return direction() * progress

func camera() -> Camera2D:
	return get_node_or_null(camera_path) as Camera2D

## The place of the camera now (the origin of the stage when it has no camera).
func view_center() -> Vector2:
	_learn_origin()
	return origin + offset()

func _learn_origin() -> void:
	if _origin_known:
		return
	var view := camera()
	if view != null:
		origin = view.position
		_origin_known = true

## `who` stops the scrolling until it calls release().
func hold(who: Object) -> void:
	var key := who.get_instance_id()
	if _holders.has(key):
		return
	_holders.append(key)
	if _holders.size() == 1:
		stopped.emit()

func release(who: Object) -> void:
	var key := who.get_instance_id()
	if not _holders.has(key):
		return
	_holders.erase(key)
	if _holders.is_empty():
		resumed.emit()

func is_held() -> bool:
	return not _holders.is_empty()

## True once the scrolling has come to `length` (never for a stage without a length).
func at_end() -> bool:
	return length > 0.0 and progress >= length

## The camera is led instead of moving by itself (a side-view stage follows its soldier): the
## progress rises to `wanted`, never falls, stops at the length and waits while it is held.
## Returns the px it moved.
func follow(wanted: float) -> float:
	_learn_origin()
	var before := progress
	if not is_held():
		var goal := maxf(progress, wanted)
		progress = minf(goal, length) if length > 0.0 else goal
	var view := camera()
	if view != null:
		view.position = origin + offset()
	if at_end() and not _ended:
		_ended = true
		reached_end.emit()
	return progress - before

## One step: the camera moves on unless it is held or at the end. Returns the px it moved.
func advance(delta: float) -> float:
	_learn_origin()
	var moved := 0.0
	if not is_held() and not at_end() and direction() != Vector2.ZERO:
		moved = speed * delta
		if length > 0.0:
			moved = minf(moved, length - progress)
		progress += moved
	var view := camera()
	if view != null:
		view.position = origin + offset()
	if at_end() and not _ended:
		_ended = true
		reached_end.emit()
	return moved
