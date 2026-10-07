extends RefCounted
## SaveManager (T6.09). Saves go to a throwaway folder under user://.

const Fixtures := preload("../lib/fixtures.gd")

var _dirs: Array[String] = []

func _setup() -> Array:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion", 5)})
	state.new_game()
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	var dir := "user://test_saves_%d_%d" % [Time.get_ticks_usec(), _dirs.size()]
	_dirs.append(dir)
	save.dir = dir
	return [state, save, dir]

func _cleanup(dir: String) -> void:
	for f in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir + "/" + f)
	DirAccess.remove_absolute(dir)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_round_trip(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 123
	state.inventory.add(&"potion", 7)
	state.set_flag("chest_1", "opened", true)
	state.player_position = Vector2(40, 50)
	var events := []
	RpgUtil.events().game_saved.connect(func(slot: int) -> void: events.append(["saved", slot]))
	RpgUtil.events().game_loaded.connect(func(slot: int) -> void: events.append(["loaded", slot]))
	t.ok(save.save(1))
	t.ok(save.has_save(1))
	t.ok(not save.has_save(2))
	state.gold = 0
	state.inventory.slots.clear()
	state.flags.clear()
	t.ok(save.load(1))
	t.eq(state.gold, 123)
	t.eq(state.inventory.count(&"potion"), 7)
	t.eq(state.get_flag("chest_1", "opened"), true)
	t.eq(events, [["saved", 1], ["loaded", 1]])
	_cleanup(ctx[2])

func test_header_and_delete(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 9
	t.eq(save.header(1), {})
	save.save(1)
	var h: Dictionary = save.header(1)
	t.eq(h["gold"], 9)
	t.eq(h["level"], 1)
	t.ok(h.has("map") and h.has("playtime_s") and h.has("saved_at"))
	t.ok(save.any_save())
	save.delete(1)
	t.ok(not save.has_save(1))
	t.eq(save.header(1), {})
	t.ok(not save.any_save())
	_cleanup(ctx[2])

func test_slot_numbers_are_checked(t) -> void:
	var ctx := _setup()
	var save: Node = ctx[1]
	t.ok(not save.save(-1))
	t.ok(not save.save(4))
	t.ok(save.save(0), "slot 0 is the autosave slot")
	t.ok(save.has_save(0) and not save.has_save(1))
	t.ok(not save.load(2), "no file")
	_cleanup(ctx[2])

func test_a_corrupted_main_file_falls_back_to_the_backup(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 11
	save.save(1)
	state.gold = 22
	save.save(1)  # the first save is now the backup
	var f := FileAccess.open(ctx[2] + "/slot_1.json", FileAccess.WRITE)
	f.store_string("{ this is not json")
	f.close()
	var notes := []
	RpgUtil.events().notify.connect(func(text: String) -> void: notes.append(text))
	t.ok(save.load(1))
	t.eq(state.gold, 11, "the backup holds the previous save")
	t.eq(notes, ["Save was damaged; loaded backup."])
	t.eq(save.header(1)["gold"], 11)
	_cleanup(ctx[2])

func test_a_tampered_checksum_is_rejected(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 5
	save.save(1)
	var path: String = ctx[2] + "/slot_1.json"
	var text := FileAccess.get_file_as_string(path).replace('"gold": 5', '"gold": 5000')
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(text)
	f.close()
	state.gold = 1
	t.ok(not save.load(1), "no backup exists, so loading fails")
	t.eq(state.gold, 1)
	t.eq(save.header(1), {})
	_cleanup(ctx[2])

func test_a_version_0_save_migrates(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 7
	save.save(1)
	# Rewrite the file as a "version 0" save whose gold lives under an old key.
	var path: String = ctx[2] + "/slot_1.json"
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	data["save_version"] = 0
	data["money"] = data["gold"]
	data.erase("gold")
	data["checksum"] = save.checksum_of(data)
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "  ", true))
	f.close()
	save.MIGRATIONS = {0: func(d: Dictionary) -> Dictionary:
		d["gold"] = d["money"]
		d.erase("money")
		return d}
	state.gold = 0
	t.ok(save.load(1))
	t.eq(state.gold, 7)
	_cleanup(ctx[2])

func test_a_save_from_a_newer_version_is_refused(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 7
	save.save(1)
	var path: String = ctx[2] + "/slot_1.json"
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	data["save_version"] = save.SAVE_VERSION + 1
	data["checksum"] = save.checksum_of(data)
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "  ", true))
	f.close()
	var notes := []
	RpgUtil.events().notify.connect(func(text: String) -> void: notes.append(text))
	state.gold = 0
	t.ok(not save.load(1))
	t.eq(state.gold, 0)
	t.eq(notes, ["Save from newer version"])
	_cleanup(ctx[2])

func test_save_leaves_no_temp_file(t) -> void:
	var ctx := _setup()
	var save: Node = ctx[1]
	save.save(2)
	save.save(2)
	var files := DirAccess.get_files_at(ctx[2])
	t.ok(not files.has("slot_2.tmp"))
	t.ok(files.has("slot_2.json") and files.has("slot_2.backup.json"))
	_cleanup(ctx[2])

# ---------------------------------------------------------------- autosave (T11.22)

func test_the_autosave_slot_is_separate_and_counts_as_a_save(t) -> void:
	var ctx := _setup()
	var state: Node = ctx[0]
	var save: Node = ctx[1]
	state.gold = 77
	t.ok(save.save(save.AUTOSAVE_SLOT))
	t.ok(save.any_save(), "Continue is available with only an autosave")
	t.ok(not save.has_save(1) and not save.has_save(2) and not save.has_save(3))
	t.eq(save.header(0)["gold"], 77)
	state.gold = 0
	t.ok(save.load(save.AUTOSAVE_SLOT))
	t.eq(state.gold, 77)
	_cleanup(ctx[2])

func test_autosave_needs_a_settled_map_and_waits_between_saves(t) -> void:
	var ctx := _setup()
	var save: Node = ctx[1]
	# No SceneRouter in this fixture: nothing to autosave, and nothing breaks.
	t.ok(not save.can_autosave())
	t.ok(not save.autosave())
	t.ok(not save.has_save(0))
	_cleanup(ctx[2])

func test_latest_save_slot_picks_an_autosave_that_is_newer(t) -> void:
	var ctx := _setup()
	var save: Node = ctx[1]
	t.eq(RpgDefeatPolicy.latest_save_slot(), -1, "no save at all")
	t.ok(save.save(2))
	t.eq(RpgDefeatPolicy.latest_save_slot(), 2)
	OS.delay_msec(1100)  # saved_at has a resolution of one second
	t.ok(save.save(save.AUTOSAVE_SLOT))
	t.eq(RpgDefeatPolicy.latest_save_slot(), 0, "the newer autosave wins (Continue and game over use it)")
	_cleanup(ctx[2])
