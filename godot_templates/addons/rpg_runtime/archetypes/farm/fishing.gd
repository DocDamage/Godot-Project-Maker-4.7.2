class_name RpgFishing
extends Node
## Fishing on a farm (T17.10). A child of the farm's mode (`Fishing`), made by it like the
## weather and the end of the day. The rod (RpgFarmRod) casts; this is the rest.
##
## * **The cast** (`cast`, what `use` with the rod at a water cell does): at a pond the line
##   is out (WAITING) and the farmer stands still; at a well a toast says that nothing lives
##   there and nothing else happens. A cast passes CAST_MINUTES of the calendar at once.
## * **The wait** is 1 to 4 seconds of the running game (`wait_of`: it follows from the seed of
##   the game and the number of the cast, which is kept in the flags, `farm_fishing.casts`). It
##   does not pass while the game is paused. `use` again while waiting pulls the line in.
## * **The bite** (BITE): the float dips, a mark shows over the farmer and the sound
##   `sfx_bite` plays when the game has it; BITE_S later the bar opens by itself.
## * **The bar** (REELING, RpgFishingBar shows it): the fish's `mark` moves along the bar
##   (0 to 1) and the `zone` (ZONE wide) rises while `use` is held and sinks when it is let go.
##   While the mark is inside the zone the `meter` fills, outside it drains: full, the fish is
##   caught (its item goes into the inventory); empty, it got away. Either passes REEL_MINUTES.
## * **Which fish** (`fish_for`): one of the fish of the table (RpgForage holds it) that bite in
##   the season, at the time of day (`time_of`: morning before 12:00, day before 18:00, then
##   evening) and in the water (`pond`), chosen by the seed and the number of the cast. When
##   none does, the wait ends with nothing.
## * `advance(delta)` is the clock of all this (`_physics_process` calls it; a test calls it
##   itself) and `button` what it asks for the `use` button (a test scripts it).

signal cast_out(cell: Vector2i)
signal bit(fish_id: String)
signal caught(item_id: StringName)
## The cast ended without a fish: `why` is PULLED, NOTHING, AWAY, FULL or ENDED.
signal lost(why: String)

const NODE_NAME := "Fishing"
const IDLE := 0
const WAITING := 1
const BITE := 2
const REELING := 3
const POND := "pond"
const WELL := "well"
const TIMES: Array[String] = ["morning", "day", "evening"]
const WAIT_MIN := 1.0
const WAIT_MAX := 4.0
const BITE_S := 0.6
const CAST_MINUTES := 10
const REEL_MINUTES := 20
## The bar: the width of the zone, how fast it moves, how fast a fish of speed 1 moves (all in
## lengths of the bar a second), where the meter starts and how fast it fills and drains.
const ZONE := 0.3
const ZONE_SPEED := 0.9
const MARK_SPEED := 0.45
const METER_START := 0.35
const FILL := 0.4
const DRAIN := 0.25
const PULLED := "pulled"
const NOTHING := "nothing"
const AWAY := "away"
const FULL := "full"
const ENDED := "ended"
const FLAG_ENTITY := "farm_fishing"
const CASTS_KEY := "casts"
const CAST_SOUND := &"sfx_water"
const BITE_SOUND := &"sfx_bite"
const CATCH_SOUND := &"sfx_harvest"
## Over the farm's HUD (5), under the summary (55) and the menus.
const BAR_LAYER := 6
const BAR_NODE := "FishingLayer"

var state := IDLE
## Where the fish is on the bar, where the middle of the zone is, and how full the meter is.
var mark := 0.5
var zone := 0.5
var meter := METER_START
## The fish on the line ("" before the bite of a cast that has none), and the water cell.
var fish_id := ""
var cell := Vector2i.ZERO
## What `advance` asks for the `use` button: `func() -> bool`. The real action when not set.
var button: Callable = Callable()
## The farmer, when the map cannot be asked (a test sets it).
var farmer: RpgFarmer = null

var _wait := 0.0
var _bite := 0.0
var _target := 0.5
var _steps := 0
var _speed := 1.0
var _armed := false  # the button that cast was let go: the next press pulls the line in
var _swallow := false  # the press that pulled the line in is still held: it casts nothing
var _tile := 16  # the size of a cell of the map the line is cast on
var _layer: CanvasLayer = null
var _bar: RpgFishingBar = null
var _float: Polygon2D = null

## The fishing of the running game, or null in a game that is no farm.
static func current() -> RpgFishing:
	var mode := RpgFarmMode.current()
	return mode.fishing if mode != null else null

## Listens to the calendar, to the maps and to the saves: a new day, another map and a loaded
## game end a cast. The mode calls it once the calendar exists.
func attach() -> void:
	var calendar := RpgCalendar.current()
	if calendar != null and not calendar.day_began.is_connected(_on_day):
		calendar.day_began.connect(_on_day)
	var bus := RpgUtil.events()
	if bus != null:
		if not bus.map_entered.is_connected(_on_map):
			bus.map_entered.connect(_on_map)
		if not bus.game_loaded.is_connected(_on_day):
			bus.game_loaded.connect(_on_day)

