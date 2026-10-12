class_name RpgFarmHoe
extends RpgFarmTool
## The hoe tills ground (grass or dirt whose tile says `tillable`) into soil.

func _init() -> void:
	id = &"hoe"
	animation = "hoe"
	acts_on = [RpgField.GROUND]

func can_use(field: RpgField, cell: Vector2i) -> bool:
	return field != null and field.can_till(cell)

func apply(field: RpgField, cell: Vector2i) -> bool:
	return field.till(cell)
