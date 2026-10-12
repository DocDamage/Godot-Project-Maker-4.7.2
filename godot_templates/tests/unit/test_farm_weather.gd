extends RefCounted
## T17.11: the weather, the HUD and the seasons of a farm. The weather of a day follows from the
## seed and the date, storms and snow keep to their seasons, rain waters, the people are told,
## the forecast is tomorrow's weather, the overlay and the duller light are for outdoor maps,
## the HUD shows the calendar, the money and the energy and tells a harvest and a sale, and a
## season swaps the textures its table names.

const Fixtures := preload("../lib/fixtures.gd")
const Farmer := preload("test_farmer.gd")
const SceneUtil := preload("../../builder/lib/scene_util.gd")
const BuildContext := preload("../../builder/lib/build_context.gd")
const CatalogReader := preload("../../builder/lib/catalog_reader.gd")
const HudRecipe := preload("../../builder/recipes/farm/hud_recipe.gd")

const DIR := "user://test_farm_weather"
const CELL := Vector2i(2, 2)
const CROPS := [
	{"id": "corn", "name": "Corn", "seed": "seed_corn", "produce": "crop_corn", "seasons": ["spring", "summer"], "days": 2, "stages": 3, "regrow": 0, "seed_price": 15, "price": 30, "energy": 14},
]

var _made: Array[Node] = []

func _crops() -> RpgCropData:
	var data := RpgCropData.new()
	data.add_list(CROPS)
	return data

func _ctx(assets: Array = []) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.catalog = CatalogReader.new({"assets": assets, "tilesets": [], "objects": []})
	ctx.config = {"archetype": "farm"}
	return ctx

## A farm's game whose weather is switched on, as the mode's scene has it.
## {state, mode, calendar, weather}
func _game(game_seed: int = 7) -> Dictionary:
	var corn := Fixtures.item(&"crop_corn")
	corn.value = 30
	var state := Fixtures.install_state({&"crop_corn": corn}) as RpgGameState
	state.inventory.registry = state.items
	state.rng.seed_value(game_seed)
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode.ensure_parts()
	mode.weather.enabled = true
	mode._ready()
	_made.append(mode)
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "weather": mode.weather}

## A plot of 4 by 3 cells at (2, 2) and its field, which is in no tree: the test shows it its
## saved state itself (`load_state`), as the field of a map that is not shown has none to show.
func _field() -> RpgField:
	var root := Node2D.new()
	root.name = "Farm"
	var soil := TileMapLayer.new()
	soil.name = "Soil"
	soil.tile_set = Farmer.tile_set()
	root.add_child(soil)
	for y in range(2, 5):
		for x in range(2, 6):
			soil.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	var field := RpgField.new()
	field.name = "Field"
	field.field_id = "farm"
	field.crops = _crops()
	root.add_child(field)
	field.setup()
	_made.append(root)
	return field

func _cleanup() -> void:
	Fixtures.tree().paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	Fixtures.uninstall_state()

func _days(game_seed: int, count: int) -> Array[String]:
	var out: Array[String] = []
	for index in count:
		out.append(RpgFarmWeather.weather_of(game_seed, index))
	return out

# ---------------------------------------------------------------- the weather of a day

func test_the_weather_of_thirty_days_is_the_same_for_the_same_seed_and_differs_for_another(t) -> void:
	t.eq(_days(12345, 30), _days(12345, 30))
	t.ok(_days(12345, 112) != _days(54321, 112), "another seed, another year")
	t.eq(RpgFarmWeather.weather_of(12345, 0), RpgFarmWeather.SUN, "the first day of a game is fair")
	t.eq(RpgFarmWeather.roll(12345, 40), RpgFarmWeather.roll(12345 + (1 << 31), 40), "the seed counts by its low 31 bits")
	for index in 200:
		var value := RpgFarmWeather.roll(99, index)
		t.ok(value >= 0 and value < 100)
	# the game: the seed is kept in the flags, so the days are the same after a save and a load
	var game := _game(4242)
	var state: RpgGameState = game["state"]
	var weather: RpgFarmWeather = game["weather"]
	var calendar: RpgCalendar = game["calendar"]
	var before: Array[String] = []
	for index in 30:
		before.append(weather.weather_on(index))
	t.eq(before, _days(4242, 30), "the game's days are those of its seed")
	t.eq(state.get_flag(RpgFarmWeather.FLAG_ENTITY, RpgFarmWeather.SEED_KEY), 4242)
	state.rng.seed_value(1)  # the random numbers move on; the weather does not
	var saved: Dictionary = JSON.parse_string(JSON.stringify(state.flags))
	state.flags = RpgUtil.restore_numbers(saved)
	var after: Array[String] = []
	for index in 30:
		after.append(weather.weather_on(index))
	t.eq(after, before, "the same after the flags went through a save")
	# whatever the player did: the days come as they were foretold
	for index in range(1, 12):
		calendar.end_day()
		t.eq(weather.today, before[index], "day %d" % index)
	_cleanup()

