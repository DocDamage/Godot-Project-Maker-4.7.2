class_name RpgFarmAxe
extends RpgFarmTool
## The axe clears a stump or a branch, and a rock in a farm that crafts (T18.15: its rocks carry
## the clear mark; elsewhere they do not, and the axe passes them by). Its item is `farm_axe`: `axe` is the weapon the starter
## gear of a pack may be. It strikes with the hoe's sound (`sfx_hoe`): the farm has no slot for
## an axe alone.

func _init() -> void:
	id = &"farm_axe"
	animation = "axe"
	sound = RpgFarmSounds.HOE
	energy_cost = 4
	clears = ["stump", "branch", "rock"]

func apply(field: RpgField, cell: Vector2i) -> bool:
	return field.clear_obstacle(cell, clears)
