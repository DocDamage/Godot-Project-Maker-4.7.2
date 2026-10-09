class_name RpgSoundBank
extends RefCounted
## The sound slots of the game (res://rpggen/sound_bank.json: slot -> resource path, written by
## the builder from `config.sounds`). A slot that is not in the file is silent: `stream()` returns
## null and nothing is logged, so a pack without audio produces a clean log.

const BANK_PATH := "res://rpggen/sound_bank.json"
## Ground asset id -> surface ("grass", "stone", ...), written by the builder from the assets'
## `surface:<name>` tags. A project made before 1.1 has no such file: every step is `sfx_step`.
const SURFACES_PATH := "res://rpggen/surfaces.json"
const STEP_SLOT := &"sfx_step"

var _paths: Dictionary = {}
var _surfaces: Dictionary = {}
var _has_step_surfaces := false
var _streams: Dictionary = {}
var _loaded := false

## Reads the bank once (or again after `reload`). A missing or malformed file is an empty bank.
func _ensure_loaded() -> void:
	if _loaded:
		return
	_loaded = true
	_paths = {}
	_surfaces = {}
	if FileAccess.file_exists(BANK_PATH):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(BANK_PATH))
		if parsed is Dictionary:
			var table: Dictionary = parsed
			for slot: Variant in table.keys():
				var path := str(table[slot])
				if path != "":
					_paths[str(slot)] = path
	if FileAccess.file_exists(SURFACES_PATH):
		var parsed_surfaces: Variant = JSON.parse_string(FileAccess.get_file_as_string(SURFACES_PATH))
		if parsed_surfaces is Dictionary:
			_surfaces = parsed_surfaces
	_note_step_surfaces()

func _note_step_surfaces() -> void:
	_has_step_surfaces = false
	for key: String in _paths.keys():
		if key.begins_with("sfx_step_"):
			_has_step_surfaces = true

func reload() -> void:
	_loaded = false
	_streams.clear()
	_ensure_loaded()

## Replaces the bank with `paths` (slot -> resource path); used by tests.
func set_paths(paths: Dictionary) -> void:
	_loaded = true
	_paths = paths.duplicate()
	_streams.clear()
	_note_step_surfaces()

## Replaces the surfaces table (asset id -> surface); used by tests.
func set_surfaces(table: Dictionary) -> void:
	_ensure_loaded()
	_surfaces = table.duplicate()

## The surface of a ground asset ("" when it has none).
func surface_of(asset_id: String) -> String:
	_ensure_loaded()
	return str(_surfaces.get(asset_id, ""))

## True when the bank has a footstep for some surface (else nobody needs to look at the ground).
func has_step_surfaces() -> bool:
	_ensure_loaded()
	return _has_step_surfaces

## The footstep slot for ground of `surface`: `sfx_step_<surface>` when the bank has it, else
## `sfx_step`.
func step_slot(surface: String) -> StringName:
	if surface != "" and has_slot(StringName("sfx_step_" + surface)):
		return StringName("sfx_step_" + surface)
	return STEP_SLOT

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
