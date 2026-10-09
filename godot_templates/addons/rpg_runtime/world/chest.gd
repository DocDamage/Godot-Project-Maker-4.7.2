class_name RpgChest
extends StaticBody2D
## A chest: gives its contents once. Layers: world (1) + interactables (5).
## Visual: 2+ frames in the sprite strip = frame 0 closed, frame 1 open; otherwise the sprite is
## darkened when opened.

@export var entity_id: String = ""
@export var loot: Array[Dictionary] = []  # [{item_id, qty}]
@export var gold: int = 0
@export var display_name: String = "Chest"
## In a side-view room (T14.04): the chest is opened from beside it, from either side, and not
## from a platform above. The recipe also takes it off the world layer there, so it blocks nobody.
@export var side_view: bool = false
@export var tile_size: float = 16.0

var opened := false

func is_opened() -> bool:
	return opened

## Asked by the side-view player before it interacts.
func can_interact(actor: Node) -> bool:
	return not side_view or RpgUtil.beside(self, actor, tile_size)

func interact(_actor: Node = null) -> void:
	if opened:
		return
	var state := RpgUtil.state()
	if state == null:
		push_error("[RPG-WORLD] GameState is not available to open chest %s" % entity_id)
		return
	var found: PackedStringArray = []
	for entry in loot:
		var id := StringName(str(entry.get("item_id", "")))
		var qty := RpgUtil.to_int(entry.get("qty", 1))
		var added: int = state.inventory.add(id, qty)
		if added > 0:
			found.append(_item_text(state, id, added))
	if gold > 0:
		state.gold = RpgUtil.to_int(state.gold) + gold
		found.append("%d %s" % [gold, tr("UI_GOLD")])
	if entity_id != "":
		state.set_flag(entity_id, "opened", true)
	apply_opened_state()
	RpgUtil.emit(&"chest_opened", [entity_id])
	RpgUtil.notify(tr("UI_CHEST_FOUND") % ", ".join(found) if not found.is_empty() else tr("UI_CHEST_EMPTY"))

func _item_text(state: RpgGameState, id: StringName, qty: int) -> String:
	var def: RpgItemDefinition = state.items.get(id)
	var item_name := tr(def.display_name) if def != null and def.display_name != "" else String(id)
	return item_name if qty == 1 else "%s x%d" % [item_name, qty]

## Also called by RpgPersistent when the saved state says the chest was opened.
func apply_opened_state() -> void:
	opened = true
	var sprite := get_node_or_null("Sprite") as Sprite2D
	if sprite == null:
		return
	if sprite.has_meta("open_texture"):
		var open_texture: Texture2D = sprite.get_meta("open_texture")
		sprite.texture = open_texture
	else:
		sprite.modulate = Color(0.55, 0.55, 0.55)