func _on_day(_what: int) -> void:
	cancel()

func _on_map(_id: StringName) -> void:
	cancel()

## True while a cast is running, and until the press that pulled a line in is let go.
func is_busy() -> bool:
	return state != IDLE or _swallow

# ------------------------------------------------------------------ what follows from the seed

## The time of day of a minute of the calendar (RpgCalendar.minute: 6:00 is 360).
static func time_of(minute: int) -> String:
	if minute < 12 * 60:
		return TIMES[0]
	return TIMES[1] if minute < 18 * 60 else TIMES[2]

## True when a fish of the table bites in this season, at this time of day, in this water. An
## entry that names no season, no time or no water bites in all.
static func bites(entry: Dictionary, season_name: String, time: String, water: String) -> bool:
	var times := RpgUtil.to_array(entry.get("times", []))
	var waters := RpgUtil.to_array(entry.get("water", []))
	return RpgForage.in_season(entry, season_name) and (times.is_empty() or times.has(time)) and (waters.is_empty() or waters.has(water))

## The ids of the fish that bite, in the order of the table.
static func fish_of(entries: Array, season_name: String, time: String, water: String) -> Array[String]:
	var out: Array[String] = []
	for raw: Variant in entries:
		var entry := RpgUtil.to_dict(raw)
		if bites(entry, season_name, time, water):
			out.append(RpgUtil.to_str(entry.get("id", "")))
	return out

## The fish of cast number `cast_no` of a game with this seed, or "" when none bites.
static func fish_for(entries: Array, season_name: String, time: String, water: String, game_seed: int, cast_no: int) -> String:
	var found := fish_of(entries, season_name, time, water)
	return found[RpgForage.roll(game_seed, cast_no, 0, 5) % found.size()] if not found.is_empty() else ""

## How many seconds cast number `cast_no` waits for its bite: WAIT_MIN to WAIT_MAX.
static func wait_of(game_seed: int, cast_no: int) -> float:
	return lerpf(WAIT_MIN, WAIT_MAX, RpgForage.roll(game_seed, cast_no, 0, 6) / 99.0)

## What the water at `water_cell` of a field's map is: the `kind` of the map's RpgWaterSource
## (`pond` or `well`), a pond when the map has water tiles and no such body.
static func water_kind(field: RpgField, _water_cell: Vector2i) -> String:
	var map := field.get_parent() if field != null else null
	if map != null:
		for body in map.find_children("*", "StaticBody2D", true, false):
			if body is RpgWaterSource:
				var source: RpgWaterSource = body
				return source.kind
	return POND

func _forage() -> RpgForage:
	var mode := get_parent() as RpgFarmMode
	return mode.forage if mode != null else RpgForage.current()

func _game_seed() -> int:
	var found := _forage()
	return found.game_seed() if found != null else 0

## How many casts this game has seen.
func casts() -> int:
	var game := RpgUtil.state()
	return maxi(0, RpgUtil.to_int(game.get_flag(FLAG_ENTITY, CASTS_KEY, 0))) if game != null else 0

# ------------------------------------------------------------------ the cast

## Casts the line at a water cell of `field`. False, and nothing is out, when a cast is
## running or the water is a well (a toast says so).
func cast(field: RpgField, water_cell: Vector2i) -> bool:
	if state != IDLE or field == null:
		return false
	var water := water_kind(field, water_cell)
	if water != POND:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_WELL"))
		return false
	var game := RpgUtil.state()
	var number := casts() + 1
	if game != null:
		game.set_flag(FLAG_ENTITY, CASTS_KEY, number)
	var calendar := RpgCalendar.current()
	var found := _forage()
	var seed_now := _game_seed()
	if found != null:
		found.table()
	var entries: Array = found.fish if found != null else []
	var season := calendar.season_name() if calendar != null else RpgCalendar.SEASONS[0]
	var time := time_of(calendar.minute if calendar != null else RpgCalendar.DAY_START)
	fish_id = fish_for(entries, season, time, water, seed_now, number)
	_speed = clampf(RpgUtil.to_float(found.fish_entry(fish_id).get("speed", 1.0), 1.0), 0.25, 4.0) if found != null and fish_id != "" else 1.0
	_wait = wait_of(seed_now, number)
	_steps = number * 1000
	_armed = false
	cell = water_cell
	_tile = field.tile_px
	state = WAITING
	_hold_farmer(field, true)
	_show_float(field, true)
	RpgMenuUtil.play_ui(CAST_SOUND)
	cast_out.emit(water_cell)
	if calendar != null:
		calendar.pass_minutes(CAST_MINUTES)  # a day that ends on the way ends the cast
	return true

## Ends a cast that is running, without a fish and without a word (a new day, another map).
func cancel() -> void:
	if state != IDLE:
		_end(ENDED)

func _physics_process(delta: float) -> void:
	if state != IDLE or _swallow:
		advance(delta)

func _held() -> bool:
	if button.is_valid():
		return button.call() == true
	return InputMap.has_action(&"use") and Input.is_action_pressed(&"use")

