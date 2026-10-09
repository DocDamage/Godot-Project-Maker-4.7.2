extends RefCounted
## The game's language option (T12.56): the locales offered, switching, saving, the fallback.

const Fixtures := preload("../lib/fixtures.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const MENU_TMP := "user://test_settings_menu.tscn"

static func _french() -> Translation:
	var fr := Translation.new()
	fr.locale = "fr"
	fr.add_message(&"UI_SPEED_SLOW", &"Lent")
	fr.add_message(&"UI_SPEED_NORMAL", &"Normal")
	fr.add_message(&"UI_LANGUAGE_SYSTEM", &"Système")
	# no UI_SPEED_FAST: it must fall back to English
	return fr

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
	var fr := _french()
	TranslationServer.add_translation(fr)
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.path = "user://test_language_settings_%d.cfg" % Time.get_ticks_usec()
	settings.set_language("en")
	var menu := _menu()
	var speed := menu.get_node("%TextSpeed") as OptionButton
	var language := menu.get_node("%Language") as OptionButton
	t.eq(speed.get_item_text(0), "Slow")
	t.eq(language.get_item_text(0), "System", "the first choice follows the system")
	settings.set_language("fr")
	t.eq(TranslationServer.get_locale(), "fr")
	t.eq(speed.get_item_text(0), "Lent", "the menu rebuilt its text on the locale change")
	t.eq(speed.get_item_text(2), "Fast", "a key French does not have falls back to English")
	t.eq(language.get_item_text(0), "Système")
	t.eq(speed.selected, 1, "the choice survives the rebuild")
	menu.free()
	settings.set_language("en")
	TranslationServer.remove_translation(fr)
	Fixtures.uninstall("RpgSettings")
	Fixtures.uninstall_english(english)

func test_the_language_is_saved_and_system_means_the_os_locale(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	settings.path = "user://test_language_saved_%d.cfg" % Time.get_ticks_usec()
	settings.set_language("fr")
	t.ok(settings.save_settings())
	settings.language = ""
	settings.load_settings()
	t.eq(settings.language, "fr")
	settings.set_language("")
	t.eq(settings.effective_locale(), OS.get_locale())
	t.eq(TranslationServer.get_locale(), OS.get_locale())
	DirAccess.remove_absolute(settings.path)
	TranslationServer.set_locale("en")
	Fixtures.uninstall("RpgSettings")

func test_the_offered_locales_are_the_translations_of_the_project(t) -> void:
	var folder := "user://test_i18n_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(folder)
	for locale: String in ["fr", "en", "de"]:
		var tr_res := Translation.new()
		tr_res.locale = locale
		ResourceSaver.save(tr_res, "%s/strings.%s.tres" % [folder, locale])
	t.eq(RpgStrings.locales(folder), PackedStringArray(["de", "en", "fr"]))
	t.eq(RpgStrings.locales("user://no_such_folder"), PackedStringArray())
	for locale: String in ["fr", "en", "de"]:
		DirAccess.remove_absolute("%s/strings.%s.tres" % [folder, locale])
	DirAccess.remove_absolute(folder)