func test_storms_come_only_in_summer_and_snow_only_in_winter(t) -> void:
	var seen := {}
	for game_seed in range(1, 40):
		for index in 112:
			var kind := RpgFarmWeather.weather_of(game_seed, index)
			var season := RpgCalendar.season_name_of(RpgCalendar.season_of(index))
			seen[kind] = true
			t.ok(RpgFarmWeather.KINDS.has(kind))
			if kind == RpgFarmWeather.STORM and season != "summer":
				t.fail("a storm in %s (seed %d, day %d)" % [season, game_seed, index])
			if kind == RpgFarmWeather.SNOW and season != "winter":
				t.fail("snow in %s (seed %d, day %d)" % [season, game_seed, index])
			if kind == RpgFarmWeather.RAIN and season == "winter":
				t.fail("rain in winter (seed %d, day %d)" % [game_seed, index])
	t.eq(seen.size(), 4, "every kind of weather comes in some year: %s" % [seen.keys()])
	# a shorter season has its own dates
	t.eq(RpgCalendar.season_name_of(RpgCalendar.season_of(8, 7)), "summer")
	for game_seed in range(1, 40):
		t.ok(RpgFarmWeather.weather_of(game_seed, 3, 7) != RpgFarmWeather.STORM, "day 4 of a week-long spring")
	t.ok(RpgFarmWeather.wet(RpgFarmWeather.RAIN) and RpgFarmWeather.wet(RpgFarmWeather.STORM))
	t.ok(not RpgFarmWeather.wet(RpgFarmWeather.SNOW) and not RpgFarmWeather.wet(RpgFarmWeather.SUN))

