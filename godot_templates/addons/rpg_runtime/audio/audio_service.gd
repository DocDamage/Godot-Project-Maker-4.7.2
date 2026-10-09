class_name RpgAudio
extends Node
## Music with a crossfade, a pool of sound-effect players and a UI sound player. Not an autoload:
## boot creates it as a child of SceneRouter so it survives scene changes.

const INDEX_PATH := "res://rpggen/audio_index.json"
## File -> {start_ms, end_ms} of the tracks that loop (written by the builder from the catalog's
## `audio.loop`, `loop_start_ms` and `loop_end_ms`). A project made before 1.1 has no such file.
const LOOPS_PATH := "res://rpggen/audio_loops.json"
const SFX_POOL := 8
const SILENT_DB := -60.0

var _music: Array[AudioStreamPlayer] = []
var _active := 0
var _sfx: Array[AudioStreamPlayer] = []
var _ui: AudioStreamPlayer
var _index: Dictionary = {}
var _index_loaded := false
var _loops: Dictionary = {}
var _loops_loaded := false
var _tween: Tween = null
var current_music_id := ""
## The sound slots of the game (res://rpggen/sound_bank.json). Unset slots are silent.
var bank := RpgSoundBank.new()
## Events (slot played when the signal fires) wired by connect_events; the player's footsteps,
## the menu sounds and the map music are driven by their own scripts.
const EVENT_SLOTS := {
	&"item_added": &"sfx_pickup",
	&"player_damaged": &"sfx_hit",
	&"level_up": &"sfx_levelup",
	&"game_saved": &"sfx_save",
	&"chest_opened": &"sfx_chest",
	&"door_used": &"sfx_door",
	&"attack_started": &"sfx_attack",
}
var _event_bus: Node = null

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for i in 2:
		var p := AudioStreamPlayer.new()
		p.name = "Music%d" % i
		p.bus = "Music"
		p.volume_db = SILENT_DB
		add_child(p)
		_music.append(p)
	for i in SFX_POOL:
		var p := AudioStreamPlayer.new()
		p.name = "Sfx%d" % i
		p.bus = "SFX"
		add_child(p)
		_sfx.append(p)
	_ui = AudioStreamPlayer.new()
	_ui.name = "Ui"
	_ui.bus = "UI"
	add_child(_ui)
	connect_events(RpgUtil.events())

## Lets go of every stream so that none is still in use when the game quits.
func _exit_tree() -> void:
	if _tween != null:
		_tween.kill()
	for p in _music + _sfx:
		p.stop()
		p.stream = null
	if _ui != null:
		_ui.stop()
		_ui.stream = null
	bank.set_paths({})
	_index.clear()

## Connects the event signals of EVENT_SLOTS on `bus` (the Events autoload; a stand-in in tests).
func connect_events(bus: Node) -> void:
	if bus == null:
		return
	_event_bus = bus
	for signal_name: StringName in EVENT_SLOTS.keys():
		if bus.has_signal(signal_name):
			var slot: StringName = EVENT_SLOTS[signal_name]
			# Every one of these signals has at most two arguments; the sound ignores them.
			bus.connect(signal_name, func(a: Variant = null, _b: Variant = null) -> void: _on_event(slot, signal_name, a))

func _on_event(slot: StringName, signal_name: StringName, first_arg: Variant = null) -> void:
	# The automatic save (slot 0) is quiet; it shows a toast instead.
	if signal_name == &"game_saved" and first_arg is int and RpgUtil.to_int(first_arg) == 0:
		return
	# No pickup sound while no map is shown (starting items, loading a save) or one is loading.
	if signal_name == &"item_added" and not _map_is_live():
		return
	play(slot)

func _map_is_live() -> bool:
	var router := RpgUtil.router()
	if router == null:
		return true
	return router.get("current_map") != null and not router.is_busy()

## Stream for an asset id from the catalog-derived index, or null.
func stream_for(asset_id: String) -> AudioStream:
	if not _index_loaded:
		_index_loaded = true
		if FileAccess.file_exists(INDEX_PATH):
			var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(INDEX_PATH))
			if parsed is Dictionary:
				_index = parsed
	var path := str(_index.get(asset_id, ""))
	if path == "" or not ResourceLoader.exists(path):
		return null
	return load(path) as AudioStream

