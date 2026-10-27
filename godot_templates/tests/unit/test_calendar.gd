extends RefCounted
## T17.03: the calendar. Minutes, days, seasons and years, the end of a day and the order of its
## night, what makes time stand still, the light that follows it, and the save.

const Fixtures := preload("../lib/fixtures.gd")

const CASES := "res://tests/unit/calendar_math_cases.json"
const ROUTER := "res://addons/rpg_runtime/world/scene_router.gd"
const STEP := 0.5  # a game minute in the tests: exact in binary, steps add up to whole minutes

## What a dialogue box is to the calendar.
class Box extends Node:
	var open := true

	func is_open() -> bool:
		return open

## A calendar of its own, in no game.
func _calendar(days_per_season: int = RpgCalendar.DAYS_PER_SEASON) -> RpgCalendar:
	var calendar := RpgCalendar.new()
	calendar.minute_s = STEP
	calendar.days_per_season = days_per_season
	return calendar

## A game with a calendar, as a mode makes one.
func _game() -> RpgCalendar:
	Fixtures.install_state()
	var calendar := RpgCalendar.ensure()
	calendar.minute_s = STEP
	return calendar

func _saves() -> RpgSaveManager:
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = "user://test_calendar_saves_%d" % Time.get_ticks_usec()
	return save

func _drop_saves(save: RpgSaveManager) -> void:
	if DirAccess.dir_exists_absolute(save.dir):
		for file: String in DirAccess.get_files_at(save.dir):
			DirAccess.remove_absolute(save.dir.path_join(file))
		DirAccess.remove_absolute(save.dir)
	Fixtures.uninstall("SaveManager")

# ---------------------------------------------------------------- the arithmetic

static func _call(fn: String, a: Array) -> Variant:
	match fn:
		"season_length":
			return RpgCalendar.season_length(a[0])
		"day_index":
			return RpgCalendar.day_index(a[0], a[1], a[2], a[3])
		"date_of":
			return RpgCalendar.date_of(a[0], a[1])
		"date_after":
			return RpgCalendar.date_after(a[0], a[1], a[2], a[3], a[4])
		"season_of":
			return RpgCalendar.season_of(a[0], a[1])
		"season_name":
			return RpgCalendar.season_name_of(a[0])
		"weekday":
			return RpgCalendar.weekday_of(a[0])
		"add_minutes":
			return RpgCalendar.add_minutes(a[0], a[1])
		"clock":
			return RpgCalendar.clock_of(a[0])
		"hour_of":
			return RpgCalendar.hour_of(a[0])
		"day_seconds":
			return RpgCalendar.day_seconds(a[0])
	return null

static func _same(got: Variant, expected: Variant) -> bool:
	if got is Array and expected is Array:
		var mine: Array = got
		var theirs: Array = expected
		if mine.size() != theirs.size():
			return false
		for i in mine.size():
			if int(mine[i]) != int(theirs[i]):
				return false
		return true
	if got is String:
		return got == expected
	if (got is float or got is int) and (expected is float or expected is int):
		return absf(float(got) - float(expected)) <= 0.0001
	return false

func test_the_arithmetic_is_rpggens_over_a_table_of_cases(t) -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(CASES))
	t.ok(parsed is Array, "the table of cases is there")
	if not (parsed is Array):
		return
	var cases: Array = RpgUtil.restore_numbers(parsed)
	t.ok(cases.size() > 300, "%d cases" % cases.size())
	var wrong: Array[String] = []
	var seen := {}
	for raw: Variant in cases:
		var case: Dictionary = raw
		var fn: String = case["fn"]
		seen[fn] = true
		var args: Array = case["args"]
		var got: Variant = _call(fn, args)
		if not _same(got, case["result"]) and wrong.size() < 5:
			wrong.append("%s%s gave %s, rpggen has %s" % [fn, args, got, case["result"]])
	t.eq(wrong, [] as Array[String])
	t.eq(seen.size(), 11, "every function of the arithmetic")

# ---------------------------------------------------------------- the clock

