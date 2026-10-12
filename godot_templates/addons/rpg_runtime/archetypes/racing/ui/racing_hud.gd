class_name RpgRacingHud
extends RpgArcadeHud
## The HUD of a racing game: the arcade HUD with the speed of the car, the boosts and the
## weapon it has, and of the race the lap, the place, the countdown and the wrong-way warning.

## The speed shown is tiles a second times this (a number that reads like one of a car).
const SPEED_SCALE := 15.0

func _process(_delta: float) -> void:
	show_car(_car())
	var mode := RpgArcadeMode.current()
	show_race((mode as RpgRacingMode).current_race() if mode is RpgRacingMode else null, _car())

func _car() -> RpgCar:
	var mode := RpgArcadeMode.current()
	if mode is RpgRacingMode:
		var found := (mode as RpgRacingMode).car
		return found if found != null and is_instance_valid(found) else null
	return null

## Fills the rows of the car from `car` (none takes them away).
func show_car(car: RpgCar) -> void:
	set_row("speed", RpgRacingStrings.t("RACE_SPEED", [roundi(absf(car.speed_tiles()) * SPEED_SCALE)]) if car != null else "")
	set_row("boosts", RpgRacingStrings.t("RACE_BOOSTS", [car.boosts]) if car != null else "")
	var held := ""
	if car != null and car.weapon != "":
		held = RpgRacingStrings.t("RACE_WEAPON", [RpgRacingStrings.t("RACE_ITEM_" + car.weapon.to_upper())])
	set_row("weapon", held)
	set_row("shield", RpgRacingStrings.t("RACE_SHIELD") if car != null and car.shielded else "")

## Fills the rows of the race (none, or no car in it, takes them away).
func show_race(race: RpgRace, car: RpgCar) -> void:
	if race == null or car == null or not is_instance_valid(race) or race.phase == RpgRace.Phase.IDLE:
		for key: String in ["lap", "place", "notice"]:
			set_row(key, "")
		return
	set_row("lap", RpgRacingStrings.t("RACE_LAP", [clampi(race.lap_of(car), 1, race.laps), race.laps]))
	set_row("place", RpgRacingStrings.t("RACE_PLACE", [race.place_of(car), race.cars.size()]))
	var notice := ""
	if race.phase == RpgRace.Phase.COUNTDOWN:
		notice = RpgRacingStrings.t("RACE_COUNT", [ceili(race.countdown_left())])
	elif race.is_finished():
		notice = RpgRacingStrings.t("RACE_FINISHED", [race.place_of(car)])
	elif race.wrong_way:
		notice = RpgRacingStrings.t("RACE_WRONG_WAY")
	elif race.time_s < 1.0:
		notice = RpgRacingStrings.t("RACE_GO")
	set_row("notice", notice)
