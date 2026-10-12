class_name RpgFarmWeather
extends Node
## The weather of a farm (T17.11). A child of the farm's mode (`Weather`), made by it like the
## energy and the end of the day; the mode's scene has it with the pictures of the overlay.
##
## * **What it is**: `sun`, `rain`, a `storm` (in summer only) or `snow` (in winter only), one a
##   day. It is not stored: the weather of a day follows from the seed of the game and the
##   number of the day (`weather_of`), so day N of a game is the same every time, whatever the
##   player did, before and after a save. The seed is the one thing that is kept: the flag
##   `farm_weather.seed`, taken from the seed of the game's random numbers the first time it is
##   asked for (a new game clears the flags and draws a new one; the smoke run's is the
##   project's `rpg/seed`). The first day of a game is always fair.
## * **When**: the night listener of the calendar at NIGHT_WEATHER decides the weather of the
##   day that begins; `day_began` puts it in force. A new game and a loaded game take theirs
##   when their map is entered (`sync`).
## * **A wet day** (rain, storm): every tilled cell of every field is watered when the day
##   begins, so it counts for the night that follows; a cell that is tilled later in the day is
##   wet at once, and the night waters once more before the crops grow (NIGHT_BEFORE_CROPS).
##   `RpgSchedule.set_weather("rain")` tells the people; a fair or a snowy day is `""`.
## * **The overlay**: on an outdoor map (`RpgMapRoot.interior()` is false) the picture of the
##   weather falls over the screen, on a CanvasLayer of its own, so it moves with the screen and
##   not with the world (RpgWeatherOverlay). Snow is the packs' own picture when they have one,
##   else drawn flakes.
## * **The light**: `RpgDayNight.weather_tint` is what the outdoor light is multiplied by.
## * `forecast()` is tomorrow's weather (RpgWeatherSign shows it); `is_wet()` and
##   `keeps_animals_in()` are for whoever asks (the animals, T17.07).
## * `force(kind)` and `force_tomorrow(kind)` are the debug hooks: they hold for that one day of
##   the running game and are forgotten by a load and a new game.
## * `enabled` is set by the mode's scene (recipes/farm/hud_recipe.gd). A mode that was made
##   without its scene (a test of another part of the farm) has fair weather every day unless a
##   day is forced, and so has the smoke run (`--rpg-smoke`), whose steps count on dry mornings
##   and force the rain they want to see.

## The weather in force changed (a new day, a load, a new game, `force`).
signal changed(kind: String)

const NODE_NAME := "Weather"
const SUN := "sun"
const RAIN := "rain"
const STORM := "storm"
const SNOW := "snow"
const KINDS: Array[String] = [SUN, RAIN, STORM, SNOW]
## Season -> [[kind, chance in a hundred], ...]; what is left is sun.
const CHANCES := {
	"spring": [[RAIN, 25]],
	"summer": [[RAIN, 12], [STORM, 10]],
	"autumn": [[RAIN, 30]],
	"winter": [[SNOW, 30]],
}
## What the outdoor light is multiplied by.
const TINTS := {
	RAIN: Color(0.78, 0.8, 0.88),
	STORM: Color(0.6, 0.62, 0.74),
	SNOW: Color(0.9, 0.92, 0.97),
}
const FLAG_ENTITY := "farm_weather"
const SEED_KEY := "seed"
## The day (its index, `RpgCalendar.today()`) whose rain has watered the fields already.
const WATERED_KEY := "watered"
## What the schedules of the people are told on a wet day (people_plan writes it).
const SCHEDULE_RAIN := "rain"
## The night of a wet day waters before the crops grow.
const NIGHT_BEFORE_CROPS := RpgCalendar.NIGHT_CROPS - 10
## Over the map, under the farm's HUD (5).
const OVERLAY_LAYER := 2
const OVERLAY_NODE := "WeatherLayer"
## The arithmetic of `roll` stays within 31 bits, so no product leaves the 64 of an int.
const MASK := 0x7FFFFFFF

## False: every day is fair unless it is forced (see the top of the file).
@export var enabled: bool = false
## The picture of the rain: `rain_frames` cells in a row, shown at `rain_fps`, repeated over the
## screen. The recipe sets them (a pack's own, else the drawn farm kit's).
@export var rain_texture: Texture2D = null
@export var rain_frames: int = 3
@export var rain_fps: float = 9.0
## A pack's own picture of a storm; the rain's, twice over, without one.
@export var storm_texture: Texture2D = null
@export var storm_frames: int = 3
@export var storm_fps: float = 12.0
## A pack's own picture of snow; drawn flakes without one.
@export var snow_texture: Texture2D = null
@export var snow_frames: int = 1
@export var snow_fps: float = 4.0

## The weather in force.
var today := SUN

