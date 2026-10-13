class_name RpgFarmTrough
extends StaticBody2D
## The trough of an animal house (T17.07). `interact` with it while the feed is held puts one
## portion in, which feeds every animal of the house for the day (RpgAnimalHouse.feed_with);
## with anything else in the hand it says what it wants. RpgAnimalHouse makes it at the marker
## `Trough` of the room when the room is entered (`make`): the map itself has only the marker.
## Its child `Feed` is shown while it is full. Layers: world (1) + interactables (5).

const WOOD := Color(0.5, 0.33, 0.18)
const WOOD_DARK := Color(0.34, 0.22, 0.12)
const HAY := Color(0.9, 0.78, 0.35)

## The house it stands in (`coop`, `barn`).
@export var house: String = ""

var herd: RpgAnimalHouse = null

## A trough of a tile, its lower edge on the origin, drawn: a box, and the feed in it. On an
## isometric map (`diamond` is the diamond of its cells, T17.14) it is a box on the middle of
## its cell, and it blocks the cell.
static func make(house_id: String, tile: float, diamond: Vector2i = Vector2i.ZERO) -> RpgFarmTrough:
	var trough := RpgFarmTrough.new()
	trough.name = "Trough"
	trough.house = house_id
	trough.collision_layer = 0
	trough.collision_mask = 0
	trough.set_collision_layer_value(1, true)
	trough.set_collision_layer_value(5, true)
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	if diamond != Vector2i.ZERO:
		shape.shape = RpgFarmIso.diamond_shape(diamond)
		trough.add_child(shape)
		trough.add_child(RpgFarmIso.box("Box", 0.12, 0.25, 0.88, 0.75, 0.0, tile * 0.3, WOOD, diamond))
		trough.add_child(RpgFarmIso.box("Inside", 0.2, 0.33, 0.8, 0.67, tile * 0.3, 0.5, WOOD_DARK, diamond))
		var hay := RpgFarmIso.box("Feed", 0.2, 0.33, 0.8, 0.67, tile * 0.3, tile * 0.08, HAY, diamond)
		hay.visible = false
		trough.add_child(hay)
		return trough
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile * 0.9, tile * 0.6)
	shape.shape = rect
	shape.position = Vector2(0.0, -tile * 0.3)
	trough.add_child(shape)
	trough.add_child(_box("Box", Vector2(tile * 0.9, tile * 0.5), 0.0, WOOD))
	trough.add_child(_box("Inside", Vector2(tile * 0.7, tile * 0.3), -tile * 0.15, WOOD_DARK))
	var feed := _box("Feed", Vector2(tile * 0.7, tile * 0.3), -tile * 0.15, HAY)
	feed.visible = false
	trough.add_child(feed)
	return trough

static func _box(node_name: String, size: Vector2, lift: float, colour: Color) -> Polygon2D:
	var box := Polygon2D.new()
	box.name = node_name
	var half := size.x * 0.5
	box.polygon = PackedVector2Array([Vector2(-half, lift - size.y), Vector2(half, lift - size.y), Vector2(half, lift), Vector2(-half, lift)])
	box.color = colour
	return box

func _ready() -> void:
	var found := the_herd()
	if found != null and not found.changed.is_connected(refresh):
		found.changed.connect(refresh)
	refresh()

func the_herd() -> RpgAnimalHouse:
	if herd == null or not is_instance_valid(herd):
		herd = RpgAnimalHouse.current()
	return herd

func is_full() -> bool:
	return RpgAnimalHouse.trough_full(house)

## Shows the feed while the trough is full.
func refresh() -> void:
	var feed := get_node_or_null("Feed") as CanvasItem
	if feed != null:
		feed.visible = is_full()

## `interact` (RpgInteraction calls this): the held feed goes in.
func interact(_actor: Node = null) -> void:
	var mode := RpgFarmMode.current()
	use_with(mode.hotbar.held_item() if mode != null and mode.hotbar != null else &"")

## What `interact` does while `item_id` is held. True when the trough was filled.
func use_with(item_id: StringName) -> bool:
	var found := the_herd()
	var filled := found != null and found.feed_with(house, item_id)
	refresh()
	return filled