func test_minutes_and_hours_pass(t) -> void:
	var calendar := _calendar()
	var minutes: Array[int] = []
	var hours: Array[int] = []
	calendar.minute_passed.connect(func(minute: int) -> void: minutes.append(minute))
	calendar.hour_passed.connect(func(hour: int) -> void: hours.append(hour))
	t.eq(calendar.clock(), [6, 0] as Array[int], "a day begins at 6:00")
	t.eq([calendar.day, calendar.season, calendar.year], [1, 0, 1])
	calendar.advance(STEP * 0.5)
	t.eq(minutes.size(), 0, "half a minute is no minute")
	calendar.advance(STEP * 0.5)
	t.eq(minutes, [361] as Array[int])
	calendar.advance(STEP * 59)
	t.eq(calendar.clock(), [7, 0] as Array[int])
	t.eq(hours, [7] as Array[int])
	calendar.advance(STEP * 60 * 17)
	t.eq(calendar.clock(), [0, 0] as Array[int], "midnight")
	t.eq(calendar.minute, 1440, "and the minute of the day goes on")
	t.eq(calendar.day, 1, "it is still the day that began in the morning")
	t.eq(hours.slice(-2), [23, 0] as Array[int])
	t.near(calendar.hour(), 0.0)
	calendar.minute_s = 0.7
	calendar.advance(0.7 * 10.5)
	t.eq(calendar.minute, 1450, "0.7 s a minute, the default")
	t.near(RpgCalendar.day_seconds(), 840.0, 0.0001, "a day is 14 minutes")
	calendar.free()

func test_a_day_ends_at_two_and_by_end_day_with_the_night_in_its_order(t) -> void:
	var calendar := _calendar()
	var log: Array[String] = []
	calendar.day_ended.connect(func(day: int) -> void: log.append("ended %d at %d" % [day, calendar.minute]))
	calendar.day_began.connect(func(day: int) -> void: log.append("began %d at %d" % [day, calendar.minute]))
	# added out of their order, and two of one priority
	calendar.on_night(RpgCalendar.NIGHT_WEATHER, func(day: int) -> void: log.append("weather %d" % day))
	calendar.on_night(RpgCalendar.NIGHT_ANIMALS, func(day: int) -> void: log.append("animals %d" % day))
	calendar.on_night(RpgCalendar.NIGHT_SHOP, func(day: int) -> void: log.append("shop %d" % day))
	calendar.on_night(RpgCalendar.NIGHT_CROPS, func(day: int) -> void: log.append("crops %d" % day))
	calendar.on_night(RpgCalendar.NIGHT_CROPS, func(day: int) -> void: log.append("more crops %d" % day))
	calendar.advance(STEP * (RpgCalendar.DAY_MINUTES - 1))
	t.eq(calendar.clock(), [1, 59] as Array[int])
	t.eq(log, [] as Array[String], "a minute before 2:00 the day goes on")
	calendar.advance(STEP)
	t.eq(log, ["crops 1", "more crops 1", "animals 1", "shop 1", "weather 1", "ended 1 at 1560", "began 2 at 360"] as Array[String])
	t.eq(calendar.clock(), [6, 0] as Array[int], "the next morning")
	t.eq(calendar.day, 2)
	# sleeping at noon: the same night
	log.clear()
	calendar.advance(STEP * 360)
	t.eq(calendar.clock(), [12, 0] as Array[int])
	calendar.end_day()
	t.eq(log, ["crops 2", "more crops 2", "animals 2", "shop 2", "weather 2", "ended 2 at 720", "began 3 at 360"] as Array[String])
	t.eq([calendar.minute, calendar.day], [RpgCalendar.DAY_START, 3])
	# a listener is there once, can be taken away, and one whose object is gone is left out
	log.clear()
	var again := func(day: int) -> void: log.append("again %d" % day)
	calendar.on_night(150, again)
	calendar.on_night(50, again)
	var gone := Node.new()
	calendar.on_night(10, gone.queue_free)
	gone.free()
	calendar.end_day()
	t.eq(log.slice(0, 3), ["again 3", "crops 3", "more crops 3"] as Array[String])
	t.eq(log.count("again 3"), 1)
	calendar.off_night(again)
	log.clear()
	calendar.end_day()
	t.eq(log[0], "crops 4")
	# a night that ends the day does not end two
	calendar.on_night(0, func(_day: int) -> void: calendar.end_day())
	calendar.end_day()
	t.eq(calendar.day, 6)
	# a long step is as many days as it holds
	var whole := _calendar()
	var days: Array[int] = []
	whole.day_ended.connect(func(day: int) -> void: days.append(day))
	whole.advance(STEP * RpgCalendar.DAY_MINUTES * 3 + STEP * 30)
	t.eq(days, [1, 2, 3] as Array[int])
	t.eq([whole.day, whole.clock()], [4, [6, 30] as Array[int]])
	calendar.free()
	whole.free()

