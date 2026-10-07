extends Node
## Autoload "SaveManager": three slots of checksummed JSON with a backup copy and migrations.

const SAVE_VERSION := 1
const SLOTS := 3

## Where saves live. A test may point it somewhere else.
var dir: String = "user://saves"
## {from_version: Callable(Dictionary) -> Dictionary}. Empty at v1; tests install a fake one.
var MIGRATIONS := {}

func _slot_path(slot: int) -> String:
	return dir.path_join("slot_%d.json" % slot)

func _tmp_path(slot: int) -> String:
	return dir.path_join("slot_%d.tmp" % slot)

func _backup_path(slot: int) -> String:
	return dir.path_join("slot_%d.backup.json" % slot)

static func checksum_of(data: Dictionary) -> String:
	var copy := data.duplicate(true)
	copy.erase("checksum")
	# Normalize through one JSON round trip: ints come back as floats after parsing, and the
	# checksum has to be the same for the data before writing and after reading.
	var once: Variant = JSON.parse_string(JSON.stringify(copy, "", true))
	return JSON.stringify(once, "", true).sha256_text()

## Copies the live player position into GameState so the save has it.
func _capture_world() -> bool:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	if state == null:
		return false
	if router != null and router.get("current_map") != null:
		var map := router.get("current_map") as RpgMapRoot
		state.current_map = map.scene_file_path
		var player := map.get_player()
		if player != null:
			state.player_position = player.global_position
			if "facing" in player:
				state.player_facing = str(player.get("facing"))
	return true

func _header(state: Node) -> Dictionary:
	return {
		"map": str(state.current_map).get_file().get_basename(),
		"playtime_s": state.playtime_s,
		"level": state.player_stats.level,
		"gold": state.gold,
		"saved_at": Time.get_datetime_string_from_system(true),
	}

func save(slot: int) -> bool:
	if slot < 1 or slot > SLOTS or not _capture_world():
		return false
	var state := RpgUtil.state()
	var data: Dictionary = state.to_dict()
	data["save_version"] = SAVE_VERSION
	data["header"] = _header(state)
	data["world"] = {
		"map": data["current_map"],
		"position": data["player_position"],
		"facing": data["player_facing"],
	}
	data["checksum"] = checksum_of(data)
	var text := JSON.stringify(data, "  ", true)
	DirAccess.make_dir_recursive_absolute(dir)
	var tmp := _tmp_path(slot)
	var file := FileAccess.open(tmp, FileAccess.WRITE)
	if file == null:
		push_error("[RPG-SAVE] cannot write %s (error %d)" % [tmp, FileAccess.get_open_error()])
		return false
	file.store_string(text)
	file.flush()
	file.close()
	var check := _read_verified(tmp)
	if check.is_empty() or str(check.get("checksum", "")) != str(data["checksum"]):
		DirAccess.remove_absolute(tmp)
		push_error("[RPG-SAVE] verification of %s failed" % tmp)
		return false
	var main := _slot_path(slot)
	if FileAccess.file_exists(main):
		DirAccess.copy_absolute(main, _backup_path(slot))
		DirAccess.remove_absolute(main)
	if DirAccess.rename_absolute(tmp, main) != OK:
		push_error("[RPG-SAVE] cannot move %s into place" % tmp)
		return false
	RpgUtil.emit(&"game_saved", [slot])
	return true

## The parsed file when it exists, parses and its checksum matches; otherwise {}.
func _read_verified(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var text := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		return {}
	var data: Dictionary = parsed
	if str(data.get("checksum", "")) != checksum_of(data):
		return {}
	return data

func has_save(slot: int) -> bool:
	return FileAccess.file_exists(_slot_path(slot)) or FileAccess.file_exists(_backup_path(slot))

func any_save() -> bool:
	for slot in range(1, SLOTS + 1):
		if has_save(slot):
			return true
	return false

## The slot's header, or {} when there is no readable save.
func header(slot: int) -> Dictionary:
	var data := _read_verified(_slot_path(slot))
	if data.is_empty():
		data = _read_verified(_backup_path(slot))
	if data.is_empty():
		return {}
	var h: Variant = data.get("header", {})
	return RpgUtil.restore_numbers(h) if h is Dictionary else {}

func delete(slot: int) -> void:
	for p in [_slot_path(slot), _backup_path(slot), _tmp_path(slot)]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## Applies MIGRATIONS[v] for v in save_version .. SAVE_VERSION-1.
func _migrate(d: Dictionary) -> Dictionary:
	var data := d
	var version := int(data.get("save_version", 0))
	while version < SAVE_VERSION:
		var step: Variant = MIGRATIONS.get(version)
		if step is Callable:
			data = (step as Callable).call(data)
		data["save_version"] = version + 1
		version += 1
	return data

## Loads the slot, falling back to its backup. Returns false when nothing usable was found or
## the save is from a newer version. The map change that follows runs in the background (watch
## SceneRouter.is_busy()).
func load(slot: int) -> bool:
	var data := _read_verified(_slot_path(slot))
	if data.is_empty():
		data = _read_verified(_backup_path(slot))
		if data.is_empty():
			return false
		RpgUtil.notify("Save was damaged; loaded backup.")
	data = RpgUtil.restore_numbers(data)
	var version := int(data.get("save_version", 0))
	if version > SAVE_VERSION:
		RpgUtil.notify("Save from newer version")
		return false
	if version < SAVE_VERSION:
		data = _migrate(data)
	var state := RpgUtil.state()
	if state == null:
		return false
	state.from_dict(data)
	var router := RpgUtil.router()
	if router != null:
		router.reload_from_state()
	RpgUtil.emit(&"game_loaded", [slot])
	return true
