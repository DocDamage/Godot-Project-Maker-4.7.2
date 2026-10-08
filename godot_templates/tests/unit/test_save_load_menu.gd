extends RefCounted
## The text of a save slot, the new header fields and the thumbnail file (T12.44).

const Fixtures := preload("../lib/fixtures.gd")

func _unix(year: int, month: int, day: int, hour: int, minute: int) -> int:
	return int(Time.get_unix_time_from_datetime_dict({"year": year, "month": month, "day": day, "hour": hour, "minute": minute, "second": 0}))

func test_a_used_slot_reads_map_level_playtime_and_local_time(t) -> void:
	RpgStrings._add_missing_defaults()  # the English defaults of the keys (the template has no generated i18n folder)
	var h := {"map": "village", "level": 3, "playtime_s": 4320.0, "saved_unix": _unix(2026, 10, 12, 14, 5)}
	t.eq(RpgSaveLoadMenu.slot_text("Slot 2", h, 0), "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 14:05")
	# local time: two hours east of UTC moves the clock and, past midnight, the day
	h["saved_unix"] = _unix(2026, 10, 12, 23, 30)
	t.eq(RpgSaveLoadMenu.slot_text("Slot 2", h, 120), "Slot 2 — Village · Lv 3 · 1:12 played · 13 Oct 01:30")
	t.eq(RpgSaveLoadMenu.slot_text("Slot 2", h, -60), "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 22:30")

func test_the_map_name_key_is_translated_and_falls_back_to_the_file_name(t) -> void:
	RpgStrings._add_missing_defaults()
	var h := {"map": "starter_map", "map_name": "MAP_STARTER_MAP", "level": 1, "playtime_s": 59.0}
	t.eq(RpgSaveLoadMenu.slot_text("Autosave", h, 0), "Autosave — Starter Map · Lv 1 · 0:00 played")
	var en := Translation.new()
	en.locale = "en"
	en.add_message(&"MAP_STARTER_MAP", &"The village")
	TranslationServer.add_translation(en)
	t.eq(RpgSaveLoadMenu.slot_text("Autosave", h, 0), "Autosave — The village · Lv 1 · 0:00 played")
	TranslationServer.remove_translation(en)

func test_an_old_save_without_a_time_shows_no_date_and_an_empty_slot_says_so(t) -> void:
	RpgStrings._add_missing_defaults()
	var old := {"map": "starter_map", "level": 2, "playtime_s": 3600.0, "gold": 5}
	t.eq(RpgSaveLoadMenu.slot_text("Slot 1", old, 0), "Slot 1 — Starter Map · Lv 2 · 1:00 played")
	t.eq(RpgSaveLoadMenu.slot_text("Slot 1", {}, 0), "Slot 1 — Empty")

func test_the_header_has_the_time_and_the_map_name_key(t) -> void:
	var state := Fixtures.install_state({})
	state.new_game()
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	save.dir = "user://test_saves_menu_%d" % Time.get_ticks_usec()
	t.ok(save.save(1))
	var h: Dictionary = save.header(1)
	t.ok(h.has("saved_unix") and h.has("map_name"))
	t.ok(abs(RpgUtil.to_int(h["saved_unix"]) - int(Time.get_unix_time_from_system())) <= 5)
	t.eq(h["map_name"], "", "no map is shown in a unit test")
	# headless: no picture is kept, and delete() leaves nothing behind
	t.ok(not FileAccess.file_exists(save.thumbnail_path(1)))
	save.delete(1)
	t.ok(not save.has_save(1))
	for f in DirAccess.get_files_at(save.dir):
		DirAccess.remove_absolute(save.dir + "/" + f)
	DirAccess.remove_absolute(save.dir)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_delete_removes_the_thumbnail_too(t) -> void:
	var state := Fixtures.install_state({})
	state.new_game()
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	save.dir = "user://test_saves_thumb_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(save.dir)
	var image := Image.create(4, 4, false, Image.FORMAT_RGBA8)
	image.save_png(save.thumbnail_path(2))
	t.ok(FileAccess.file_exists(save.thumbnail_path(2)))
	save.delete(2)
	t.ok(not FileAccess.file_exists(save.thumbnail_path(2)))
	DirAccess.remove_absolute(save.dir)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_the_map_root_names_its_key(t) -> void:
	var map := RpgMapRoot.new()
	map.map_id = &"village"
	t.eq(map.name_key(), "MAP_VILLAGE")
	map.display_name = "MAP_CUSTOM"
	t.eq(map.name_key(), "MAP_CUSTOM")
	map.free()

func test_the_slot_numbers_come_from_the_save_manager(t) -> void:
	t.eq(RpgSaveManager.SLOTS, 3)
	t.eq(RpgSaveManager.AUTOSAVE_SLOT, 0)
	var menu := RpgSaveLoadMenu.new()
	t.eq(menu._slots(), [0, 1, 2, 3] as Array[int])
	menu.free()
