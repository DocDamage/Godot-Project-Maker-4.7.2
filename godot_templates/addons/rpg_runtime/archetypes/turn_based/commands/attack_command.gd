class_name RpgAttackCommand
extends RpgBattleCommand

func _init() -> void:
	id = &"attack"
	label = "BATTLE_ATTACK"
	targets = TARGET_ONE_ENEMY

func execute(user: RpgBattleActor, targets_list: Array[RpgBattleActor], battle: Variant) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for target in targets_list:
		if not target.alive:
			continue
		var roll := RpgBattleMath.roll_damage(user.stats.attack, target.stats.defense, target.defending, battle.rng)
		var amount: int = mini(int(roll["amount"]), target.stats.hp)
		target.stats.hp -= amount
		var key := "BATTLE_ATTACK_CRIT" if roll["crit"] else "BATTLE_ATTACK_HIT"
		out.append(RpgBattleCommand.entry("damage", RpgBattleText.t(key, [user.display_name, target.display_name, amount]), target, amount, roll["crit"]))
		if not target.alive:
			out.append(RpgBattleCommand.entry("status", RpgBattleText.t("BATTLE_DEFEATED_NAME", [target.display_name]), target))
		if target.is_player_side:
			RpgUtil.emit(&"player_damaged", [amount])
	return out
