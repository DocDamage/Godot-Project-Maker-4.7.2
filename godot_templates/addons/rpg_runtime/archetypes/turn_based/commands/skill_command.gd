class_name RpgSkillCommand
extends RpgBattleCommand
## Uses a skill (`user.chosen_skill`, a game/data/skills id): pays its MP, then RpgBattleEffects
## does the rest. The skill decides whom it aims at (RpgSkillDefinition.targets). Silence blocks it.

func _init() -> void:
	id = &"skill"
	label = "BATTLE_SKILL"
	targets = TARGET_ONE_ENEMY

## True when the user knows a skill it can pay for and is not silenced.
func can_use(user: RpgBattleActor, battle: RpgBattleController) -> bool:
	return not usable_skills(user, battle).is_empty()

## The skills the user knows and can pay for now (none while silenced).
func usable_skills(user: RpgBattleActor, battle: RpgBattleController) -> Array[RpgSkillDefinition]:
	var out: Array[RpgSkillDefinition] = []
	if not user.can_cast():
		return out
	for skill in battle.skills_of(user):
		if user.can_pay(skill.mp_cost):
			out.append(skill)
	return out

func execute(user: RpgBattleActor, targets_list: Array[RpgBattleActor], battle: RpgBattleController) -> Array[Dictionary]:
	var skill := battle.skill(user.chosen_skill)
	if skill == null:
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_EFFECT"), user)]
	if not user.can_cast():
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_CANNOT_CAST", [user.display_name]), user)]
	if not user.pay_mp(skill.mp_cost):
		return [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_NO_MP", [user.display_name]), user)]
	var out: Array[Dictionary] = [RpgBattleCommand.entry("text", RpgBattleText.t("BATTLE_SKILL_USE", [user.display_name, skill.label()]), user)]
	for target in targets_list:
		out.append_array(RpgBattleEffects.use_skill(user, target, skill, battle))
	return out
