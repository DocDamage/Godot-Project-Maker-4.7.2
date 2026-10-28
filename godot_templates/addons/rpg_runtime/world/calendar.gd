class_name RpgCalendar
extends Node
## The time of a game that has days (T17.03): the minute of the day, the day of the season, the
## season and the year. One clock for the light, for what grows, for when a shop is open and for
## where a person is.
##
## It is not an autoload and no game has one unless its mode asks for it: `RpgCalendar.ensure()`
## makes it a child of GameState (the mode calls it in its `_ready`), and everybody else finds it
## with `RpgCalendar.current()`, which is null in a game without days. Such a game is what it was:
## its light keeps the clock of T12.62 and its saves have no `calendar` key.
##
## A day runs from 6:00 to 2:00 of the night. `minute` is counted from the midnight before the
## morning, so 6:00 is 360, midnight 1440 and 2:00 of the night 1560; `clock()` gives the hour
## and the minute a clock shows. A game minute is `minute_s` real seconds. Time stands still
## while the game is paused (every menu pauses it), in a dialogue, in a cutscene, in a battle,
## while the map changes and when no map is shown, and indoors when `stops_indoors` is on.
##
## The end of a day, by `end_day()` (sleeping) or by the clock at 2:00, always goes this way:
##   1. the night listeners of `on_night`, the lowest priority first (NIGHT_CROPS, NIGHT_ANIMALS,
##      NIGHT_SHOP, NIGHT_WEATHER), two of the same priority in the order they were added;
##   2. the signal `day_ended` with the day that ended, for whoever does not care about the order;
##   3. the date moves on and the minute is 6:00;
##   4. `season_changed`, when the day was the last of its season;
##   5. `day_began` with the new day.
## A night listener is called with the day of the season that ended and reads the calendar for
## the rest: it still shows that day. The arithmetic is the same as `rpggen/core/calendar_math.py`
## (tests/unit/calendar_math_cases.json).

signal minute_passed(minute: int)
## A full hour was reached: `hour` is what a clock shows (0 to 23).
signal hour_passed(hour: int)
signal day_ended(day: int)
signal day_began(day: int)
signal season_changed(season: int)

const NODE_NAME := "Calendar"
## The key of a saved game that holds the calendar.
const SAVE_KEY := "calendar"
const SEASONS: Array[String] = ["spring", "summer", "autumn", "winter"]
const DAY_START := 360
const DAY_END := 1560
const DAY_MINUTES := 1200
const MINUTE_S := 0.7
const DAYS_PER_SEASON := 28
const SEASON_LENGTHS: Array[int] = [7, 14, 28]
const WEEK_DAYS := 7
## The priorities of what happens overnight, in their order.
const NIGHT_CROPS := 100
const NIGHT_ANIMALS := 200
const NIGHT_SHOP := 300
const NIGHT_WEATHER := 400

## Real seconds a game minute; a day is 1200 of them (14 minutes at 0.7).
@export var minute_s: float = MINUTE_S
## The days of a season: 28, or 14 or 7 for a shorter game (anything else counts as 28).
@export var days_per_season: int = DAYS_PER_SEASON
## True: time stands still while the player is in an interior map.
@export var stops_indoors: bool = false
## True: the day and night light of the outdoor maps follows this calendar, and the player's
## *Day and night* setting is on by default (RpgSettings.day_night_on, T18.06); turned off, the
## light stays full day and the time goes on.
@export var drives_light: bool = true

var minute: int = DAY_START
var day: int = 1
## 0 spring, 1 summer, 2 autumn, 3 winter (`season_name()`).
var season: int = 0
var year: int = 1

var _carry := 0.0  # real seconds that are not a game minute yet
var _night: Array[Dictionary] = []  # [{priority, order, callable}], sorted
var _added := 0
var _ending := false

# ------------------------------------------------------------------ finding it

## The calendar of the running game, or null: most games have none.
static func current() -> RpgCalendar:
	var state := RpgUtil.state()
	return state.get_node_or_null(NODE_NAME) as RpgCalendar if state != null else null