func test_a_mode_without_its_scene_has_fair_weather(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var mode := RpgFarmMode.new()
	mode.crops = _crops()
	mode._ready()
	_made.append(mode)
	var calendar := RpgCalendar.current()
	for day in 60:
		calendar.end_day()
		t.eq(mode.weather.today, RpgFarmWeather.SUN)
	t.ok(not state.flags.has(RpgFarmWeather.FLAG_ENTITY), "and keeps nothing in the saved game")
	mode.weather.force(RpgFarmWeather.RAIN)
	t.eq(mode.weather.today, RpgFarmWeather.RAIN, "unless a day is forced")
	_cleanup()

# ---------------------------------------------------------------- rain

func test_rain_waters_the_fields_and_a_crop_grows_through_a_rainy_day_without_the_can(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var weather: RpgFarmWeather = game["weather"]
	var calendar: RpgCalendar = game["calendar"]
	var field := _field()
	t.ok(field.till(CELL) and field.plant(CELL, "corn"))
	t.ok(field.till(CELL + Vector2i.RIGHT), "tilled soil with nothing on it")
	# a second field, on a map that is not shown
	state.set_flag(RpgField.FLAG_ENTITY, "meadow", {"5,5": {"w": false, "crop": "corn", "grown": 0, "dead": false, "idle": 0}})
	weather.force_tomorrow(RpgFarmWeather.RAIN)
	calendar.end_day()
	field.load_state()
	t.eq(weather.today, RpgFarmWeather.RAIN)
	t.ok(weather.is_wet() and weather.keeps_animals_in())
	t.eq(field.grown_at(CELL), 0, "the dry day before did not count")
	t.ok(field.is_watered(CELL) and field.is_watered(CELL + Vector2i.RIGHT), "the rain watered every tilled cell in the morning")
	t.ok(RpgUtil.to_bool(RpgUtil.to_dict(RpgUtil.to_dict(state.get_flag(RpgField.FLAG_ENTITY, "meadow"))["5,5"])["w"]), "of every field")
	t.eq(state.get_flag(RpgFarmWeather.FLAG_ENTITY, RpgFarmWeather.WATERED_KEY), calendar.today())
	# what is tilled in the rain is wet at once
	weather.watch_field(field)
	t.ok(field.till(CELL + Vector2i.DOWN))
	t.ok(field.is_watered(CELL + Vector2i.DOWN), "tilled in the rain: wet")
	# the rainy day counts in its night, without the can
	weather.force_tomorrow(RpgFarmWeather.SUN)
	calendar.end_day()
	field.load_state()
	t.eq(field.grown_at(CELL), 1, "the crop grew through the rainy day")
	t.ok(not field.is_watered(CELL), "and the soil is dry on the fair morning after")
	t.eq(weather.today, RpgFarmWeather.SUN)
	t.ok(not weather.is_wet() and not weather.keeps_animals_in())
	calendar.end_day()
	field.load_state()
	t.eq(field.grown_at(CELL), 1, "a fair day without the can does not count")
	# a storm waters too; the rain of a day falls once (a load on that day waters nothing again)
	weather.force(RpgFarmWeather.STORM)
	field.load_state()
	t.ok(field.is_watered(CELL), "a storm waters")
	var again := RpgUtil.to_dict(state.get_flag(RpgField.FLAG_ENTITY, "farm"))
	RpgUtil.to_dict(again[RpgField.cell_name(CELL)])["w"] = false
	state.set_flag(RpgField.FLAG_ENTITY, "farm", again)
	weather.sync()
	field.load_state()
	t.ok(not field.is_watered(CELL), "the same day does not rain on the field twice")
	t.eq(RpgFarmWeather.water_fields(), 1, "what the night before the crops does")
	# snow keeps the animals in and waters nothing
	weather.force_tomorrow(RpgFarmWeather.SNOW)
	calendar.end_day()
	field.load_state()
	t.ok(weather.keeps_animals_in() and not weather.is_wet() and not field.is_watered(CELL))
	_cleanup()

func test_the_schedules_are_told_the_weather_and_it_is_empty_after_a_new_game(t) -> void:
	var game := _game()
	var state: RpgGameState = game["state"]
	var weather: RpgFarmWeather = game["weather"]
	var calendar: RpgCalendar = game["calendar"]
	t.eq(RpgSchedule.weather(), "", "the first morning is fair")
	weather.force_tomorrow(RpgFarmWeather.RAIN)
	calendar.end_day()
	t.eq(RpgSchedule.weather(), "rain")
	weather.force_tomorrow(RpgFarmWeather.STORM)
	calendar.end_day()
	t.eq(RpgSchedule.weather(), "rain", "a storm is rain to the people")
	weather.force_tomorrow(RpgFarmWeather.SNOW)
	calendar.end_day()
	t.eq(RpgSchedule.weather(), "", "snow is not")
	weather.force(RpgFarmWeather.RAIN)
	t.eq(RpgSchedule.weather(), "rain")
	# a new game: the flags and the calendar start over, and so does the weather
	state.new_game()
	state.rng.seed_value(7)
	RpgUtil.emit(&"map_entered", [&"farm"])
	t.eq([calendar.today(), weather.today, RpgSchedule.weather()], [0, RpgFarmWeather.SUN, ""])
	# a loaded game takes the weather of its day
	var rainy := -1
	for index in range(1, 112):
		if RpgFarmWeather.weather_of(7, index) == RpgFarmWeather.RAIN:
			rainy = index
			break
	t.ok(rainy > 0, "a year of seed 7 has a rainy day")
	var date := RpgCalendar.date_of(rainy)
	calendar.from_dict({"minute": 600, "day": date[0], "season": date[1], "year": date[2]})
	RpgUtil.emit(&"game_loaded", [1])
	t.eq([weather.today, RpgSchedule.weather()], [RpgFarmWeather.RAIN, "rain"])
	# the mode that is gone leaves nothing behind
	_cleanup()
	t.eq(RpgSchedule.weather(), "")
	t.eq(RpgDayNight.weather_tint, RpgDayNight.DAY)

func test_the_forecast_is_tomorrows_weather(t) -> void:
	var game := _game(31)
	var weather: RpgFarmWeather = game["weather"]
	var calendar: RpgCalendar = game["calendar"]
	var kinds := {}
	for day in 60:
		var foretold := weather.forecast()
		kinds[foretold] = true
		calendar.end_day()
		t.eq(weather.today, foretold, "day %d" % (day + 1))
	t.ok(kinds.size() >= 2, "two months have more than one kind of weather")
	weather.force_tomorrow(RpgFarmWeather.STORM)
	t.eq(weather.forecast(), RpgFarmWeather.STORM)
	t.eq(weather.forecast_text(), "Tomorrow's weather: Storm.")
	var sign := RpgWeatherSign.new()
	_made.append(sign)
	t.eq(sign.reading(), "", "a sign in a game without a mode says nothing")
	var texts: Array[String] = []
	RpgUtil.events().notify.connect(func(text: String) -> void: texts.append(text))
	sign.interact()
	t.eq(texts, [""] as Array[String])
	var built := HudRecipe.build_sign(_ctx())
	_made.append(built)
	t.ok(built is RpgWeatherSign and built.name == "WeatherSign")
	t.eq(built.collision_layer, 17, "the world and the interactables")
	t.ok(built.get_node_or_null("Shape") != null and built.get_node_or_null("Sprite") != null)
	_cleanup()

# ---------------------------------------------------------------- the overlay and the light

func _strip(cells: int) -> ImageTexture:
	return ImageTexture.create_from_image(Image.create_empty(64 * cells, 64, false, Image.FORMAT_RGBA8))

func test_the_overlay_is_there_outdoors_on_a_wet_day_and_not_indoors(t) -> void:
	var game := _game()
	var weather: RpgFarmWeather = game["weather"]
	weather.rain_texture = _strip(3)
	var outdoors := RpgMapRoot.new()
	outdoors.map_id = &"farm"
	var indoors := RpgMapRoot.new()
	indoors.map_id = &"house"
	indoors.is_interior = true
	_made.append(outdoors)
	_made.append(indoors)
	weather.refresh_overlay(outdoors)
	t.ok(weather.overlay() == null and not weather.overlay_visible(), "a fair day has none")
	weather.force(RpgFarmWeather.RAIN)
	t.ok(weather.shows_on(outdoors) and not weather.shows_on(indoors) and not weather.shows_on(null))
	weather.refresh_overlay(outdoors)
	var overlay := weather.overlay()
	t.ok(overlay != null and weather.overlay_visible(), "rain falls outdoors")
	t.ok(overlay.get_parent() is CanvasLayer, "on a layer of the screen, not in the world")
	t.eq((overlay.get_parent() as CanvasLayer).layer, RpgFarmWeather.OVERLAY_LAYER)
	t.eq([overlay.mode, overlay.frames, overlay.passes], [RpgWeatherOverlay.FALL, 3, 1])
	t.eq(overlay.cell_size(), Vector2(64, 64), "one cell of the strip, repeated")
	t.near(overlay.fps, 9.0)
	weather.refresh_overlay(indoors)
	t.ok(not weather.overlay_visible(), "and not indoors")
	t.eq(overlay.mode, "")
	weather.force(RpgFarmWeather.STORM)
	weather.refresh_overlay(outdoors)
	t.eq([overlay.mode, overlay.passes], [RpgWeatherOverlay.FALL, 2], "a storm without a picture is the rain twice over")
	weather.storm_texture = _strip(2)
	weather.storm_frames = 2
	weather.refresh_overlay(outdoors)
	t.eq([overlay.texture, overlay.frames, overlay.passes], [weather.storm_texture, 2, 1], "a pack's own storm")
	weather.force(RpgFarmWeather.SNOW)
	weather.refresh_overlay(outdoors)
	t.eq(overlay.mode, RpgWeatherOverlay.FLAKES, "snow without a picture is drawn")
	weather.snow_texture = _strip(1)
	weather.refresh_overlay(outdoors)
	t.eq([overlay.mode, overlay.texture], [RpgWeatherOverlay.FALL, weather.snow_texture])
	weather.force(RpgFarmWeather.SUN)
	weather.refresh_overlay(outdoors)
	t.ok(not weather.overlay_visible(), "gone when the weather is fair again")
	_cleanup()

func test_the_light_is_duller_on_a_wet_day_outdoors_only(t) -> void:
	var game := _game()
	var weather: RpgFarmWeather = game["weather"]
	var calendar: RpgCalendar = game["calendar"]
	calendar.minute = 12 * 60
	var fair := RpgDayNight.map_ambient(false, true, 0.0)
	t.eq(fair, RpgDayNight.DAY, "noon of a fair day")
	weather.force(RpgFarmWeather.RAIN)
	var rain := RpgDayNight.map_ambient(false, true, 0.0)
	t.ok(rain.r < fair.r and rain.g < fair.g and rain.b < fair.b, "duller in the rain: %s" % rain)
	t.eq(RpgDayNight.map_ambient(true, true, 0.0), RpgDayNight.INTERIOR, "an interior is what it was")
	weather.force(RpgFarmWeather.STORM)
	t.ok(RpgDayNight.map_ambient(false, true, 0.0).r < rain.r, "darker in a storm")
	t.eq(RpgDayNight.ambient_at(12.0), RpgDayNight.DAY, "the table of the day is not touched")
	weather.force(RpgFarmWeather.SUN)
	t.eq(RpgDayNight.map_ambient(false, true, 0.0), fair)
	_cleanup()
	t.eq(RpgDayNight.weather_tint, RpgDayNight.DAY)

# ---------------------------------------------------------------- the HUD

func test_the_hud_shows_the_calendar_the_money_and_the_energy_and_tells_a_harvest_and_a_sale(t) -> void:
	var corn := Fixtures.item(&"crop_corn")
	corn.value = 30
	corn.display_name = "Corn"
	var state := Fixtures.install_state({&"crop_corn": corn}) as RpgGameState
	state.inventory.registry = state.items
	state.rng.seed_value(11)
	var tree := Fixtures.tree()
	await tree.process_frame
	var ctx := _ctx()
	var mode := RpgFarmMode.new()
	mode.name = "Combat"
	mode.crops = _crops()
	var hud := HudRecipe.build_hud(ctx) as RpgFarmHud
	mode.add_child(hud)
	mode.add_child(HudRecipe.build_weather(ctx))
	SceneUtil.set_owner_recursive(mode, mode)
	tree.root.add_child(mode)
	_made.append(mode)
	var calendar := RpgCalendar.current()
	var weather := mode.weather
	t.ok(weather.enabled and weather.get_parent() == mode, "the mode's scene has the weather, switched on")
	t.eq(hud.layer, RpgFarmHud.LAYER)
	var clock := hud.get_node("%Clock") as Label
	var date := hud.get_node("%Date") as Label
	var sky := hud.get_node("%Weather") as Label
	var money := hud.get_node("%Money") as Label
	var bar := hud.get_node("%EnergyBar") as ProgressBar
	t.eq(hud.get_node("%Slots").get_child_count(), RpgHotbar.SLOTS, "the hotbar is what it was")
	t.eq([clock.text, date.text, sky.text], ["6:00", "Monday 1, spring", "Sunny"])
	t.ok(sky.visible and not (hud.get_node("%WeatherIcon") as TextureRect).visible, "a word where the packs have no icon")
	t.eq(money.text, "Gold: 0")
	state.gold = 120
	t.eq(money.text, "Gold: 120", "the money follows Events.gold_changed")
	calendar.pass_minutes(6 * 60 + 40)
	t.eq(clock.text, "12:40")
	calendar.pass_minutes(7)
	t.eq(clock.text, "12:40", "the clock moves in steps of ten minutes")
	calendar.pass_minutes(3)
	t.eq(clock.text, "12:50")
	t.eq(RpgFarmHud.clock_text(RpgCalendar.DAY_END - 1), "1:50")
	mode.energy.value = 40
	t.eq([bar.value, bar.max_value], [40.0, 100.0], "the energy as a bar")
	weather.force_tomorrow(RpgFarmWeather.RAIN)
	calendar.end_day()
	t.eq([clock.text, date.text, sky.text], ["6:00", "Tuesday 2, spring", "Rain"])
	for day in calendar.days_per_season - 2:
		calendar.end_day()
	t.eq(date.text.get_slice(", ", 1), "spring")
	calendar.end_day()
	t.eq(date.text, "%s 1, summer" % RpgFarmStrings.weekday(calendar.weekday()))
	# a pack's icon of the weather stands in for the word
	var icon := ImageTexture.create_from_image(Image.create_empty(12, 12, false, Image.FORMAT_RGBA8))
	weather.force(RpgFarmWeather.SUN)
	hud.weather_icons = {RpgFarmWeather.STORM: icon}
	weather.force(RpgFarmWeather.STORM)
	t.ok((hud.get_node("%WeatherIcon") as TextureRect).visible and not sky.visible)
	t.eq((hud.get_node("%WeatherIcon") as TextureRect).texture, icon)
	weather.force(RpgFarmWeather.SUN)
	t.ok(sky.visible and sky.text == "Sunny")
	# the toasts
	var texts: Array[String] = []
	RpgUtil.events().notify.connect(func(text: String) -> void: texts.append(text))
	var field := _field()
	hud.watch_field(field)
	t.ok(field.till(CELL) and field.plant(CELL, "corn"))
	RpgUtil.to_dict(field.cells[CELL])["grown"] = 2
	t.ok(field.harvest(CELL))
	t.eq(texts, ["Harvested Corn."] as Array[String], "a harvest gives a toast")
	t.eq(RpgFarmHud.harvest_text(&"crop_corn", 3), "Harvested Corn x3.")
	texts.clear()
	t.eq(RpgShippingBin.put(&"crop_corn", 1), 1)
	calendar.end_day()
	var summary := mode.day_end.summary()
	t.ok(summary != null, "the morning's summary first")
	if summary != null:
		summary.close()
	t.ok(texts.has("The shipping bin paid 30 G."), "a sale gives a toast: %s" % [texts])
	t.eq(state.gold, 150)
	t.eq(money.text, "Gold: 150")
	texts.clear()
	calendar.end_day()
	t.ok(not texts.has("The shipping bin paid 30 G."), "a night that sold nothing gives none")
	# the small font of a small screen
	var small := _ctx()
	small.config["resolution"] = [320, 180]
	var small_hud := HudRecipe.build_hud(small)
	_made.append(small_hud)
	t.eq((small_hud.find_child("Clock", true, false) as Label).get_theme_font_size("font_size"), HudRecipe.SMALL_FONT)
	t.ok(HudRecipe.mode_hash(small) != HudRecipe.mode_hash(ctx))
	tree.root.remove_child(mode)
	_cleanup()

# ---------------------------------------------------------------- the seasons

func _saved_texture(file: String, colour: Color) -> String:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR))
	var image := Image.create_empty(32, 16, false, Image.FORMAT_RGBA8)
	image.fill(colour)
	var path := "%s/%s.tres" % [DIR, file]
	ResourceSaver.save(ImageTexture.create_from_image(image), path)
	return path

