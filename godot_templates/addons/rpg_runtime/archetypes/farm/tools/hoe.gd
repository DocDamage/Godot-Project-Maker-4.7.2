class_name RpgFarmHoe
extends RpgFarmTool
## The hoe tills ground (grass or dirt whose tile says `tillable`) into soil, and digs out a crop
## of a kind the game no longer has (T18.09).

func _init() -> void:
	id = &"hoe"
	animation = "hoe"
	sound = RpgFarmSounds.HOE
	acts_on = [RpgField.GROUND]

func can_use(field: RpgField, cell: Vector2i) -> bool:
	return field != null and (field.can_till(cell) or field.is_orphan(cell))

func apply(field: RpgField, cell: Vector2i) -> bool:
	if field.is_orphan(cell):
		return field.remove_crop(cell)
	return field.till(cell)