## The calendar of the running game, made when there is none yet (a child of GameState, so it is
## there on every map and is saved with the game). Null without a GameState.
static func ensure() -> RpgCalendar:
	var state := RpgUtil.state()
	if state == null:
		return null
	var found := state.get_node_or_null(NODE_NAME) as RpgCalendar
	if found == null:
		found = RpgCalendar.new()
		found.name = NODE_NAME
		state.add_child(found)
	return found

# ------------------------------------------------------------------ the clock

func _process(delta: float) -> void:
	advance(delta)

## Lets `delta` real seconds pass, unless time stands still.
func advance(delta: float) -> void:
	if delta <= 0.0 or stands_still():
		return
	_carry += delta
	var step := maxf(minute_s, 0.001)
	var whole := int(floorf(_carry / step))
	if whole > 0:
		_carry -= whole * step
		pass_minutes(whole)

## Lets `count` game minutes pass at once, whatever stands still (a tool that takes time, a
## test). A day that reaches 2:00 on the way ends, and the minutes left over are of the next.
func pass_minutes(count: int) -> void:
	for i in maxi(0, count):
		minute += 1
		minute_passed.emit(minute)
		if minute % 60 == 0:
			hour_passed.emit(clock()[0])
		if minute >= DAY_END:
			end_day()

## True while time does not pass (see the top of the file).
func stands_still() -> bool:
	var tree := RpgUtil.tree()
	if tree != null and tree.paused:
		return true
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box != null and box.has_method(&"is_open") and RpgUtil.to_bool(box.call(&"is_open")):
		return true
	var router := RpgUtil.router()
	if router == null:
		return false
	if router.current_map == null or router.is_busy() or RpgSequenceRunner.running():
		return true
	if router.combat != null and router.combat.is_in_combat():
		return true
	return stops_indoors and router.current_map.interior()

## The hour and the minute a clock shows: [hour (0 to 23), minute].
func clock() -> Array[int]:
	return clock_of(minute)

## The hour of the day and night light, 0 to 24.
func hour() -> float:
	return hour_of(minute)

func season_name() -> String:
	return season_name_of(season)

## How many days lie before today since the first day of the first year.
func today() -> int:
	return day_index(day, season, year, days_per_season)

## The day of the week, 0 to 6; the first day of a year is 0.
func weekday() -> int:
	return weekday_of(today())

# ------------------------------------------------------------------ the night

## Has `callable` called at the end of every day, with the day that ended, before the signal
## `day_ended`. The lowest `priority` is called first (NIGHT_CROPS, NIGHT_ANIMALS, NIGHT_SHOP,
## NIGHT_WEATHER, or a number between them); of two with the same, the one added first. A
## listener whose object is gone is left out.
func on_night(priority: int, callable: Callable) -> void:
	off_night(callable)
	_night.append({"priority": priority, "order": _added, "callable": callable})
	_added += 1
	_night.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if RpgUtil.to_int(a["priority"]) != RpgUtil.to_int(b["priority"]):
			return RpgUtil.to_int(a["priority"]) < RpgUtil.to_int(b["priority"])
		return RpgUtil.to_int(a["order"]) < RpgUtil.to_int(b["order"]))

## Takes a night listener away again.
func off_night(callable: Callable) -> void:
	for i in range(_night.size() - 1, -1, -1):
		var entry: Callable = _night[i]["callable"]
		if entry == callable:
			_night.remove_at(i)

## Ends the day: sleeping calls it, and the clock at 2:00. The order of what follows is at the
## top of the file. Called from a night listener it does nothing.
func end_day() -> void:
	if _ending:
		return
	_ending = true
	var ended := day
	for entry: Dictionary in _night.duplicate():
		var listener: Callable = entry["callable"]
		if listener.is_valid():
			listener.call(ended)
		else:
			off_night(listener)
	day_ended.emit(ended)
	var before := season
	var next := date_after(day, season, year, 1, days_per_season)
	day = next[0]
	season = next[1]
	year = next[2]
	minute = DAY_START
	_carry = 0.0
	_ending = false
	if season != before:
		season_changed.emit(season)
	day_began.emit(day)

