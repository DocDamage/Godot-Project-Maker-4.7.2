class_name RpgItemCommand
extends RpgBattleCommand
## Uses a consumable (`user.chosen_item`) on one ally through RpgInventory.use().

func _init() -> void:
	id = &"item"
	label = "BATTLE_ITEM"
	targets = TARGET_ONE_ALLY

## True when the user holds at least one consumable that does something.
func can_use(user: RpgBattleActor, battle: Variant) -> bool:
	return not usable_items(user, battle).is_empty()

## [{item_id, qty}] of the usable consumables the user holds, in inventory order.
func usable_items(user: RpgBattleActor, battle: Variant) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var inv: RpgInventory = battle.inventory_of(user)
	if inv == null:
		return out
	for slot in inv.slots:
		var def := inv.definition(slot["item_id"])
		if def != null and def.category == RpgItemDefinition.Category.CONSUMABLE and def.use_effect != &"":
			out.append({"item_id": slot["item_id"], "qty": int(slot["qty"])})
	return out

func execute(user: RpgBattleActor, targets_list: Array[RpgBattleActor], battle: Variant) -> Array[Dictionary]:
	var inv: RpgInventory = battle.inventory_of(user)
	var item_id := user.chosen_item
	var target: RpgBattleActor = targets_list[0] if not targets_list.is_empty() else user
	if inv == null or item_id == &"":
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_EFFECT"), user)]
	var item_label := RpgBattleText.item_name(inv.definition(item_id), item_id)
	var before := target.stats.hp
	if not inv.use(item_id, target.stats):
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_EFFECT"), target)]
	var healed := target.stats.hp - before
	return [RpgBattleCommand.entry("heal", RpgBattleText.t("BATTLE_ITEM_HEAL", [user.display_name, item_label, target.display_name, healed]), target, healed)]
