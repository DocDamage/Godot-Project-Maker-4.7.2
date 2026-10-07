class_name RpgSkillCommand
extends RpgBattleCommand
## Placeholder: disabled until the project adds skills.

func _init() -> void:
	id = &"skill"
	label = "BATTLE_SKILLS_NONE"
	targets = TARGET_ONE_ENEMY

func can_use(_user: RpgBattleActor, _battle: Variant) -> bool:
	return false
