class_name RpgCombatMode
extends Node
## Base class implemented by archetypes. Boot creates the archetype's combat mode as a child of
## SceneRouter (one per game) and stores it as `SceneRouter.combat`. Shared code calls only these
## methods.

signal encounter_finished(result: RpgEncounterResult)

func start_encounter(_data: RpgEncounterData) -> void:
	push_error("[RPG-COMBAT] start_encounter not implemented")

func is_in_combat() -> bool:
	return false
