class_name RpgDefendCommand
extends RpgBattleCommand
## Halves the damage the user takes until the start of the next round.

func _init() -> void:
	id = &"defend"
	label = "BATTLE_DEFEND"
	targets = TARGET_SELF
	priority = 10

func execute(user: RpgBattleActor, _targets: Array[RpgBattleActor], _battle: RpgBattleController) -> Array[Dictionary]:
	user.defending = true
	return [RpgBattleCommand.entry("status", RpgBattleText.t("BATTLE_DEFENDS", [user.display_name]), user)]