## Lets `delta` seconds of a cast pass.
func advance(delta: float) -> void:
	if delta <= 0.0:
		return
	var held := _held()
	if state == IDLE:
		_swallow = _swallow and held
		return
	match state:
		WAITING:
			if not held:
				_armed = true
			elif _armed:
				RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_PULLED"))
				_end(PULLED)
				_swallow = true
				return
			_wait -= delta
			if _wait <= 0.0:
				_on_wait_over()
		BITE:
			_bite -= delta
			if _bite <= 0.0:
				_open_bar()
		REELING:
			_reel(delta, held)

func _on_wait_over() -> void:
	if fish_id == "":
		RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_NOTHING"))
		_end(NOTHING)
		return
	state = BITE
	_bite = BITE_S
	if _float != null:
		_float.position.y += 2.0
	RpgMenuUtil.play_ui(BITE_SOUND)
	_show_bar()
	bit.emit(fish_id)

func _open_bar() -> void:
	state = REELING
	mark = 0.5
	zone = 0.5
	meter = METER_START
	_target = _next_target()
	_show_bar()

func _next_target() -> float:
	_steps += 1
	return RpgForage.roll(_game_seed(), _steps, 0, 7) / 99.0

func _reel(delta: float, held: bool) -> void:
	var half := ZONE * 0.5
	zone = clampf(zone + (ZONE_SPEED if held else -ZONE_SPEED) * delta, half, 1.0 - half)
	var step := MARK_SPEED * _speed * delta
	if absf(_target - mark) <= step:
		mark = _target
		_target = _next_target()
	else:
		mark += step * signf(_target - mark)
	meter = clampf(meter + (FILL if is_on_mark() else -DRAIN) * delta, 0.0, 1.0)
	if meter >= 1.0:
		_land()
	elif meter <= 0.0:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_AWAY"))
		_pass_reel()
		_end(AWAY)

## True while the zone is over the fish's mark.
func is_on_mark() -> bool:
	return absf(mark - zone) <= ZONE * 0.5

func _pass_reel() -> void:
	var calendar := RpgCalendar.current()
	if calendar != null:
		state = IDLE  # a day that ends on the way finds no cast to end
		calendar.pass_minutes(REEL_MINUTES)

func _land() -> void:
	var found := _forage()
	var entry := found.fish_entry(fish_id) if found != null else {}
	var item := StringName(RpgUtil.to_str(entry.get("item", "")))
	var game := RpgUtil.state()
	if game == null or item == &"" or game.inventory.room_for(item) < 1:
		RpgUtil.notify(RpgFarmStrings.t("FARM_FULL"))
		_pass_reel()
		_end(FULL)
		return
	game.inventory.add(item, 1)
	RpgMenuUtil.play_ui(CATCH_SOUND)
	RpgUtil.notify(RpgFarmStrings.t("FARM_FISH_CAUGHT", [RpgFarmStrings.item_name(item)]))
	_pass_reel()
	_end("")
	caught.emit(item)

func _end(why: String) -> void:
	state = IDLE
	fish_id = ""
	_hold_farmer(null, false)
	_show_float(null, false)
	_show_bar()
	if why != "":
		lost.emit(why)

# ------------------------------------------------------------------ what is seen

func _the_farmer(field: RpgField) -> RpgFarmer:
	if farmer != null and is_instance_valid(farmer):
		return farmer
	var tree := field.get_tree() if field != null and field.is_inside_tree() else RpgUtil.tree()
	return tree.get_first_node_in_group("player") as RpgFarmer if tree != null else null

## The farmer stands still while the line is out.
func _hold_farmer(field: RpgField, on: bool) -> void:
	var who := _the_farmer(field)
	if who == null:
		return
	who.fishing = on
	who.move_locked = on or who.is_busy()
	if on:
		who.move_dir(Vector2.ZERO)

## The float on the water.
func _show_float(field: RpgField, on: bool) -> void:
	if not on:
		if _float != null:
			_float.visible = false
		return
	if _float == null:
		_float = Polygon2D.new()
		_float.name = "Float"
		_float.polygon = PackedVector2Array([Vector2(-1.5, -3.0), Vector2(1.5, -3.0), Vector2(1.5, 1.0), Vector2(-1.5, 1.0)])
		_float.color = Color(0.9, 0.25, 0.2)
		_float.z_index = 20
		add_child(_float)
	_float.position = field.cell_center(cell)
	_float.visible = true

## The bar, or null before the first bite.
func bar() -> RpgFishingBar:
	return _bar if _bar != null and is_instance_valid(_bar) else null

## Shows the bar from the bite to the end of the cast.
func _show_bar() -> void:
	var wanted := state == BITE or state == REELING
	if not wanted and _layer == null:
		return
	if _layer == null:
		_layer = CanvasLayer.new()
		_layer.name = BAR_NODE
		_layer.layer = BAR_LAYER
		add_child(_layer)
		_bar = RpgFishingBar.new()
		_bar.name = "Bar"
		_bar.fishing = self
		_layer.add_child(_bar)
	_layer.visible = wanted
	_bar.visible = wanted
	_bar.follow(_the_farmer(null))
	_bar.lift = _tile * 1.5 + 4.0
	_bar.queue_redraw()