func test_the_season_swap_changes_the_textures_the_table_names(t) -> void:
	var spring := _saved_texture("trees_spring", Color.GREEN)
	var winter := _saved_texture("trees_winter", Color.WHITE)
	var plain := _saved_texture("ground", Color.BROWN)
	var snowy := _saved_texture("ground_winter", Color.GRAY)
	var other := _saved_texture("house", Color.RED)
	var seasons := RpgFarmSeasons.new()
	_made.append(seasons)
	seasons.set_table({"pack.trees_spring": {"spring": spring, "winter": winter}, "pack.ground": {"": plain, "winter": snowy}, "pack.lonely": {"spring": other}})
	t.eq(seasons.groups.size(), 2, "a group of one sheet is none")
	t.eq(seasons.path_for(spring, "winter"), winter)
	t.eq(seasons.path_for(winter, "summer"), spring, "a season without a sheet shows the group's first")
	t.eq(seasons.path_for(snowy, "summer"), plain, "or the sheet that names no season")
	t.eq(seasons.path_for(other, "winter"), other, "what is in no group stays")
	var map := RpgMapRoot.new()
	map.map_id = &"farm"
	_made.append(map)
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(16, 16)
	tiles.add_custom_data_layer()
	tiles.set_custom_data_layer_name(0, "tillable")
	tiles.set_custom_data_layer_type(0, TYPE_BOOL)
	for entry: Array in [[0, plain], [3, other]]:
		var source := TileSetAtlasSource.new()
		source.texture = load(str(entry[1])) as Texture2D
		source.texture_region_size = Vector2i(16, 16)
		tiles.add_source(source, RpgUtil.to_int(entry[0]))
		source.create_tile(Vector2i(0, 0))
		source.create_tile(Vector2i(1, 0))
	var ground := tiles.get_source(0) as TileSetAtlasSource
	ground.get_tile_data(Vector2i(1, 0), 0).set_custom_data("tillable", true)
	var layer := TileMapLayer.new()
	layer.name = "Ground"
	layer.tile_set = tiles
	layer.set_cell(Vector2i(4, 4), 0, Vector2i(1, 0))
	layer.set_cell(Vector2i(5, 4), 3, Vector2i(0, 0))
	map.add_child(layer)
	var tree_sprite := Sprite2D.new()
	tree_sprite.texture = load(spring) as Texture2D
	map.add_child(tree_sprite)
	var part := AtlasTexture.new()
	part.atlas = load(spring) as Texture2D
	part.region = Rect2(16, 0, 16, 16)
	var bush := Sprite2D.new()
	bush.texture = part
	map.add_child(bush)
	var frames := SpriteFrames.new()
	frames.add_frame(&"default", load(spring) as Texture2D, 2.0)
	var animated := AnimatedSprite2D.new()
	animated.sprite_frames = frames
	map.add_child(animated)
	var house := Sprite2D.new()
	house.texture = load(other) as Texture2D
	map.add_child(house)

	t.eq(seasons.apply(map, "winter"), 4, "the ground's source, the tree, the bush's atlas is counted with its sprite's, the frame")
	t.eq(ground.texture.resource_path, snowy, "the atlas source of the tile set")
	t.eq((tiles.get_source(3) as TileSetAtlasSource).texture.resource_path, other, "a source that is in no group stays")
	t.eq([layer.get_cell_source_id(Vector2i(4, 4)), layer.get_cell_atlas_coords(Vector2i(4, 4))], [0, Vector2i(1, 0)], "no cell was painted")
	t.ok(RpgUtil.to_bool(ground.get_tile_data(Vector2i(1, 0), 0).get_custom_data("tillable")), "and the tiles keep what they say")
	t.eq(tree_sprite.texture.resource_path, winter)
	t.eq([bush.texture, part.atlas.resource_path, part.region], [part, winter, Rect2(16, 0, 16, 16)], "an AtlasTexture keeps its region")
	t.eq(frames.get_frame_texture(&"default", 0).resource_path, winter)
	t.near(frames.get_frame_duration(&"default", 0), 2.0)
	t.eq(house.texture.resource_path, other)
	t.eq(seasons.apply(map, "winter"), 0, "nothing to do the second time")
	t.ok(seasons.apply(map, "summer") > 0)
	t.eq([ground.texture.resource_path, tree_sprite.texture.resource_path, part.atlas.resource_path], [plain, spring, spring], "and back")
	var indoors := RpgMapRoot.new()
	indoors.is_interior = true
	_made.append(indoors)
	var lamp := Sprite2D.new()
	lamp.texture = load(spring) as Texture2D
	indoors.add_child(lamp)
	t.eq(seasons.apply(indoors, "winter"), 0, "an interior is left alone")
	t.eq(lamp.texture.resource_path, spring)
	# the calendar: the mode's part swaps when the season changes (no map is shown here)
	t.eq(seasons.apply_to_current(), 0)
	_cleanup()
	for file: String in ["trees_spring", "trees_winter", "ground", "ground_winter", "house"]:
		DirAccess.remove_absolute(ProjectSettings.globalize_path("%s/%s.tres" % [DIR, file]))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(DIR))