## Makes `stream` loop: from `end_ms` back to `start_ms` (0 for the end is the end of the track).
## A WAV stream loops between both points; an Ogg Vorbis or MP3 stream always plays to its end
## and comes back to the start point (their `loop_offset`).
static func apply_loop(stream: AudioStream, info: Dictionary) -> void:
	var start_s := maxf(0.0, RpgUtil.to_float(info.get("start_ms", 0)) / 1000.0)
	var end_s := RpgUtil.to_float(info.get("end_ms", 0)) / 1000.0
	if stream is AudioStreamWAV:
		var wav := stream as AudioStreamWAV
		var frames := roundi(wav.get_length() * wav.mix_rate)
		if frames <= 0:
			return
		var begin := clampi(roundi(start_s * wav.mix_rate), 0, frames - 1)
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = begin
		wav.loop_end = frames if end_s <= start_s else clampi(roundi(end_s * wav.mix_rate), begin + 1, frames)
	elif stream is AudioStreamOggVorbis:
		var ogg := stream as AudioStreamOggVorbis
		ogg.loop = true
		ogg.loop_offset = start_s
	elif stream is AudioStreamMP3:
		var mp3 := stream as AudioStreamMP3
		mp3.loop = true
		mp3.loop_offset = start_s

## The loop of the file at `path`, or {} when it does not loop.
func loop_of(path: String) -> Dictionary:
	if not _loops_loaded:
		_loops_loaded = true
		if FileAccess.file_exists(LOOPS_PATH):
			var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(LOOPS_PATH))
			if parsed is Dictionary:
				_loops = parsed
	var found: Variant = _loops.get(path, {})
	return found if found is Dictionary else {}

## Replaces the loops table (file -> {start_ms, end_ms}); used by tests.
func set_loops(table: Dictionary) -> void:
	_loops_loaded = true
	_loops = table.duplicate(true)

func _resolve(what: Variant) -> AudioStream:
	if what is AudioStream:
		return what
	if what is String or what is StringName:
		var s := stream_for(str(what))
		if s == null:
			push_warning("[RPG-AUDIO] unknown audio asset '%s'" % str(what))
		return s
	return null

## Crossfades to `what` (an AudioStream or a catalog asset id). A null/unknown value fades out.
func play_music(what: Variant, fade: float = 0.5) -> void:
	var stream := _resolve(what)
	if _music.is_empty():
		return
	if _tween != null:
		_tween.kill()
	var old := _music[_active]
	_active = 1 - _active
	var fresh := _music[_active]
	_tween = create_tween().set_parallel(true)
	_tween.tween_property(old, "volume_db", SILENT_DB, fade)
	if stream != null:
		var loop := loop_of(stream.resource_path)
		if not loop.is_empty():
			apply_loop(stream, loop)
		fresh.stream = stream
		fresh.volume_db = SILENT_DB
		fresh.play()
		_tween.tween_property(fresh, "volume_db", 0.0, fade)
		current_music_id = str(what) if not (what is AudioStream) else ""
	else:
		current_music_id = ""
	_tween.chain().tween_callback(old.stop)

func play_sfx(stream: AudioStream, volume_db: float = 0.0, pitch_scale: float = 1.0) -> void:
	if stream == null:
		return
	for p in _sfx:
		if not p.playing:
			p.stream = stream
			p.volume_db = volume_db
			p.pitch_scale = pitch_scale
			p.play()
			return
	# Every player is busy: steal the first one.
	_sfx[0].stream = stream
	_sfx[0].volume_db = volume_db
	_sfx[0].pitch_scale = pitch_scale
	_sfx[0].play()

## Plays the sound of a slot on the SFX bus. An unset slot is a silent no-op (no warning).
func play(slot: StringName, volume_db: float = 0.0, pitch_scale: float = 1.0) -> void:
	play_sfx(bank.stream(slot), volume_db, pitch_scale)

## Plays the sound of a slot on the UI bus (silent no-op when unset).
func play_ui_slot(slot: StringName) -> void:
	play_ui(bank.stream(slot))

## Crossfades to the music of a slot (silent no-op when unset).
func play_music_slot(slot: StringName, fade: float = 0.5) -> void:
	var stream := bank.stream(slot)
	if stream != null:
		play_music(stream, fade)

func play_ui(stream: AudioStream) -> void:
	if stream == null or _ui == null:
		return
	_ui.stream = stream
	_ui.play()

func sfx_busy_count() -> int:
	var n := 0
	for p in _sfx:
		if p.playing:
			n += 1
	return n