func test_days_are_a_season_and_four_seasons_a_year(t) -> void:
	var calendar := _calendar()
	var seasons: Array[int] = []
	var began: Array[int] = []
	calendar.season_changed.connect(func(season: int) -> void:
		seasons.append(season)
		t.eq(calendar.day, 1, "a season changes on its first day")
		t.eq(began.size() % 28, 27, "before the day begins"))
	calendar.day_began.connect(func(day: int) -> void: began.append(day))
	for i in 27:
		calendar.end_day()
	t.eq([calendar.day, calendar.season, calendar.year], [28, 0, 1])
	t.eq(seasons, [] as Array[int])
	t.eq(calendar.weekday(), 6)
	calendar.end_day()
	t.eq([calendar.day, calendar.season, calendar.year], [1, 1, 1], "28 days are a season")
	t.eq(calendar.season_name(), "summer")
	t.eq(seasons, [1] as Array[int])
	for i in 28 * 3:
		calendar.end_day()
	t.eq([calendar.day, calendar.season, calendar.year], [1, 0, 2], "four seasons are a year")
	t.eq(seasons, [1, 2, 3, 0] as Array[int])
	t.eq(began.size(), 112)
	t.eq(calendar.today(), 112)
	calendar.free()
	for length: int in [7, 14]:
		var short := _calendar(length)
		for i in length:
			short.end_day()
		t.eq([short.day, short.season, short.year], [1, 1, 1], "a season of %d days" % length)
		for i in length * 3:
			short.end_day()
		t.eq([short.day, short.season, short.year], [1, 0, 2])
		short.free()
	var odd := _calendar(10)
	for i in 10:
		odd.end_day()
	t.eq([odd.day, odd.season], [11, 0], "a length that is not offered counts as 28")
	odd.free()

## The card's Done when: the date going through a year by the clock, minute for minute.
func test_the_clock_goes_through_a_year(t) -> void:
	var calendar := _calendar(7)
	var ended := [0]
	var hours := [0]
	var seasons: Array[String] = []
	calendar.day_ended.connect(func(_day: int) -> void: ended[0] += 1)
	calendar.hour_passed.connect(func(_hour: int) -> void: hours[0] += 1)
	calendar.season_changed.connect(func(_season: int) -> void: seasons.append(calendar.season_name()))
	for day in 28:
		for hour in 20:
			calendar.advance(STEP * 60)
	t.eq(ended[0], 28)
	t.eq(hours[0], 28 * 20)
	t.eq(seasons, ["summer", "autumn", "winter", "spring"] as Array[String])
	t.eq([calendar.day, calendar.season, calendar.year, calendar.minute], [1, 0, 2, RpgCalendar.DAY_START])
	calendar.free()

# ---------------------------------------------------------------- standing still

func test_time_stands_still_in_a_menu_a_dialogue_and_a_cutscene(t) -> void:
	await Fixtures.tree().process_frame  # groups are asked of the tree
	var calendar := _calendar()
	var tree := Fixtures.tree()
	calendar.advance(STEP)
	t.eq(calendar.minute, 361)
	# a menu pauses the tree (RpgUiController), as do the screens of a mode
	tree.paused = true
	t.ok(calendar.stands_still())
	calendar.advance(STEP * 100)
	tree.paused = false
	t.eq(calendar.minute, 361, "no time passes in a menu")
	calendar.advance(STEP)
	t.eq(calendar.minute, 362, "and none is owed afterwards")
	# a dialogue
	var box := Box.new()
	tree.root.add_child(box)
	box.add_to_group(&"rpg_dialogue_box")
	t.ok(calendar.stands_still())
	calendar.advance(STEP * 100)
	t.eq(calendar.minute, 362, "no time passes in a dialogue")
	box.open = false
	calendar.advance(STEP)
	t.eq(calendar.minute, 363)
	tree.root.remove_child(box)
	box.free()
	# with a router: no map (the title screen), a change of map, a cutscene, indoors
	var router := Fixtures.install("SceneRouter", ROUTER) as RpgSceneRouter
	t.ok(calendar.stands_still(), "no map is shown")
	var map := RpgMapRoot.new()
	router.current_map = map
	t.ok(not calendar.stands_still(), "on a map time passes")
	router._busy = true
	t.ok(calendar.stands_still(), "the map changes")
	router._busy = false
	var runner := RpgSequenceRunner.new()
	runner.name = RpgSequenceRunner.NODE_NAME
	router.add_child(runner)
	t.ok(not calendar.stands_still())
	runner._frames = [{"sequence": RpgSequence.new(), "pc": 0}]
	t.ok(calendar.stands_still(), "a cutscene plays")
	calendar.advance(STEP * 100)
	t.eq(calendar.minute, 363)
	runner._frames = []
	map.is_interior = true
	t.ok(not calendar.stands_still(), "indoors time passes")
	calendar.stops_indoors = true
	t.ok(calendar.stands_still(), "unless the option says it does not")
	calendar.advance(STEP * 100)
	t.eq(calendar.minute, 363)
	map.is_interior = false
	calendar.advance(STEP)
	t.eq(calendar.minute, 364)
	# what takes time takes it whatever stands still
	router.current_map = null
	calendar.pass_minutes(10)
	t.eq(calendar.minute, 374)
	map.free()
	Fixtures.uninstall("SceneRouter")
	calendar.free()

