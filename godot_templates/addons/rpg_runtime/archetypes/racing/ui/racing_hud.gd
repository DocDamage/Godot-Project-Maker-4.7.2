class_name RpgRacingHud
extends RpgArcadeHud
## The HUD of a racing game: the arcade HUD with the speed of the car and the boosts it has.

## The speed shown is tiles a second times this (a number that reads like one of a car).
const SPEED_SCALE := 15.0

func _process(_delta: float) -> void:
	show_car(_car())

func _car() -> RpgCar:
	var mode := RpgArcadeMode.current()
	if mode is RpgRacingMode:
		var found := (mode as RpgRacingMode).car
		return found if found != null and is_instance_valid(found) else null
	return null

## Fills the rows from `car` (none takes them away).
func show_car(car: RpgCar) -> void:
	set_row("speed", RpgRacingStrings.t("RACE_SPEED", [roundi(absf(car.speed_tiles()) * SPEED_SCALE)]) if car != null else "")
	set_row("boosts", RpgRacingStrings.t("RACE_BOOSTS", [car.boosts]) if car != null else "")
