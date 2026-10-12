class_name RpgWaterSource
extends StaticBody2D
## Water the can is filled at (T17.06): the pond of a farm, or its well. `interact` beside it
## fills the watering can; so does `use` with the can held, which asks the field for the tile
## ahead (the map recipe writes the bool custom data `water` into the cells this body covers).
## Filling costs no energy. Layers: world (1) + interactables (5).

## What it is: `pond` or `well` (the plan's `water.kind`; the game does not read it).
@export var kind: String = "pond"

## True when the bag holds a watering can.
static func has_can() -> bool:
	var state := RpgUtil.state()
	return state != null and state.inventory.has(&"watering_can")

## Fills the can. False, with a line that says why, when the farmer has none or it is full.
func fill_can() -> bool:
	if not has_can():
		return false
	if RpgFarmWateringCan.charges() >= RpgFarmWateringCan.SIZE:
		RpgUtil.notify(RpgFarmStrings.t("FARM_CAN_FULL"))
		return false
	RpgFarmWateringCan.fill()
	RpgUtil.notify(RpgFarmStrings.t("FARM_CAN_FILLED"))
	return true

## `interact` (RpgInteraction calls this).
func interact(_actor: Node = null) -> void:
	fill_can()
