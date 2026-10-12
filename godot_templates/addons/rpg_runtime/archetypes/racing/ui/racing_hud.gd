class_name RpgRacingHud
extends RpgArcadeHud
## The HUD of a racing game: the arcade HUD without the lives (a car has none), with the lap,
## the place, the speed of the car, its boosts and what it carries, a map of the track with
## every car on it, and a sign in the middle of the screen for the countdown, the start, the
## wrong way and the finish.

## The speed shown is tiles a second times this (a number that reads like one of a car).
const SPEED_SCALE := 15.0
const SIGN_SIZE := 32
const SIGN_COLOR := Color(1, 1, 1)
const WARNING_COLOR := Color(1.0, 0.3, 0.25)

## The map of the track in the corner (the recipe turns it on).
@export var track_map: bool = true

var _sign: Label = null
var _map: RpgRaceMinimap = null

func _ready() -> void:
	super._ready()
	_sign = Label.new()
	_sign.name = "Sign"
	_sign.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_sign.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_sign.add_theme_font_size_override(&"font_size", SIGN_SIZE)
	_sign.add_theme_color_override(&"font_outline_color", Color.BLACK)
	_sign.add_theme_constant_override(&"outline_size", 6)
	_sign.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_sign.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_sign.offset_top = 56.0
	_sign.visible = false
	add_child(_sign)
	if track_map:
		_map = RpgRaceMinimap.new()
		add_child(_map)
	refresh()

func refresh() -> void:
	super.refresh()
	if _lives != null:
		_lives.visible = false

func _process(_delta: float) -> void:
	show_car(_car())
	var mode := RpgArcadeMode.current()
	var racing: RpgRacingMode = null
	if mode is RpgRacingMode:
		racing = mode as RpgRacingMode
	show_race(racing.current_race() if racing != null else null, _car())
	show_championship(racing.championship if racing != null else null)

func _car() -> RpgCar:
	var mode := RpgArcadeMode.current()
	if mode is RpgRacingMode:
		var found := (mode as RpgRacingMode).car
		return found if found != null and is_instance_valid(found) else null
	return null

## The map of the track, or null when the HUD has none.
func track_minimap() -> RpgRaceMinimap:
	return _map

## What the sign in the middle of the screen says ("" when it is not shown).
func sign_text() -> String:
	return _sign.text if _sign != null and _sign.visible else ""

func _show_sign(text: String, warning: bool = false) -> void:
	_sign.text = text
	_sign.visible = text != ""
	_sign.add_theme_color_override(&"font_color", WARNING_COLOR if warning else SIGN_COLOR)

## Fills the rows of the car from `car` (none takes them away).
func show_car(car: RpgCar) -> void:
	set_row("speed", RpgRacingStrings.t("RACE_SPEED", [roundi(absf(car.speed_tiles()) * SPEED_SCALE)]) if car != null else "")
	set_row("boosts", RpgRacingStrings.t("RACE_BOOSTS", [car.boosts]) if car != null else "")
	var held := ""
	if car != null and car.weapon != "":
		held = RpgRacingStrings.t("RACE_WEAPON", [RpgRacingStrings.t("RACE_ITEM_" + car.weapon.to_upper())])
	set_row("weapon", held)
	set_row("shield", RpgRacingStrings.t("RACE_SHIELD") if car != null and car.shielded else "")

## Fills the rows of the race and the sign (none, or no car in it, takes them away).
func show_race(race: RpgRace, car: RpgCar) -> void:
	if race == null or car == null or not is_instance_valid(race) or race.phase == RpgRace.Phase.IDLE:
		for key: String in ["lap", "place"]:
			set_row(key, "")
		_show_sign("")
		return
	set_row("lap", RpgRacingStrings.t("RACE_LAP", [clampi(race.lap_of(car), 1, race.laps), race.laps]))
	set_row("place", RpgRacingStrings.t("RACE_PLACE", [race.place_of(car), race.cars.size()]))
	if race.phase == RpgRace.Phase.COUNTDOWN:
		_show_sign(RpgRacingStrings.t("RACE_COUNT", [ceili(race.countdown_left())]))
	elif race.is_finished():
		_show_sign(RpgRacingStrings.t("RACE_FINISHED", [race.place_of(car)]))
	elif race.wrong_way:
		_show_sign(RpgRacingStrings.t("RACE_WRONG_WAY"), true)
	elif race.time_s < 1.0:
		_show_sign(RpgRacingStrings.t("RACE_GO"))
	else:
		_show_sign("")

## The rows of the championship: the player's points once a race was driven, and how often it
## came in last when that puts it out.
func show_championship(table: RpgChampionship) -> void:
	var points := ""
	var last := ""
	if table != null and table.races > 0:
		points = RpgRacingStrings.t("RACE_POINTS", [table.points_of(RpgChampionship.PLAYER)])
	if table != null and table.elimination and table.last_count > 0:
		last = RpgRacingStrings.t("RACE_LAST", [table.last_count, RpgChampionship.LAST_LIMIT])
	set_row("points", points)
	set_row("last", last)