var _decided := ""  # what the night decided for the day that begins
var _forced: Dictionary = {}  # day index -> kind
var _layer: CanvasLayer = null
var _overlay: RpgWeatherOverlay = null
var _field: RpgField = null

# ------------------------------------------------------------------ finding it

## The weather of the running game, or null in a game that is no farm.
static func current() -> RpgFarmWeather:
	var mode := RpgFarmMode.current()
	return mode.weather if mode != null else null

## Listens to the calendar, to the maps and to the saves. The mode calls it once the calendar
## exists; a second call changes nothing.
func attach() -> void:
	if OS.get_cmdline_user_args().has("--rpg-smoke"):
		enabled = false
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.on_night(NIGHT_BEFORE_CROPS, _before_night)
		calendar.on_night(RpgCalendar.NIGHT_WEATHER, _on_night)
		if not calendar.day_began.is_connected(_on_morning):
			calendar.day_began.connect(_on_morning)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.map_entered.is_connected(_on_map):
			bus.map_entered.connect(_on_map)
		if not bus.game_loaded.is_connected(_on_loaded):
			bus.game_loaded.connect(_on_loaded)
	sync()

func _exit_tree() -> void:
	_let_go()

func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		_let_go()

## What the weather set outside itself is as it was: the light and what the schedules go by.
func _let_go() -> void:
	RpgDayNight.weather_tint = RpgDayNight.DAY
	RpgSchedule.set_weather("")

# ------------------------------------------------------------------ the weather of a day

## A number from 0 to 99 that follows from a seed and the index of a day and from nothing else.
static func roll(game_seed: int, index: int) -> int:
	var x := ((game_seed & MASK) * 73856093) & MASK
	x = (x ^ ((maxi(0, index) + 1) * 19349663)) & MASK
	x = ((x ^ (x >> 15)) * 83492791) & MASK
	x = ((x ^ (x >> 13)) * 1274126177) & MASK
	x = x ^ (x >> 16)
	return x % 100

## The weather of the day with this index (`RpgCalendar.today()`: 0 is the first day of the
## first year) in a game with this seed and seasons of `length` days.
static func weather_of(game_seed: int, index: int, length: int = RpgCalendar.DAYS_PER_SEASON) -> String:
	if index <= 0:
		return SUN
	var season := RpgCalendar.season_name_of(RpgCalendar.season_of(index, length))
	var chance := roll(game_seed, index)
	var rows: Array = CHANCES.get(season, [])
	for row: Array in rows:
		chance -= RpgUtil.to_int(row[1])
		if chance < 0:
			return RpgUtil.to_str(row[0])
	return SUN

## True for a kind that waters the fields.
static func wet(kind: String) -> bool:
	return kind == RAIN or kind == STORM

## The seed the weather of this game follows from (see the top of the file).
func game_seed() -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	var kept: Variant = state.get_flag(FLAG_ENTITY, SEED_KEY, null)
	if kept != null:
		return RpgUtil.to_int(kept)
	_forced.clear()  # a game that has no seed yet is a new one
	var drawn := int(state.rng.gen.seed) & MASK
	state.set_flag(FLAG_ENTITY, SEED_KEY, drawn)
	return drawn

## The weather of the day with this index in this game.
func weather_on(index: int) -> String:
	if not enabled and _forced.is_empty():
		return SUN
	var seed_now := game_seed()
	if _forced.has(index):
		return RpgUtil.to_str(_forced[index])
	if not enabled:
		return SUN
	var calendar := RpgCalendar.current()
	return weather_of(seed_now, index, calendar.days_per_season if calendar != null else RpgCalendar.DAYS_PER_SEASON)

## Tomorrow's weather.
func forecast() -> String:
	var calendar := RpgCalendar.current()
	return weather_on(calendar.today() + 1) if calendar != null else SUN

func is_wet() -> bool:
	return wet(today)

## True on a day the animals do not go out (rain, a storm, snow).
func keeps_animals_in() -> bool:
	return today != SUN

## The word for a kind of weather ("Rain").
static func text(kind: String) -> String:
	return RpgFarmStrings.t("FARM_WEATHER_" + kind.to_upper())

## What the sign by the house says.
func forecast_text() -> String:
	return RpgFarmStrings.t("FARM_FORECAST", [text(forecast())])

# ------------------------------------------------------------------ the debug hooks

## Makes today's weather `kind`, at once, with all that follows from it.
func force(kind: String) -> void:
	_force_day(0, kind)
	sync()

## Makes tomorrow's weather `kind`.
func force_tomorrow(kind: String) -> void:
	_force_day(1, kind)

func _force_day(ahead: int, kind: String) -> void:
	var calendar := RpgCalendar.current()
	if calendar == null or not KINDS.has(kind):
		return
	game_seed()  # the forced days of a game that is over are dropped first
	_forced[calendar.today() + ahead] = kind

# ------------------------------------------------------------------ the night and the morning

func _before_night(_day: int) -> void:
	if is_wet():
		water_fields()

