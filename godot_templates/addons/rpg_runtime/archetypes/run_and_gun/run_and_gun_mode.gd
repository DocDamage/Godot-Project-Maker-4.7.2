class_name RpgRunAndGunMode
extends RpgArcadeMode
## The combat mode of a run and gun: the arcade run (RpgArcadeMode) with a soldier. A death of
## the soldier costs a life, and the soldier comes back from the top of the screen.

## The soldier of the stage that is played, or null.
var soldier: RpgSoldier = null

func _ready() -> void:
	super._ready()
	life_lost.connect(_on_life_lost)

func bind_stage(next: RpgArcadeStage) -> void:
	soldier = _find_soldier(next)
	if soldier != null and not soldier.destroyed.is_connected(_on_soldier_destroyed):
		soldier.destroyed.connect(_on_soldier_destroyed)
	super.bind_stage(next)

func _find_soldier(inside: Node) -> RpgSoldier:
	for node in inside.find_children("*", "CharacterBody2D", true, false):
		if node is RpgSoldier:
			return node as RpgSoldier
	return null

func _on_soldier_destroyed() -> void:
	await player_died()

func _on_life_lost(_left: int) -> void:
	if soldier != null and is_instance_valid(soldier):
		soldier.respawn()
