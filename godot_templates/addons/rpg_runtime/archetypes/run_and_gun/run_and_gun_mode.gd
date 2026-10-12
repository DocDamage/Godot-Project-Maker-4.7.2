class_name RpgRunAndGunMode
extends RpgArcadeMode
## The combat mode of a run and gun: the arcade run (RpgArcadeMode) with a soldier. A death of
## the soldier costs a life, and the soldier comes back from the top of the screen.

## The soldier of the stage that is played, or null.
var soldier: RpgSoldier = null

func _ready() -> void:
	super._ready()
	life_lost.connect(_on_life_lost)
	continued.connect(_on_continued)

func bind_stage(next: RpgArcadeStage) -> void:
	soldier = _find_soldier(next)
	if soldier != null and not soldier.destroyed.is_connected(_on_soldier_destroyed):
		soldier.destroyed.connect(_on_soldier_destroyed)
	# before the run hears of it: the soldier of the stage is still there to be asked
	next.cleared.connect(_remember_weapon)
	super.bind_stage(next)
	if weapon != "" and soldier != null:
		soldier.equip(weapon)  # the weapon of the run: the stage before, or the saved game

## The soldier's weapon as the run keeps it, so that the next stage, and a saved game that is
## continued, begin with it.
func _remember_weapon() -> void:
	if soldier != null and is_instance_valid(soldier):
		weapon = soldier.weapon()

## Continue after the last life: the stage begins again with the machine gun, as after a death,
## unless the soldier keeps its weapon.
func _on_continued() -> void:
	if soldier == null or not is_instance_valid(soldier) or not soldier.keep_weapon:
		weapon = ""

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
