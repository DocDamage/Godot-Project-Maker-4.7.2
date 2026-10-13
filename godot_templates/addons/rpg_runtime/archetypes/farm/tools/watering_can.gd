class_name RpgFarmWateringCan
extends RpgFarmTool
## The watering can waters tilled soil, with or without a crop on it, and is filled at water.
## It holds SIZE cells' worth; how much is left is kept in the flags of the game state
## (`farm.water`). Filling it costs no energy.

const SIZE := 20
const FLAG_ENTITY := "farm"
const FLAG_KEY := "water"

func _init() -> void:
	id = &"watering_can"
	animation = "water"
	sound = RpgFarmSounds.WATER
	acts_on = [RpgField.SOIL, RpgField.CROP, RpgField.RIPE, RpgField.WITHERED]

## How many cells the can still waters.
static func charges() -> int:
	var state := RpgUtil.state()
	return clampi(RpgUtil.to_int(state.get_flag(FLAG_ENTITY, FLAG_KEY, SIZE), SIZE), 0, SIZE) if state != null else SIZE

static func set_charges(count: int) -> void:
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, FLAG_KEY, clampi(count, 0, SIZE))

static func fill() -> void:
	set_charges(SIZE)

func can_use(field: RpgField, cell: Vector2i) -> bool:
	if field == null:
		return false
	if field.is_water(cell):
		return charges() < SIZE
	return charges() > 0 and field.can_water(cell)

func cost(field: RpgField, cell: Vector2i) -> int:
	return 0 if field != null and field.is_water(cell) else energy_cost

func apply(field: RpgField, cell: Vector2i) -> bool:
	if field.is_water(cell):
		fill()
		return true
	if charges() <= 0 or not field.water(cell):
		return false
	set_charges(charges() - 1)
	return true
