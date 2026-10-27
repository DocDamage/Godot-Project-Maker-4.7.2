extends RefCounted
## The game's language option (T12.56): the locales offered, switching, saving, the fallback.

const Fixtures := preload("../lib/fixtures.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const MENU_TMP := "user://test_settings_menu.tscn"

const TEST_LOCALE := "eo"  # any locale the server knows; the texts are made up

static func _test_locale() -> Translation:
	var made_up := Translation.new()
	made_up.locale = TEST_LOCALE
	made_up.add_message(&"UI_SPEED_SLOW", &"[Slow~]")
	made_up.add_message(&"UI_SPEED_NORMAL", &"[Normal~]")
	made_up.add_message(&"UI_LANGUAGE_SYSTEM", &"[System~]")
	# no UI_SPEED_FAST: it must fall back to English
	return made_up

func _menu() -> RpgSettingsMenu:
	var root: Node = UiRecipes.new().call("_build_settings_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgSettingsMenu
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

func test_switching_the_locale_changes_a_label_and_a_missing_text_stays_english(t) -> void:
	var english := Fixtures.install_english()
	var made_up := _test_locale()
	TranslationServer.add_translation(made_up)
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.path = "user://test_language_settings_%d.cfg" % Time.get_ticks_usec()
	settings.set_language("en")
	var menu := _menu()
	var speed := menu.get_node("%TextSpeed") as OptionButton
	var language := menu.get_node("%Language") as OptionButton
	t.eq(speed.get_item_text(0), "Slow")
	t.eq(language.get_item_text(0), "System", "the first choice follows the system")
	settings.set_language(TEST_LOCALE)
	t.eq(TranslationServer.get_locale(), TEST_LOCALE)
	t.eq(speed.get_item_text(0), "[Slow~]", "the menu rebuilt its text on the locale change")
	t.eq(speed.get_item_text(2), "Fast", "a key the locale does not have falls back to English")
	t.eq(language.get_item_text(0), "[System~]")
	t.eq(speed.selected, 1, "the choice survives the rebuild")
	menu.free()
	settings.set_language("en")
	TranslationServer.remove_translation(made_up)
	Fixtures.uninstall("RpgSettings")
	Fixtures.uninstall_english(english)

func test_the_language_is_saved_and_system_means_the_os_locale(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.path = "user://test_language_saved_%d.cfg" % Time.get_ticks_usec()
	settings.set_language(TEST_LOCALE)
	t.ok(settings.save_settings())
	settings.language = ""
	settings.load_settings()
	t.eq(settings.language, TEST_LOCALE)
	# the server standardizes a locale (a Linux runner's "C" becomes "en"): compare with what it
	# makes of the system's
	TranslationServer.set_locale(OS.get_locale())
	var system_locale := TranslationServer.get_locale()
	TranslationServer.set_locale(TEST_LOCALE)
	settings.set_language("")
	t.eq(settings.effective_locale(), OS.get_locale())
	t.eq(TranslationServer.get_locale(), system_locale)
	DirAccess.remove_absolute(settings.path)
	TranslationServer.set_locale("en")
	Fixtures.uninstall("RpgSettings")

func test_the_offered_locales_are_the_translations_of_the_project(t) -> void:
	var folder := "user://test_i18n_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(folder)
	for locale: String in ["eo", "en", "de"]:
		var tr_res := Translation.new()
		tr_res.locale = locale
		ResourceSaver.save(tr_res, "%s/strings.%s.tres" % [folder, locale])
	t.eq(RpgStrings.locales(folder), PackedStringArray(["de", "en", "eo"]))
	t.eq(RpgStrings.locales("user://no_such_folder"), PackedStringArray())
	for locale: String in ["eo", "en", "de"]:
		DirAccess.remove_absolute("%s/strings.%s.tres" % [folder, locale])
	DirAccess.remove_absolute(folder)
