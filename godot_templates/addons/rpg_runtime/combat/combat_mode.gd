class_name RpgCombatMode
extends Node
## Base class implemented by archetypes. Boot creates the archetype's combat mode as a child of
## SceneRouter (one per game) and stores it as `SceneRouter.combat`. Shared code calls only these
## methods.
##
## Turn-based (archetypes/turn_based/): encounters open a battle scene. The action RPG
## (archetypes/arpg/) and the metroidvania (archetypes/metroidvania/) fight on the map with the
## real-time set in combat/realtime/: RpgDamageInfo, RpgHitbox, RpgHurtbox, RpgHealth,
## RpgProjectile, RpgStateMachine, RpgPickup, RpgScreenFeedback and the formulas of RpgRealtimeMath.
## Until 1.2 the set lived in archetypes/arpg/; a script at each old path keeps a preload working
## until 2.0.

signal encounter_finished(result: RpgEncounterResult)

func start_encounter(_data: RpgEncounterData) -> void:
	push_error("[RPG-COMBAT] start_encounter not implemented")

func is_in_combat() -> bool:
	return false