func _asset(id: String, tags: Array, role: String = "DECORATION", usage: String = "tiles") -> Dictionary:
	return {"id": id, "pack_id": id.get_slice(".", 0), "path": "assets/packs/%s.png" % id.replace(".", "/"), "status": "CONFIRMED",
		"detected": {"role": role, "usage": usage, "tags": tags, "size": [192, 64], "frame": [64, 64]}}

func test_the_recipe_writes_the_table_of_the_seasons_and_finds_the_pictures_of_the_weather(t) -> void:
	var ctx := _ctx([
		_asset("pack.trees_autumn", ["season:autumn", "variant_of:pack.trees"]),
		_asset("pack.trees", []),
		_asset("pack.trees_winter", ["season:winter", "variant_of:pack.trees"]),
		_asset("pack.grass_spring", ["season:spring"]),
		_asset("pack.grass_summer", ["season:summer", "variant_of:pack.grass_spring"]),
		_asset("pack.car_red", ["colour:red"]),
		_asset("pack.car_blue", ["colour:blue", "variant_of:pack.car_red"]),
		_asset("pack.rock", []),
		_asset("pack.rock_winter", ["season:winter", "variant_of:pack.rock"]),
		_asset("pack.fx.heavy_rain", ["weather"], "EFFECT", "sprite"),
		_asset("pack.fx.snow_fall", ["weather"], "EFFECT", "sprite"),
		_asset("pack.ui.rain_icon", ["weather"], "UI", "ui"),
		_asset("rpggen_farm_kit.rain", ["weather", "farm_kit"], "EFFECT", "sprite"),
	])
	t.eq(HudRecipe.season_table(ctx), {
		"pack.trees": {"": "res://assets/packs/pack/trees.png", "autumn": "res://assets/packs/pack/trees_autumn.png", "winter": "res://assets/packs/pack/trees_winter.png"},
		"pack.grass_spring": {"spring": "res://assets/packs/pack/grass_spring.png", "summer": "res://assets/packs/pack/grass_summer.png"},
	}, "a group of colours and a group with one season are none")
	t.eq(HudRecipe.rain_asset(ctx).get("id"), "pack.fx.heavy_rain", "a pack's own rain before the kit's")
	t.eq(HudRecipe.weather_asset(ctx, "snow").get("id"), "pack.fx.snow_fall")
	t.ok(HudRecipe.weather_asset(ctx, "storm").is_empty())
	t.eq(HudRecipe.icon_asset(ctx, "rain").get("id"), "pack.ui.rain_icon")
	t.ok(HudRecipe.icon_asset(ctx, "sun").is_empty())
	t.eq(HudRecipe.strip_of(ctx, ctx.catalog.asset("pack.fx.heavy_rain")), [3, 9.0], "three cells in its row")
	var kit_only := _ctx([_asset("rpggen_farm_kit.rain", ["weather", "farm_kit"], "EFFECT", "sprite")])
	t.eq(HudRecipe.rain_asset(kit_only).get("id"), "rpggen_farm_kit.rain")
	t.eq(HudRecipe.season_table(kit_only), {})
	var bare := HudRecipe.build_weather(_ctx())
	_made.append(bare)
	t.ok(bare is RpgFarmWeather and (bare as RpgFarmWeather).enabled and bare.name == RpgFarmWeather.NODE_NAME)
	t.ok((bare as RpgFarmWeather).rain_texture == null, "no picture, no rain to see; it waters all the same")
	_cleanup()