# ------------------------------------------------------------------ a new game and the save

## The first morning: 6:00 on the first day of spring of the first year. No signal.
func reset() -> void:
	minute = DAY_START
	day = 1
	season = 0
	year = 1
	_carry = 0.0

## What a saved game holds of the calendar.
func to_dict() -> Dictionary:
	return {"minute": minute, "day": day, "season": season, "year": year}

## Takes the `calendar` key of a saved game. A save without it (or with something else there) is
## the first morning; numbers that are no date are the nearest one. No signal: the game that was
## loaded shows its map anew.
func from_dict(raw: Variant) -> void:
	reset()
	if not (raw is Dictionary):
		return
	var data: Dictionary = raw
	var length := season_length(days_per_season)
	minute = clampi(RpgUtil.to_int(data.get("minute", DAY_START), DAY_START), DAY_START, DAY_END - 1)
	day = clampi(RpgUtil.to_int(data.get("day", 1), 1), 1, length)
	season = clampi(RpgUtil.to_int(data.get("season", 0)), 0, SEASONS.size() - 1)
	year = maxi(1, RpgUtil.to_int(data.get("year", 1), 1))

# ------------------------------------------------------------------ the arithmetic (calendar_math.py)

## The length of a season a game may have: 7, 14 or 28 days, 28 for anything else.
static func season_length(length: int) -> int:
	return length if SEASON_LENGTHS.has(length) else DAYS_PER_SEASON

## How many days lie before a date since the first day of the first year.
static func day_index(of_day: int, of_season: int, of_year: int, length: int = DAYS_PER_SEASON) -> int:
	var days := season_length(length)
	var seasons := (maxi(1, of_year) - 1) * SEASONS.size() + clampi(of_season, 0, SEASONS.size() - 1)
	return seasons * days + clampi(of_day, 1, days) - 1

## The date of the day with this index: [day of the season, season, year].
static func date_of(index: int, length: int = DAYS_PER_SEASON) -> Array[int]:
	var days := season_length(length)
	var at := maxi(0, index)
	var seasons := at / days
	return [at % days + 1, seasons % SEASONS.size(), seasons / SEASONS.size() + 1]

## The date `days` days after a date.
static func date_after(of_day: int, of_season: int, of_year: int, days: int, length: int = DAYS_PER_SEASON) -> Array[int]:
	return date_of(day_index(of_day, of_season, of_year, length) + days, length)

## The season of the day with this index.
static func season_of(index: int, length: int = DAYS_PER_SEASON) -> int:
	return date_of(index, length)[1]

static func season_name_of(of_season: int) -> String:
	return SEASONS[posmod(of_season, SEASONS.size())]

## The day of the week of the day with this index: 0 for the first day of a year.
static func weekday_of(index: int) -> int:
	return maxi(0, index) % WEEK_DAYS

## The minute of the day `span` game minutes after `of_minute`, and how many days ended on the
## way: [minute, days].
static func add_minutes(of_minute: int, span: int) -> Array[int]:
	var passed := clampi(of_minute, DAY_START, DAY_END - 1) - DAY_START + maxi(0, span)
	return [DAY_START + passed % DAY_MINUTES, passed / DAY_MINUTES]

## The time a clock shows at a minute of the day: [hour (0 to 23), minute].
static func clock_of(of_minute: int) -> Array[int]:
	return [of_minute / 60 % 24, of_minute % 60]

## The hour of the day and night light (0 to 24) at a minute of the day.
static func hour_of(of_minute: int) -> float:
	return (of_minute % 1440) / 60.0

## How long a whole day is in real seconds.
static func day_seconds(of_minute_s: float = MINUTE_S) -> float:
	return DAY_MINUTES * of_minute_s