# ---------------------------------------------------------------- finding it

func test_a_mode_makes_the_calendar_and_others_find_it(t) -> void:
	Fixtures.uninstall_state()
	t.ok(RpgCalendar.current() == null and RpgCalendar.ensure() == null, "no game: no calendar")
	var state := Fixtures.install_state() as RpgGameState
	t.ok(RpgCalendar.current() == null, "a game has none until a mode asks for one")
	var calendar := RpgCalendar.ensure()
	t.ok(calendar != null and calendar.get_parent() == state)
	t.ok(RpgCalendar.ensure() == calendar and RpgCalendar.current() == calendar, "there is one")
	t.eq(state.get_child_count(), 1)
	calendar.pass_minutes(500)
	calendar.end_day()
	state.new_game()
	t.eq(calendar.to_dict(), {"minute": 360, "day": 1, "season": 0, "year": 1}, "a new game is the first morning")
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the light

func test_the_light_follows_the_calendar(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.clear_day_night_choice()  # the game's default: on with a calendar (T18.06)
	var calendar := _game()
	var state := RpgUtil.state()
	state.playtime_s = 600.0  # the clock of T12.62 says something else
	var outside := RpgMapRoot.new()
	outside._ready()
	var ambient := outside.get_node("Ambient") as CanvasModulate
	t.ok(outside.is_processing(), "with a calendar the outdoor light is kept up to date")
	# through a day, hour by hour
	var colours: Array[Color] = []
	for hour in 20:
		outside.update_ambient()
		colours.append(ambient.color)
		t.eq(ambient.color, RpgDayNight.ambient_at(6.0 + hour), "%d hours after 6:00" % hour)
		calendar.advance(STEP * 60)
	t.eq(calendar.day, 2, "the day is over")
	# full day from six, when a farm's day begins (T17.33); the dawn is the hour before
	t.eq(colours[0], RpgDayNight.DAY, "6:00 is day")
	var dawn := RpgDayNight.ambient_at(5.0)
	t.ok(dawn != RpgDayNight.NIGHT and dawn != RpgDayNight.DAY, "5:00 is dawn")
	t.eq(colours[2], RpgDayNight.DAY, "8:00")
	t.eq(colours[6], RpgDayNight.DAY, "noon")
	t.ok(colours[13] != RpgDayNight.DAY and colours[13] != RpgDayNight.NIGHT, "19:00 is dusk")
	t.eq(colours[15], RpgDayNight.NIGHT, "21:00")
	t.eq(colours[19], RpgDayNight.NIGHT, "1:00 at night")
	t.ok(RpgDayNight.ambient_at(4.0).v < dawn.v and dawn.v < colours[0].v, "the morning gets lighter")
	outside.update_ambient()
	t.eq(ambient.color, colours[0], "the next morning looks like this one")
	t.eq(RpgDayNight.map_ambient(false, true, 600.0), colours[0], "whatever the play time is")
	t.near(RpgDayNight.current_hour(600.0), 6.0)
	# indoors nothing changes; a colour of the map's own stays
	var inside := RpgMapRoot.new()
	inside.is_interior = true
	inside._ready()
	t.eq((inside.get_node("Ambient") as CanvasModulate).color, RpgDayNight.INTERIOR)
	t.ok(not inside.is_processing())
	# a calendar that does not drive the light leaves the older cycle and its setting alone
	calendar.drives_light = false
	outside.update_ambient()
	t.eq(ambient.color, RpgDayNight.DAY)
	t.ok(not outside.is_processing())
	settings.day_night = true
	outside.update_ambient()
	t.eq(ambient.color, RpgDayNight.ambient_at(RpgDayNight.hour_at(600.0)))
	for root: Node in [inside, outside]:
		root.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall("RpgSettings")

func test_a_game_without_a_calendar_has_the_light_of_before(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	var state := Fixtures.install_state() as RpgGameState
	state.playtime_s = 600.0
	t.ok(RpgCalendar.current() == null and RpgDayNight.calendar() == null)
	t.near(RpgDayNight.current_hour(600.0), RpgDayNight.hour_at(600.0))
	t.near(RpgDayNight.hour_at(600.0), 18.0, 0.0001, "ten minutes of play after 8:00, a day in 24")
	t.eq(RpgDayNight.map_ambient(false, true, 600.0), RpgDayNight.ambient_at(18.0))
	t.eq(RpgDayNight.map_ambient(false, false, 600.0), RpgDayNight.DAY)
	settings.day_night = false
	var outside := RpgMapRoot.new()
	outside._ready()
	var ambient := outside.get_node("Ambient") as CanvasModulate
	t.eq(ambient.color, RpgDayNight.DAY)
	t.ok(not outside.is_processing(), "the cycle is off until its setting turns it on")
	settings.day_night = true
	outside.update_ambient()
	t.eq(ambient.color, RpgDayNight.ambient_at(18.0), "and then it runs on the play time")
	t.ok(outside.is_processing())
	outside.free()
	Fixtures.uninstall_state()
	Fixtures.uninstall("RpgSettings")

# ---------------------------------------------------------------- the save

func test_the_calendar_is_saved_and_loaded(t) -> void:
	var calendar := _game()
	var state := RpgUtil.state()
	state.new_game()
	var save := _saves()
	calendar.pass_minutes(555)
	calendar.day = 12
	calendar.season = 2
	calendar.year = 3
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.eq(RpgUtil.restore_numbers(written["calendar"]), {"minute": 915, "day": 12, "season": 2, "year": 3})
	t.eq(RpgUtil.to_int(written["save_version"]), 1, "the save version stays 1")
	calendar.end_day()
	calendar.pass_minutes(7)
	var heard := [0]
	calendar.day_began.connect(func(_day: int) -> void: heard[0] += 1)
	t.ok(save.load(1))
	t.eq(calendar.to_dict(), {"minute": 915, "day": 12, "season": 2, "year": 3})
	t.eq(calendar.clock(), [15, 15] as Array[int])
	t.eq(heard[0], 0, "loading is not a new day")
	# a save from before the calendar: it loads, on the first morning
	var old := state.to_dict()
	old.erase("calendar")
	state.from_dict(old)
	t.eq(calendar.to_dict(), {"minute": 360, "day": 1, "season": 0, "year": 1})
	# what is no date is the nearest one, and what is no calendar the first morning
	calendar.from_dict({"minute": 5000, "day": 40, "season": 7, "year": 0})
	t.eq(calendar.to_dict(), {"minute": 1559, "day": 28, "season": 3, "year": 1})
	calendar.from_dict({"minute": 30.0, "day": "x"})
	t.eq(calendar.to_dict(), {"minute": 360, "day": 1, "season": 0, "year": 1})
	calendar.from_dict("spring")
	t.eq(calendar.to_dict(), {"minute": 360, "day": 1, "season": 0, "year": 1})
	_drop_saves(save)
	Fixtures.uninstall_state()

func test_a_game_without_a_calendar_saves_no_calendar(t) -> void:
	var with := _game()
	with.pass_minutes(100)
	var saved := RpgUtil.state().to_dict()
	t.ok(saved.has("calendar"))
	var state := Fixtures.install_state() as RpgGameState  # another game, without one
	state.new_game()
	var save := _saves()
	t.ok(not state.to_dict().has("calendar"), "no calendar: no key")
	t.ok(save.save(1))
	var written: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(save.dir.path_join("slot_1.json")))
	t.ok(not written.has("calendar"))
	state.gold = 77
	state.from_dict(saved)  # a save that has the key loads in a game that has no calendar
	t.ok(RpgCalendar.current() == null)
	t.ok(not state.to_dict().has("calendar"))
	t.ok(save.load(1))
	_drop_saves(save)
	Fixtures.uninstall_state()