func test_the_music_follows_the_season_and_the_night(t) -> void:
	var all := func(_slot: StringName) -> bool: return true
	var none := func(_slot: StringName) -> bool: return false
	var summer_only := func(slot: StringName) -> bool: return slot == &"music_summer"
	var no_night := func(slot: StringName) -> bool: return slot != &"music_night"
	t.eq(RpgFarmSeasons.slot_for(0, 12, all), &"music_spring")
	t.eq(RpgFarmSeasons.slot_for(3, 12, all), &"music_winter")
	t.eq(RpgFarmSeasons.slot_for(2, 21, all), &"music_night", "after dark")
	t.eq(RpgFarmSeasons.slot_for(2, 1, all), &"music_night", "until the day ends")
	t.eq(RpgFarmSeasons.slot_for(2, 19, all), &"music_autumn")
	t.eq(RpgFarmSeasons.slot_for(2, 6, all), &"music_autumn", "the morning")
	t.eq(RpgFarmSeasons.slot_for(2, 22, no_night), &"music_autumn", "a game without night music keeps the season's")
	t.eq(RpgFarmSeasons.slot_for(0, 12, summer_only), &"music_summer", "a season without its own plays the first that is filled")
	t.eq(RpgFarmSeasons.slot_for(3, 23, summer_only), &"music_summer")
	t.eq(RpgFarmSeasons.slot_for(1, 12, none), &"", "nothing filled: the maps keep their music")
