class_name RpgItemCommand
extends RpgBattleCommand
## Uses a consumable (`user.chosen_item`) on one ally: heal and mp through RpgInventory.use(), cure
## here (statuses live in the battle).

func _init() -> void:
	id = &"item"
	label = "BATTLE_ITEM"
	targets = TARGET_ONE_ALLY

## True when the user holds at least one consumable that does something.
func can_use(user: RpgBattleActor, battle: RpgBattleController) -> bool:
	return not usable_items(user, battle).is_empty()

## [{item_id, qty}] of the usable consumables the user holds, in inventory order.
func usable_items(user: RpgBattleActor, battle: RpgBattleController) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var inv: RpgInventory = battle.inventory_of(user)
	if inv == null:
		return out
	for slot in inv.slots:
		var slot_id: StringName = slot["item_id"]
		var def := inv.definition(slot_id)
		if def != null and def.category == RpgItemDefinition.Category.CONSUMABLE and def.use_effect != &"":
			out.append({"item_id": slot_id, "qty": RpgUtil.to_int(slot["qty"])})
	return out

func execute(user: RpgBattleActor, targets_list: Array[RpgBattleActor], battle: RpgBattleController) -> Array[Dictionary]:
	var inv: RpgInventory = battle.inventory_of(user)
	var item_id := user.chosen_item
	var target: RpgBattleActor = targets_list[0] if not targets_list.is_empty() else user
	if inv == null or item_id == &"":
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_EFFECT"), user)]
	var def := inv.definition(item_id)
	var item_label := RpgBattleText.item_name(def, item_id)
	if def != null and def.use_effect == &"cure":
		var cured := RpgBattleEffects.cure(target, def.cures)
		if cured.is_empty() or not inv.remove(item_id, 1):
			return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_EFFECT"), target)]
		var out: Array[Dictionary] = [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_ITEM_USE", [user.display_name, item_label, target.display_name]), target)]
		out.append_array(cured)
		return out
	var before_hp := target.stats.hp
	var before_mp := target.stats.mp
	if not inv.use(item_id, target.stats):
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_EFFECT"), target)]
	if def != null and def.use_effect == &"mp":
		var restored := target.stats.mp - before_mp
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_ITEM_MP", [user.display_name, item_label, target.display_name, restored]), target, restored)]
	var healed := target.stats.hp - before_hp
	return [RpgBattleCommand.entry("heal", RpgBattleText.t("BATTLE_ITEM_HEAL", [user.display_name, item_label, target.display_name, healed]), target, healed)]
