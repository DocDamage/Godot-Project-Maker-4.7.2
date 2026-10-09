class_name RpgMetroidvaniaMode
extends RpgCombatMode
## The metroidvania archetype's combat mode, SceneRouter.combat. The fighting happens in the rooms
## themselves (the real-time set of combat/realtime/), so there are no encounters and
## is_in_combat() is always false. The mode owns what the shared code asks an archetype for: the
## defeat policy and the rules of saving.

func is_in_combat() -> bool:
	return false

func start_encounter(_data: RpgEncounterData) -> void:
	push_warning("[RPG-COMBAT] the metroidvania has no encounters; enemies fight in the rooms")

## The player was defeated: the shared policy (the game-over screen, or at once the newest save
## or the start of the room in a smoke test).
func apply_defeat() -> void:
	await RpgDefeatPolicy.show_game_over()
