class_name RpgFarmRod
extends RpgFarmTool
## The fishing rod (T17.10) is cast at water: `use` with it held, facing a cell whose tile says
## `water` (what fills the can). The cast costs its energy; the rest is RpgFishing's (the wait,
## the bite, the bar). A well is water too, and has no fish: the cast is not made and costs
## nothing. Its item is `fishing_rod`, bought at the shop of a farm that has a pond.

## The fishing of the game (the mode gives it; a rod without one casts nothing).
var fishing: RpgFishing = null

func _init() -> void:
	id = &"fishing_rod"
	animation = "rod"
	energy_cost = 3

func can_use(field: RpgField, cell: Vector2i) -> bool:
	return field != null and field.is_water(cell) and fishing != null and is_instance_valid(fishing) and not fishing.is_busy()

func apply(field: RpgField, cell: Vector2i) -> bool:
	return fishing != null and is_instance_valid(fishing) and fishing.cast(field, cell)
