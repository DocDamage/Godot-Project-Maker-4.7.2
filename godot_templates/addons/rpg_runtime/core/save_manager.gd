class_name RpgSaveManager
extends Node
## Autoload "SaveManager": three slots of checksummed JSON with a backup copy and migrations.

const SAVE_VERSION := 1
const SLOTS := 3
## The extra slot of the automatic save, beside the manual slots 1 to SLOTS (their numbers do not
## shift, so existing saves stay valid).
const AUTOSAVE_SLOT := 0
## "No save" for functions that answer with a slot number.
const NO_SLOT := -1
## The size of the picture kept beside a slot.
const THUMB_SIZE := Vector2i(160, 90)
## At least this long between two automatic saves.
const AUTOSAVE_COOLDOWN_MS := 10000

## Where saves live. A test may point it somewhere else.
var dir: String = "user://saves"
var _last_autosave_ms := -AUTOSAVE_COOLDOWN_MS
## {from_version: Callable(Dictionary) -> Dictionary}. Empty at v1; tests install a fake one.
var MIGRATIONS := {}

func _slot_path(slot: int) -> String:
	return dir.path_join("slot_%d.json" % slot)

func _tmp_path(slot: int) -> String:
	return dir.path_join("slot_%d.tmp" % slot)

func _backup_path(slot: int) -> String:
	return dir.path_join("slot_%d.backup.json" % slot)

## The 160x90 picture saved beside a slot (absent for saves made headless or before it existed).
func thumbnail_path(slot: int) -> String:
	return dir.path_join("slot_%d.png" % slot)

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
		var map := router.current_map
		state.current_map = map.scene_file_path
		var player := map.get_player()
		if player != null:
			state.player_position = player.global_position
			if "facing" in player:
				state.player_facing = str(player.get("facing"))
	return true

func _header(state: RpgGameState) -> Dictionary:
	return {
		"map": str(state.current_map).get_file().get_basename(),
		"map_name": _map_name_key(),
		"playtime_s": state.playtime_s,
		"level": state.player_stats.level,
		"gold": state.gold,
		"saved_at": Time.get_datetime_string_from_system(true),
		"saved_unix": int(Time.get_unix_time_from_system()),
	}

## The translation key of the current map's name ("" when no map is shown).
func _map_name_key() -> String:
	var router := RpgUtil.router()
	if router != null and router.current_map != null:
		return router.current_map.name_key()
	return ""

## Keeps a 160x90 picture of the screen beside the slot (not when running headless).
func _save_thumbnail(slot: int) -> void:
	if DisplayServer.get_name() == "headless":
		return
	var viewport := get_viewport()
	if viewport == null:
		return
	var texture: ViewportTexture = viewport.get_texture()
	if texture == null:
		return
	var image := texture.get_image()
	if image == null or image.is_empty():
		return
	image.resize(THUMB_SIZE.x, THUMB_SIZE.y, Image.INTERPOLATE_BILINEAR)
	image.save_png(thumbnail_path(slot))

func _ready() -> void:
	var bus := RpgUtil.events()
	if bus != null:
		bus.map_entered.connect(_on_map_entered)

## An automatic save one frame after a map is entered, so that the map's persistent entities are
## already in place. This also covers returning to the map after a battle.
func _on_map_entered(_map_id: StringName) -> void:
	await get_tree().process_frame
	autosave()

## True when an automatic save may happen now: the setting is on, a map is shown and settled (no
## fade, no battle, no dialogue, no sequence), the player is alive and the last one was 10 or more seconds ago.
func can_autosave() -> bool:
	var settings := RpgUtil.settings()
	if settings != null and not RpgUtil.to_bool(settings.get("autosave")):
		return false
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	if state == null or router == null or router.get("current_map") == null or router.is_busy():
		return false
	var combat := router.combat
	if combat != null and combat.is_in_combat():
		return false
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box != null and box.call("is_open"):
		return false
	if RpgSequenceRunner.running():
		return false
	if state.player_stats.hp <= 0:
		return false
	return Time.get_ticks_msec() - _last_autosave_ms >= AUTOSAVE_COOLDOWN_MS

## Saves into the autosave slot (the normal save path: temp file, verify, backup, rename) and
## shows a small toast. False when it may not happen now or the save failed.
func autosave() -> bool:
	if not can_autosave():
		return false
	if not save(AUTOSAVE_SLOT):
		return false
	_last_autosave_ms = Time.get_ticks_msec()
	RpgUtil.notify(tr("UI_AUTOSAVED"))
	return true

## Lets the next autosave happen at once (tests).
func reset_autosave_cooldown() -> void:
	_last_autosave_ms = -AUTOSAVE_COOLDOWN_MS

func save(slot: int) -> bool:
	if slot < AUTOSAVE_SLOT or slot > SLOTS or not _capture_world():
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
		# Only a save that verifies becomes the backup: a damaged main file must never replace
		# the last good one.
		if _read_verified(main).is_empty():
			push_warning("[RPG-SAVE] skipped backing up a damaged save")
		else:
			DirAccess.copy_absolute(main, _backup_path(slot))
	if not _move_into_place(tmp, main):
		push_error("[RPG-SAVE] cannot move %s into place" % tmp)
		return false
	_save_thumbnail(slot)
	RpgUtil.emit(&"game_saved", [slot])
	return true

## Moves the verified temporary file onto the slot. DirAccess.rename_absolute replaces an
## existing file (docs/godot_api_verified.md, probe_rename_replace.gd), so the main file is never
## missing in between; if a platform refuses, the main file goes first and the backup covers
## the gap.
func _move_into_place(from: String, to: String) -> bool:
	if DirAccess.rename_absolute(from, to) == OK:
		return true
	if FileAccess.file_exists(to):
		DirAccess.remove_absolute(to)
	return DirAccess.rename_absolute(from, to) == OK

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
	for slot in range(AUTOSAVE_SLOT, SLOTS + 1):
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
	for p: String in [_slot_path(slot), _backup_path(slot), _tmp_path(slot), thumbnail_path(slot)]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## Applies MIGRATIONS[v] for v in save_version .. SAVE_VERSION-1.
func _migrate(d: Dictionary) -> Dictionary:
	var data := d
	var version := RpgUtil.to_int(data.get("save_version", 0))
	while version < SAVE_VERSION:
		var step: Variant = MIGRATIONS.get(version)
		if step is Callable:
			var migrate: Callable = step
			data = migrate.call(data)
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
		RpgUtil.notify(tr("UI_SAVE_DAMAGED_LOADED_BACKUP"))
	data = RpgUtil.restore_numbers(data)
	var version := RpgUtil.to_int(data.get("save_version", 0))
	if version > SAVE_VERSION:
		RpgUtil.notify(tr("UI_SAVE_FROM_NEWER_VERSION"))
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