func _on_night(_day: int) -> void:
	_decided = forecast()

func _on_morning(_day: int) -> void:
	var decided := _decided
	_decided = ""
	_put(decided if decided != "" else _of_today())

func _on_map(_id: StringName) -> void:
	sync()

func _on_loaded(_slot: int) -> void:
	_forced.clear()
	sync()

func _of_today() -> String:
	var calendar := RpgCalendar.current()
	return weather_on(calendar.today()) if calendar != null else SUN

## Takes the weather of the day the calendar shows and puts it in force: after a new game, a
## load, and whenever a map is entered.
func sync() -> void:
	_put(_of_today())

func _put(kind: String) -> void:
	var before := today
	today = kind if KINDS.has(kind) else SUN
	RpgSchedule.set_weather(SCHEDULE_RAIN if is_wet() else "")
	RpgDayNight.weather_tint = TINTS.get(today, RpgDayNight.DAY)
	if is_wet():
		_rain_once()
	watch_field(RpgField.current())
	var router := RpgUtil.router()
	var map := router.current_map if router != null else null
	if map != null:
		map.update_ambient()
	refresh_overlay(map)
	if today != before:
		changed.emit(today)

# ------------------------------------------------------------------ the rain on the fields

## The rain of a wet day waters the fields once: the day is remembered in the flags, so a game
## that is loaded on that day is not watered again (what was tilled since stays as it was).
func _rain_once() -> void:
	var state := RpgUtil.state()
	var calendar := RpgCalendar.current()
	if state == null or calendar == null:
		return
	var index := calendar.today()
	if RpgUtil.to_int(state.get_flag(FLAG_ENTITY, WATERED_KEY, -1), -1) == index:
		return
	state.set_flag(FLAG_ENTITY, WATERED_KEY, index)
	water_fields()

## Waters every tilled cell of every field of the game, shown or not. Returns how many cells
## were dry.
static func water_fields() -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	var count := 0
	var fields := RpgUtil.to_dict(state.flags.get(RpgField.FLAG_ENTITY, {}))
	for id: Variant in fields.keys():
		var saved := RpgUtil.to_dict(fields[id])
		for key: Variant in saved.keys():
			var entry := RpgUtil.to_dict(saved[key])
			if not RpgUtil.to_bool(entry.get("w", false)):
				entry["w"] = true
				saved[key] = entry
				count += 1
		state.set_flag(RpgField.FLAG_ENTITY, RpgUtil.to_str(id), saved)
	var shown := RpgField.current()
	if shown != null:
		shown.load_state()
		shown.refresh()
	return count

## A cell of `field` that is tilled or planted in the rain is wet at once from now on (the field
## of the map that is shown is watched by itself).
func watch_field(field: RpgField) -> void:
	if field == _field:
		return
	if _field != null and is_instance_valid(_field) and _field.changed.is_connected(_on_cell):
		_field.changed.disconnect(_on_cell)
	_field = field
	if _field != null:
		_field.changed.connect(_on_cell)

func _on_cell(cell: Vector2i) -> void:
	if is_wet() and _field != null and _field.can_water(cell):
		_field.water(cell)

# ------------------------------------------------------------------ the overlay

## True when the weather in force is seen on `map`: something falls and the map is outdoors.
func shows_on(map: Node) -> bool:
	if today == SUN or map == null:
		return false
	var root := map as RpgMapRoot
	return root == null or not root.interior()

## The overlay, or null before the first wet day.
func overlay() -> RpgWeatherOverlay:
	return _overlay if _overlay != null and is_instance_valid(_overlay) else null

## True while the overlay is shown.
func overlay_visible() -> bool:
	return overlay() != null and _layer.visible

## Shows or hides the overlay for `map` (the map that is shown when null).
func refresh_overlay(map: Node = null) -> void:
	if map == null:
		var router := RpgUtil.router()
		map = router.current_map if router != null else null
	var wanted := shows_on(map)
	if not wanted and _layer == null:
		return
	if _layer == null:
		_layer = CanvasLayer.new()
		_layer.name = OVERLAY_NODE
		_layer.layer = OVERLAY_LAYER
		add_child(_layer)
		_overlay = RpgWeatherOverlay.new()
		_overlay.name = "Fall"
		_layer.add_child(_overlay)
	_layer.visible = wanted
	if not wanted:
		_overlay.stop()
		return
	match today:
		STORM:
			if storm_texture != null:
				_overlay.fall(storm_texture, storm_frames, storm_fps, 1)
			else:
				_overlay.fall(rain_texture, rain_frames, rain_fps * 1.3, 2)
		SNOW:
			if snow_texture != null:
				_overlay.fall(snow_texture, snow_frames, snow_fps, 1)
			else:
				_overlay.flakes()
		_:
			_overlay.fall(rain_texture, rain_frames, rain_fps, 1)
