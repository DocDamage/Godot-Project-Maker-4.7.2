class_name RpgRacePickup
extends Node2D
## Something that lies on a track for a car to drive over. `kind`: `boost` (one more boost),
## `missile` or `bomb` (a weapon to carry), `shield` (takes one hit), or a part that stays for
## the championship: `speed`, `tyres`, `acceleration` (only the player takes those, and a part
## is taken once). The others come back after `respawn_s`. The race asks which car is on it
## (`reaches`) and says when it was taken (`take`).
##
## Its `position` is its place in the plan of the track. On a track seen at an angle
## (RpgRaceView, T17.15) it is drawn where that place is on the screen.

const KINDS: Array[String] = ["boost", "missile", "bomb", "shield"]
const PARTS: Array[String] = ["speed", "tyres", "acceleration"]
const COLORS := {
	"boost": Color(0.35, 0.86, 1.0),
	"missile": Color(0.95, 0.85, 0.3),
	"bomb": Color(0.2, 0.2, 0.24),
	"shield": Color(0.5, 0.7, 1.0),
	"speed": Color(0.95, 0.4, 0.3),
	"tyres": Color(0.6, 0.6, 0.65),
	"acceleration": Color(0.5, 0.9, 0.4),
}

@export var kind: String = "boost"
## The size of a tile in px.
@export var tile: float = 16.0
@export var respawn_s: float = 6.0
## The picture of a pickup of the packs (tinted by its kind); a drawn one without it.
@export var texture: Texture2D = null

var active := true
var _wait := 0.0

func is_part() -> bool:
	return PARTS.has(kind)

func radius() -> float:
	return tile * 0.9

## True when a car at `point` drives over it.
func reaches(point: Vector2) -> bool:
	return active and point.distance_to(position) <= radius()

## It was taken: a part is gone, the others come back.
func take() -> void:
	active = false
	visible = false
	_wait = respawn_s

func advance(delta: float) -> void:
	if active or is_part():
		return
	_wait -= delta
	if _wait <= 0.0:
		active = true
		visible = true

## Where it is drawn, in the coordinates it is in.
func shown_position() -> Vector2:
	var seen := RpgRaceView.of(get_parent())
	return seen.to_screen(position) if seen != null else position

func _draw() -> void:
	var seen := RpgRaceView.of(get_parent())
	if seen != null:
		draw_set_transform(seen.to_screen(position) - position)
	var color: Color = COLORS.get(kind, Color.WHITE)
	if texture != null:
		draw_texture(texture, -Vector2(texture.get_size()) * 0.5, color.lightened(0.5))
		return
	var r := tile * 0.42
	var shape := PackedVector2Array([Vector2(0, -r), Vector2(r, 0), Vector2(0, r), Vector2(-r, 0)])
	if is_part():  # a part is a square, a pickup a diamond
		shape = PackedVector2Array([Vector2(-r, -r), Vector2(r, -r), Vector2(r, r), Vector2(-r, r)])
	draw_colored_polygon(shape, color)
	draw_polyline(shape + PackedVector2Array([shape[0]]), Color(0.05, 0.05, 0.08), 1.0)
