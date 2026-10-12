class_name RpgFarmSickle
extends RpgFarmTool
## The sickle cuts a ripe crop (a harvest), a withered one (it is gone) and grass.

func _init() -> void:
	id = &"sickle"
	animation = "sickle"
	acts_on = [RpgField.RIPE, RpgField.WITHERED]
	clears = ["grass"]

func apply(field: RpgField, cell: Vector2i) -> bool:
	match field.state_of(cell):
		RpgField.RIPE:
			return field.harvest(cell)
		RpgField.WITHERED:
			return field.remove_crop(cell)
	return field.clear_obstacle(cell, clears)
