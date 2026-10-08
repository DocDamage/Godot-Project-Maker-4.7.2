class_name RpgRunCommand
extends RpgBattleCommand
## Tries to flee. The chance comes from the speed of both sides (RpgBattleMath.escape_chance).

func _init() -> void:
	id = &"run"
	label = "BATTLE_RUN"
	targets = TARGET_SELF

func can_use(_user: RpgBattleActor, battle: RpgBattleController) -> bool:
	return RpgUtil.to_bool(battle.can_escape)

func execute(user: RpgBattleActor, _targets: Array[RpgBattleActor], battle: RpgBattleController) -> Array[Dictionary]:
	if not battle.can_escape:
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_ESCAPE"), user)]
	var chance := RpgBattleMath.escape_chance(_speeds(battle.party), _speeds(battle.enemies))
	if battle.rng.randf() < chance:
		battle.escaped = true
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_ESCAPED"), user)]
	return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_ESCAPE_FAILED"), user)]

static func _speeds(actors: Array[RpgBattleActor]) -> Array:
	var out: Array = []
	for a in actors:
		if a.alive:
			out.append(a.stats.speed)
	return out
