class_name RpgItemPickup
extends RpgSideInteractable
## An item (or a few coins) lying in a room. Touching it puts it into the inventory and removes it
## for good: the flag `<entity_id>.collected` is saved, and RpgPersistent takes a collected
## pickup out of the room when the room is entered again.

@export var item_id: StringName = &""
@export var qty: int = 1
@export var gold: int = 0

var _taken := false

func _ready() -> void:
	body_entered.connect(_on_body_entered)
	var sprite := get_node_or_null("Sprite") as Sprite2D
	if sprite != null and sprite.texture == null:
		sprite.texture = RpgPickup.placeholder_texture()  # the packs have no picture for it

func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		collect()

func _use(_actor: Node) -> void:
	collect()

## Gives the item and the gold once. False (and the pickup stays) when the bag is full.
func collect() -> bool:
	if _taken:
		return false
	var state := RpgUtil.state()
	if state == null:
		return false
	if item_id != &"":
		var added: int = state.inventory.add(item_id, qty)
		if added <= 0:
			return false
		var def: RpgItemDefinition = state.items.get(item_id)
		RpgUtil.notify(RpgMetroidvaniaStrings.t("MV_ITEM_GAINED", [RpgRealtimeText.item_name(def, item_id), added]))
	if gold > 0:
		state.gold = RpgUtil.to_int(state.gold) + gold
		RpgUtil.notify(RpgMetroidvaniaStrings.t("MV_GOLD_GAINED", [gold]))
	_taken = true
	if entity_id != "":
		state.set_flag(entity_id, "collected", true)
	queue_free()
	return true
