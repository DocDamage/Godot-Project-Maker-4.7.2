class_name RpgSpouseTable
extends Area2D
## What the spouse leaves on the table of the farmhouse in the morning (T17.26): a small table
## with the thing on it, made by RpgMarriage at run time beside the spouse's place, for as long
## as the thing lies there. It is walked over; `interact` takes the thing (layer 5, the
## interactables). The table is drawn (RpgFestivalThing's), the thing is the icon of its item.

## Asked to be emptied (RpgMarriage does it: it knows the bag and the flags).
signal taken

const NODE_NAME := "SpouseTable"

var item_id: StringName = &""

## Makes the table with `of_item` on it, its foot on the origin. On an isometric map (`diamond`
## is the diamond of its cells) it stands on the middle of its cell and its area is the cell.
static func make(of_item: StringName, tile_px: int, diamond: Vector2i = Vector2i.ZERO) -> RpgSpouseTable:
	var node := RpgSpouseTable.new()
	node.name = NODE_NAME
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
	var picture := Node2D.new()
	picture.name = "Picture"
	if diamond != Vector2i.ZERO:
		picture.position = Vector2(0.0, diamond.y * 0.25)
	node.add_child(picture)
	var unit := float(tile_px) * 0.5  # half the festival's table: one tile wide
	RpgFestivalThing._draw_table(picture, unit)
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(of_item) if state != null else null
	if def != null and def.icon != null:
		var sprite := Sprite2D.new()
		sprite.name = "Thing"
		sprite.texture = def.icon
		sprite.centered = false
		var size := Vector2(def.icon.get_size())
		var fit := minf(1.0, unit * 1.2 / maxf(1.0, maxf(size.x, size.y)))
		sprite.scale = Vector2(fit, fit)
		sprite.position = Vector2(-size.x * fit * 0.5, -unit * 0.9 - size.y * fit)
		picture.add_child(sprite)
	return node

## `interact` takes the thing (RpgInteraction calls this).
func interact(_actor: Node = null) -> void:
	taken.emit()
