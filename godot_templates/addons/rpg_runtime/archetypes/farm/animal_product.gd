class_name RpgAnimalProduct
extends Area2D
## What an animal left on the floor of its house overnight (T17.07): an egg beside a hen's
## stall. `interact` picks it up (RpgAnimalHouse.take_product: it is the product the animal
## `animal_id` has ready, so it lies there until it is taken, and a full bag leaves it lying).
## RpgAnimalHouse makes it when the room is entered (`make`), with the icon of the item as its
## picture. Layer: interactables (5); it is walked over.

signal picked(item_id: StringName)

@export var item_id: StringName = &""

var animal_id := 0
var herd: RpgAnimalHouse = null

## A product of the animal `id` that lies with its lower edge on the origin.
static func make(id: int, item: StringName, tile: float) -> RpgAnimalProduct:
	var product := RpgAnimalProduct.new()
	product.name = "Product_%d" % id
	product.animal_id = id
	product.item_id = item
	product.collision_layer = 0
	product.collision_mask = 0
	product.set_collision_layer_value(5, true)
	product.monitoring = false
	product.monitorable = true
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile, tile) * 0.7
	shape.shape = rect
	shape.position = Vector2(0.0, -tile * 0.35)
	product.add_child(shape)
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item) if state != null else null
	if def != null and def.icon != null:
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = def.icon
		sprite.centered = false
		sprite.position = Vector2(-def.icon.get_width() * 0.5, -def.icon.get_height())
		product.add_child(sprite)
	else:
		var dot := Polygon2D.new()
		dot.name = "Sprite"
		var r := tile * 0.2
		dot.polygon = PackedVector2Array([Vector2(-r, -r * 2.0), Vector2(r, -r * 2.0), Vector2(r, 0.0), Vector2(-r, 0.0)])
		dot.color = Color(0.96, 0.93, 0.85)
		product.add_child(dot)
	return product

func the_herd() -> RpgAnimalHouse:
	if herd == null or not is_instance_valid(herd):
		herd = RpgAnimalHouse.current()
	return herd

## `interact` (RpgInteraction calls this): the product goes into the bag.
func interact(_actor: Node = null) -> void:
	pick_up()

## Picks it up. False, and it stays, when the bag has no room.
func pick_up() -> bool:
	var found := the_herd()
	var taken := found.take_product(animal_id) if found != null else &""
	if taken == &"":
		return false
	RpgUtil.notify(RpgFarmStrings.t("FARM_ANIMAL_PICKED", [RpgFarmStrings.item_name(taken)]))
	picked.emit(taken)
	if get_parent() != null:
		get_parent().remove_child(self)
	queue_free()
	return true
