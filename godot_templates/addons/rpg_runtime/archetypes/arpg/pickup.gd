class_name RpgPickup
extends Area2D
## An item lying on the ground. It sits on the interactables layer (5), looks for the player body
## (layer 2) and is collected on contact. A tween makes it bob. Pickups are not saved.

const BOB_PX := 1.5
const BOB_S := 0.5

@export var item_id: StringName = &""
@export var qty: int = 1

var _collected := false

## A ready-made pickup (not yet in the tree). `icon` may be null: a small diamond is used then.
static func create(id: StringName, count: int, icon: Texture2D) -> RpgPickup:
	var pickup := RpgPickup.new()
	pickup.name = "Pickup_%s" % id
	pickup.item_id = id
	pickup.qty = count
	pickup.collision_layer = 0
	pickup.collision_mask = 0
	pickup.set_collision_layer_value(5, true)  # interactables
	pickup.set_collision_mask_value(2, true)  # player
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var circle := CircleShape2D.new()
	circle.radius = 7.0
	shape.shape = circle
	pickup.add_child(shape)
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	sprite.texture = icon if icon != null else placeholder_texture()
	sprite.offset = Vector2(0, -sprite.texture.get_height() * 0.5 - 2.0)
	pickup.add_child(sprite)
	return pickup

static func placeholder_texture() -> Texture2D:
	var img := Image.create(7, 7, false, Image.FORMAT_RGBA8)
	for y in 7:
		for x in 7:
			var d := absi(x - 3) + absi(y - 3)
			if d <= 3:
				img.set_pixel(x, y, Color(0.15, 0.1, 0.0) if d == 3 else Color(1.0, 0.85, 0.2))
	return ImageTexture.create_from_image(img)

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	var sprite := get_node_or_null("Sprite") as Sprite2D
	if sprite != null:
		var tween := create_tween().set_loops()
		tween.tween_property(sprite, "position:y", -BOB_PX, BOB_S).set_trans(Tween.TRANS_SINE)
		tween.tween_property(sprite, "position:y", BOB_PX, BOB_S).set_trans(Tween.TRANS_SINE)

func _on_body_entered(body: Node2D) -> void:
	if body.is_in_group("player"):
		collect()

## Puts the item into the player's inventory and removes the pickup. False (and the pickup stays)
## when nothing fitted.
func collect() -> bool:
	if _collected:
		return false
	var state := RpgUtil.state()
	if state == null:
		return false
	var added: int = state.inventory.add(item_id, qty)
	if added <= 0:
		return false
	_collected = true
	RpgUtil.notify(RpgArpgText.t("ARPG_ITEM_GAINED", [RpgArpgText.item_name(state.items.get(item_id), item_id), added]))
	queue_free()
	return true
