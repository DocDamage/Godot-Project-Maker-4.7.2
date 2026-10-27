class_name RpgPlacedThing
extends StaticBody2D
## A thing the farmer made and placed (T18.15): a fence piece, a chest, a sprinkler, a scarecrow,
## a path stone, a preserves jar. RpgFarmWorkshop keeps what it is and where (`thing_id`) and
## makes this node when its map is shown; `interact` hands it to the workshop. Drawn in plain
## shapes of the size of a cell. A path stone does not block; the others do.

const COLOURS := {
	"fence_piece": [Color(0.55, 0.38, 0.22), Color(0.42, 0.28, 0.16)],
	"chest": [Color(0.6, 0.4, 0.2), Color(0.85, 0.7, 0.3)],
	"sprinkler": [Color(0.55, 0.58, 0.62), Color(0.35, 0.6, 0.9)],
	"scarecrow": [Color(0.75, 0.62, 0.35), Color(0.5, 0.3, 0.2)],
	"path_stone": [Color(0.6, 0.6, 0.58), Color(0.5, 0.5, 0.48)],
	"preserves_jar": [Color(0.8, 0.85, 0.9, 0.9), Color(0.75, 0.3, 0.3)],
	"stove": [Color(0.35, 0.35, 0.38), Color(0.85, 0.4, 0.2)],
}
const STATION := "res://addons/rpg_runtime/world/station.gd"

@export var thing_id := 0
@export var kind := ""

## A thing of `kind` drawn for cells of `tile` px; `blocks`: on the world layer.
static func make(id: int, of_kind: String, tile: int, blocks: bool) -> RpgPlacedThing:
	var made := RpgPlacedThing.new()
	made.thing_id = id
	made.kind = of_kind
	made.name = "Placed_%d" % id
	made.collision_layer = 0
	made.collision_mask = 0
	made.set_collision_layer_value(5, true)  # interactables: `interact` finds it
	if blocks:
		made.set_collision_layer_value(1, true)
	var shape := CollisionShape2D.new()
	var box := RectangleShape2D.new()
	box.size = Vector2(tile, tile) * 0.8
	shape.shape = box
	shape.position = Vector2(0, -tile * 0.4)
	made.add_child(shape)
	var colours: Array = COLOURS.get(of_kind, [Color.GRAY, Color.DIM_GRAY])
	var t := float(tile)
	for part: Array in _parts(of_kind, t):
		var rect := Polygon2D.new()
		var r: Rect2 = part[0]
		rect.polygon = PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
		rect.color = colours[RpgUtil.to_int(part[1])]
		made.add_child(rect)
	if of_kind == "stove":  # a kitchen (T18.16): the crafting window on its tab
		made.add_child(kitchen_station(tile, "placed_stove_%d" % id))
	return made

## The RpgStation of a kitchen: `kitchen`, keeping its queue under `key`.
static func kitchen_station(tile: int, key: String) -> Area2D:
	var station := Area2D.new()
	station.name = "Station"
	station.set_script(load(STATION))
	station.set("station_id", &"kitchen")
	station.set("entity_id", key)
	station.set("title", "FARM_KITCHEN")
	station.collision_layer = 0
	station.collision_mask = 0
	station.set_collision_layer_value(5, true)
	var reach := CollisionShape2D.new()
	var area := RectangleShape2D.new()
	area.size = Vector2(tile, tile)
	reach.shape = area
	reach.position = Vector2(0.0, -tile * 0.5)
	station.add_child(reach)
	return station

## [Rect2, colour index] of the drawing, the foot at (0, 0).
static func _parts(of_kind: String, t: float) -> Array:
	match of_kind:
		"fence_piece":
			return [[Rect2(-t * 0.45, -t * 0.7, t * 0.15, t * 0.7), 0], [Rect2(t * 0.3, -t * 0.7, t * 0.15, t * 0.7), 0], [Rect2(-t * 0.5, -t * 0.55, t, t * 0.12), 1], [Rect2(-t * 0.5, -t * 0.3, t, t * 0.12), 1]]
		"chest":
			return [[Rect2(-t * 0.4, -t * 0.6, t * 0.8, t * 0.55), 0], [Rect2(-t * 0.08, -t * 0.4, t * 0.16, t * 0.12), 1]]
		"sprinkler":
			return [[Rect2(-t * 0.1, -t * 0.5, t * 0.2, t * 0.45), 0], [Rect2(-t * 0.3, -t * 0.55, t * 0.6, t * 0.1), 1]]
		"scarecrow":
			return [[Rect2(-t * 0.06, -t * 1.2, t * 0.12, t * 1.2), 1], [Rect2(-t * 0.45, -t * 0.9, t * 0.9, t * 0.12), 1], [Rect2(-t * 0.2, -t * 1.35, t * 0.4, t * 0.3), 0]]
		"path_stone":
			return [[Rect2(-t * 0.4, -t * 0.3, t * 0.8, t * 0.25), 0]]
		"preserves_jar":
			return [[Rect2(-t * 0.22, -t * 0.55, t * 0.44, t * 0.5), 0], [Rect2(-t * 0.16, -t * 0.4, t * 0.32, t * 0.3), 1]]
		"stove":
			return [[Rect2(-t * 0.42, -t * 0.8, t * 0.84, t * 0.78), 0], [Rect2(-t * 0.25, -t * 0.45, t * 0.5, t * 0.25), 1]]
	return [[Rect2(-t * 0.4, -t * 0.5, t * 0.8, t * 0.5), 0]]

## `interact` (RpgInteraction calls it): the workshop uses the thing (a stove's station answers
## for itself).
func interact(actor: Node = null) -> void:
	if kind == "stove":
		var station := get_node_or_null("Station")
		if station != null:
			station.call("interact", actor)
		return
	var workshop := RpgFarmWorkshop.current()
	if workshop != null:
		workshop.use_thing(thing_id)
