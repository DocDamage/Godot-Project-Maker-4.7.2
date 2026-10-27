extends RefCounted
## The *Day and night* setting in a game with a calendar (T18.06): on by default in a farm, stored
## only once the player changes it, and obeyed: off, the outdoor light stays full day while the
## calendar's time goes on; a game without a calendar is as before.

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const MENU_TMP := "user://test_day_night_menu.tscn"

func _settings() -> RpgSettingsStore:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.path = "user://test_day_night_%d.cfg" % Time.get_ticks_usec()
	settings.clear_day_night_choice()
	return settings

func _farm() -> RpgCalendar:
	Fixtures.install_state()
	var calendar := RpgCalendar.ensure()
	calendar.minute_s = 0.5
	return calendar

func _light_at(calendar: RpgCalendar, outside: RpgMapRoot, minute: int) -> Color:
	calendar.minute = minute
	outside.update_ambient()
	return (outside.get_node("Ambient") as CanvasModulate).color

func _end(settings: RpgSettingsStore, roots: Array) -> void:
	for root: Node in roots:
		root.free()
	DirAccess.remove_absolute(settings.path)
	Fixtures.uninstall_state()
	Fixtures.uninstall("RpgSettings")

func test_a_farm_with_no_stored_setting_dims_at_night(t) -> void:
	var settings := _settings()
	var calendar := _farm()
	t.ok(settings.day_night_on(), "on by default with a calendar")
	settings.load_settings()
	t.ok(settings.day_night_on(), "no file: still the default")
	var outside := RpgMapRoot.new()
	outside._ready()
	t.eq(_light_at(calendar, outside, 12 * 60), RpgDayNight.DAY, "noon")
	t.eq(_light_at(calendar, outside, 24 * 60), RpgDayNight.NIGHT, "midnight")
	t.ok(settings.save_settings())
	var cfg := ConfigFile.new()
	cfg.load(settings.path)
	t.ok(not cfg.has_section_key("game", "day_night"), "not stored until the player changes it")
	_end(settings, [outside])

func test_turned_off_noon_and_midnight_have_the_same_light_and_time_goes_on(t) -> void:
	var settings := _settings()
	var calendar := _farm()
	var outside := RpgMapRoot.new()
	outside._ready()
	settings.set_day_night(false)
	t.ok(not settings.day_night_on())
	var noon := _light_at(calendar, outside, 12 * 60)
	t.eq(_light_at(calendar, outside, 24 * 60), noon, "midnight looks like noon")
	t.eq(noon, RpgDayNight.DAY)
	t.ok(not outside.is_processing())
	var before := calendar.minute
	calendar.advance(10.0)
	t.eq(calendar.minute, before + 20, "the calendar's time goes on")
	RpgDayNight.weather_tint = Color(0.8, 0.8, 0.9)
	outside.update_ambient()
	t.eq((outside.get_node("Ambient") as CanvasModulate).color, Color(0.8, 0.8, 0.9), "a weather tint still applies")
	RpgDayNight.weather_tint = RpgDayNight.DAY
	# the choice is stored and read back
	t.ok(settings.save_settings())
	settings.clear_day_night_choice()
	settings.load_settings()
	t.ok(settings.day_night_chosen and not settings.day_night_on(), "off, as chosen")
	# turned on again in the menu, the light changes at once
	settings.set_day_night(true)
	t.eq((outside.get_node("Ambient") as CanvasModulate).color, RpgDayNight.ambient_at(calendar.hour()), "at once")
	_end(settings, [outside])

func test_a_settings_file_of_before_keeps_only_a_cycle_that_was_on(t) -> void:
	var settings := _settings()
	var cfg := ConfigFile.new()
	cfg.set_value("game", "day_night", false)  # every file of 1.0 to 1.4 had the key
	cfg.save(settings.path)
	settings.load_settings()
	t.ok(not settings.day_night_chosen, "off was the default, not a choice")
	cfg.set_value("game", "day_night", true)
	cfg.save(settings.path)
	settings.load_settings()
	t.ok(settings.day_night_chosen and settings.day_night_on(), "on was a choice")
	DirAccess.remove_absolute(settings.path)
	Fixtures.uninstall("RpgSettings")

func test_a_top_down_rpg_is_unchanged(t) -> void:
	var settings := _settings()
	var state := Fixtures.install_state() as RpgGameState
	state.playtime_s = 600.0
	t.ok(RpgCalendar.current() == null)
	t.ok(not settings.day_night_on(), "off by default without a calendar")
	var outside := RpgMapRoot.new()
	outside._ready()
	t.eq((outside.get_node("Ambient") as CanvasModulate).color, RpgDayNight.DAY)
	t.ok(not outside.is_processing())
	settings.set_day_night(true)
	t.eq((outside.get_node("Ambient") as CanvasModulate).color, RpgDayNight.ambient_at(RpgDayNight.hour_at(600.0)), "on: the cycle of the play time")
	_end(settings, [outside])

func test_the_menu_shows_the_toggle_pressed_in_a_farm(t) -> void:
	var settings := _settings()
	_farm()
	var root: Node = UiRecipes.new().call("_build_settings_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgSettingsMenu
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	var toggle := menu.get_node("%DayNight") as CheckButton
	t.ok(toggle.visible and toggle.button_pressed, "pressed by default in a farm")
	toggle.button_pressed = false
	t.ok(settings.day_night_chosen and not settings.day_night_on())
	_end(settings, [menu])
