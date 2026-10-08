class_name RpgSoundBank
extends RefCounted
## The sound slots of the game (res://rpggen/sound_bank.json: slot -> resource path, written by
## the builder from `config.sounds`). A slot that is not in the file is silent: `stream()` returns
## null and nothing is logged, so a pack without audio produces a clean log.

const BANK_PATH := "res://rpggen/sound_bank.json"

var _paths: Dictionary = {}
var _streams: Dictionary = {}
var _loaded := false

## Reads the bank once (or again after `reload`). A missing or malformed file is an empty bank.
func _ensure_loaded() -> void:
	if _loaded:
		return
	_loaded = true
	_paths = {}
	if not FileAccess.file_exists(BANK_PATH):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(BANK_PATH))
	if parsed is Dictionary:
		var table: Dictionary = parsed
		for slot: Variant in table.keys():
			var path := str(table[slot])
			if path != "":
				_paths[str(slot)] = path

func reload() -> void:
	_loaded = false
	_streams.clear()
	_ensure_loaded()

## Replaces the bank with `paths` (slot -> resource path); used by tests.
func set_paths(paths: Dictionary) -> void:
	_loaded = true
	_paths = paths.duplicate()
	_streams.clear()

func has_slot(slot: StringName) -> bool:
	_ensure_loaded()
	return _paths.has(str(slot))

func path_of(slot: StringName) -> String:
	_ensure_loaded()
	return str(_paths.get(str(slot), ""))

func slots() -> Array[String]:
	_ensure_loaded()
	var out: Array[String] = []
	for key: String in _paths.keys():
		out.append(key)
	return out

## The stream of a slot (loaded once), or null when the slot is unset or the file does not load.
func stream(slot: StringName) -> AudioStream:
	_ensure_loaded()
	var key := str(slot)
	if _streams.has(key):
		return _streams[key]
	var path := str(_paths.get(key, ""))
	var loaded: AudioStream = null
	if path != "" and ResourceLoader.exists(path):
		loaded = load(path) as AudioStream
	_streams[key] = loaded
	return loaded
