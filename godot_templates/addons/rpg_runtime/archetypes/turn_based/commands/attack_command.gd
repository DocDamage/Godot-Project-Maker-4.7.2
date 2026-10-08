class_name RpgAttackCommand
extends RpgBattleCommand
## A plain attack: the hit roll, the damage (with the weapon's element) and the status it carries.

func _init() -> void:
	id = &"attack"
	label = "BATTLE_ATTACK"
	targets = TARGET_ONE_ENEMY

func execute(user: RpgBattleActor, targets_list: Array[RpgBattleActor], battle: RpgBattleController) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for target in targets_list:
		if target.alive:
			out.append_array(RpgBattleEffects.attack(user, target, battle))
	return out
