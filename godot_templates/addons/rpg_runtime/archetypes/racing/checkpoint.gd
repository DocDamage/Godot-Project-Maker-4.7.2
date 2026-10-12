class_name RpgRaceCheckpoint
extends RefCounted
## A line across the road of a track that a race counts crossings of: a checkpoint, or the
## start line. It has a place, the way the race goes there and a width; it is crossed by going
## over it that way, within its width.

var id := ""
var position := Vector2.ZERO
## The way the race goes over the line: rad, 0 is to the right.
var heading := 0.0
## How wide the line is, in px.
var width := 144.0

static func make(at: Vector2, way: float, wide: float, label: String = "") -> RpgRaceCheckpoint:
	var gate := RpgRaceCheckpoint.new()
	gate.id = label
	gate.position = at
	gate.heading = way
	gate.width = wide
	return gate

## A checkpoint from its entry in the list of a track (`position` [x, y], `heading`, `width`).
static func from_data(data: Dictionary, fallback_width: float = 144.0) -> RpgRaceCheckpoint:
	var at := RpgUtil.to_array(data.get("position", data.get("line", [])))
	var where := Vector2(RpgUtil.to_float(at[0]), RpgUtil.to_float(at[1])) if at.size() >= 2 else Vector2.ZERO
	return make(where, RpgUtil.to_float(data.get("heading", 0.0)), RpgUtil.to_float(data.get("width", fallback_width), fallback_width), RpgUtil.to_str(data.get("id", "")))

## How far `point` is past the line, along the way of the race (negative: before it).
func along(point: Vector2) -> float:
	return (point - position).dot(Vector2.from_angle(heading))

## How far `point` is from the middle of the line, sideways.
func across(point: Vector2) -> float:
	return absf((point - position).dot(Vector2.from_angle(heading + PI * 0.5)))

## True when the step from `from` to `to` went over the line the right way, within its width.
func crossed(from: Vector2, to: Vector2) -> bool:
	if along(from) >= 0.0 or along(to) < 0.0:
		return false
	return across(to) <= width * 0.5 and from.distance_to(to) <= width
