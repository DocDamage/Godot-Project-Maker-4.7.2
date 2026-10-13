class_name RpgForagePickup
extends Area2D
## A thing that lies at one of the farm's forage places this morning (T17.10). RpgForage makes
## it where the map has a place, among the entities of the map so that it Y-sorts with the
## farmer, and takes it away when it is picked up. It is walked over; `interact` picks it up
## (layer 5, the interactables). Its picture is the icon of its item.

## Asked to be picked up (RpgForage does it: it knows the inventory and the day).
signal taken(spot: int)

## The colour of the small square an item without an icon is shown as.
const FALLBACK := Color(0.85, 0.75, 0.3)

## Which place of the map it lies at (0 is `Spot1`), and what it is.
var spot := 0
var item_id: StringName = &""

## Makes the thing of a place: its area, and the icon of `item_id` with its foot on the origin
## (a small square in `fallback` when the item has no icon). On an isometric map (`diamond` is
## the diamond of its cells, T17.14) it lies on the middle of its cell and its area is the cell.
static func make(at_spot: int, of_item: StringName, tile_px: int, fallback: Color = FALLBACK, diamond: Vector2i = Vector2i.ZERO) -> RpgForagePickup:
	var node := RpgForagePickup.new()
	node.name = "Forage%d" % (at_spot + 1)
	node.spot = at_spot
	node.item_id = of_item
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
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(of_item) if state != null else null
	if def != null and def.icon != null:
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = def.icon
		sprite.centered = false
		sprite.position = Vector2(-def.icon.get_width() * 0.5, -def.icon.get_height())
		node.add_child(sprite)
	else:
		var drawn := Polygon2D.new()
		drawn.name = "Sprite"
		var half := tile_px * 0.25
		drawn.polygon = PackedVector2Array([Vector2(-half, -half * 2.0), Vector2(half, -half * 2.0), Vector2(half, 0.0), Vector2(-half, 0.0)])
		drawn.color = fallback
		node.add_child(drawn)
	return node

## `interact` picks it up (RpgInteraction calls this).
func interact(_actor: Node = null) -> void:
	taken.emit(spot)
