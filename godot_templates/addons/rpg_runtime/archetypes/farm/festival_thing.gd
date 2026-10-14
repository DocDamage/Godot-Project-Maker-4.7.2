class_name RpgFestivalThing
extends Area2D
## A thing of a festival day on the village (T17.25): an **egg** of the egg hunt, or the
## **table** of a contest or a feast. RpgFarmEvents makes it at a marker of the map, among the
## entities of the map so that it Y-sorts with the farmer, for that day only: it is in no saved
## scene. It is walked over, the table too; `interact` finds it (layer 5, the interactables).
## Both are drawn (no pack has a picture that is known to be one): an egg in one of a few
## colours, a table with a cloth and three dishes.

const EGG := "egg"
const TABLE := "table"
const EGG_COLOURS: Array[Color] = [Color(0.95, 0.55, 0.6), Color(0.55, 0.75, 0.95), Color(0.98, 0.85, 0.45), Color(0.65, 0.85, 0.6), Color(0.8, 0.65, 0.9)]
const SPECK := Color(1.0, 1.0, 1.0, 0.9)
const WOOD := Color(0.5, 0.33, 0.18)
const CLOTH := Color(0.93, 0.93, 0.88)
const DISHES: Array[Color] = [Color(0.85, 0.3, 0.25), Color(0.95, 0.75, 0.3), Color(0.4, 0.65, 0.35)]

## EGG or TABLE, and the marker of the map it is at (the `spots` and the `table` of the event).
var kind := EGG
var spot := ""

## Makes a thing: its area and its picture, its foot on the origin. `index` chooses the colour
## of an egg. On an isometric map (`diamond` is the diamond of its cells, T17.14) it lies on the
## middle of its cell and its area is the cell.
static func make(of_kind: String, at_spot: String, index: int, tile_px: int, diamond: Vector2i = Vector2i.ZERO) -> RpgFestivalThing:
	var node := RpgFestivalThing.new()
	node.name = ("Festival_%s" % at_spot).validate_node_name()
	node.kind = of_kind
	node.spot = at_spot
	node.collision_layer = 0
	node.collision_mask = 0
	node.set_collision_layer_value(5, true)
	node.monitoring = false
	node.monitorable = true
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	if diamond != Vector2i.ZERO:
		shape.shape = RpgFarmIso.diamond_shape(diamond)
	else:
		var rect := RectangleShape2D.new()
		rect.size = Vector2(tile_px, tile_px) * 0.8
		shape.shape = rect
		shape.position = Vector2(0.0, -tile_px * 0.5)
	node.add_child(shape)
	var picture := Node2D.new()
	picture.name = "Picture"
	if diamond != Vector2i.ZERO:
		picture.position = Vector2(0.0, diamond.y * 0.25)  # its foot on the near half of the cell
	node.add_child(picture)
	var unit := float(tile_px)
	if of_kind == TABLE:
		_draw_table(picture, unit)
	else:
		_draw_egg(picture, unit, EGG_COLOURS[posmod(index, EGG_COLOURS.size())])
	return node

static func _polygon(node_name: String, points: PackedVector2Array, colour: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	shape.polygon = points
	shape.color = colour
	return shape

static func _box(node_name: String, rect: Rect2, colour: Color) -> Polygon2D:
	return _polygon(node_name, PackedVector2Array([rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)]), colour)

## An egg two thirds of a tile high: an oval that is wider below its middle, with a band.
static func _draw_egg(picture: Node2D, unit: float, colour: Color) -> void:
	var half := unit * 0.27
	var height := unit * 0.66
	var points := PackedVector2Array()
	for i in 12:
		var angle := TAU * i / 12.0
		var up := -cos(angle)  # -1 at the foot, 1 at the tip
		var wide := half * (1.0 - 0.25 * maxf(0.0, up))
		points.append(Vector2(sin(angle) * wide, -height * 0.5 - up * height * 0.5))
	picture.add_child(_polygon("Egg", points, colour))
	picture.add_child(_box("Band", Rect2(-half * 0.8, -height * 0.5, half * 1.6, maxf(1.0, unit * 0.06)), SPECK))

## A table two tiles wide: two legs, a top, a cloth over it and three dishes on it.
static func _draw_table(picture: Node2D, unit: float) -> void:
	var wide := unit * 2.0
	var top := unit * 0.7
	picture.add_child(_box("LegLeft", Rect2(-wide * 0.5 + 1.0, -top, maxf(2.0, unit * 0.12), top), WOOD))
	picture.add_child(_box("LegRight", Rect2(wide * 0.5 - 1.0 - maxf(2.0, unit * 0.12), -top, maxf(2.0, unit * 0.12), top), WOOD))
	picture.add_child(_box("Top", Rect2(-wide * 0.5, -top - unit * 0.12, wide, unit * 0.14), WOOD))
	picture.add_child(_box("Cloth", Rect2(-wide * 0.5 + 1.0, -top - unit * 0.18, wide - 2.0, unit * 0.34), CLOTH))
	for i in DISHES.size():
		var x := (i - 1) * wide * 0.3
		picture.add_child(_box("Dish%d" % (i + 1), Rect2(x - unit * 0.12, -top - unit * 0.34, unit * 0.24, unit * 0.16), DISHES[i]))

## `interact` (RpgInteraction calls this): an egg is found; at the table whatever the festival
## of the day has to do there is done with the thing in the farmer's hand.
func interact(_actor: Node = null) -> void:
	var found := RpgFarmEvents.current()
	if found == null:
		return
	if kind == EGG:
		found.find_egg(spot)
		return
	var mode := RpgFarmMode.current()
	found.use_table(mode.hotbar.held_item() if mode != null and mode.hotbar != null else &"")
