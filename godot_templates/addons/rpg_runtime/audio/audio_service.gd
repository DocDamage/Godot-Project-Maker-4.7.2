class_name RpgAudio
extends Node
## Music with a crossfade, a pool of sound-effect players and a UI sound player. Not an autoload:
## boot creates it as a child of SceneRouter so it survives scene changes.

const INDEX_PATH := "res://rpggen/audio_index.json"
const SFX_POOL := 8
const SILENT_DB := -60.0

var _music: Array[AudioStreamPlayer] = []
var _active := 0
var _sfx: Array[AudioStreamPlayer] = []
var _ui: AudioStreamPlayer
var _index: Dictionary = {}
var _index_loaded := false
var _tween: Tween = null
var current_music_id := ""

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
		fresh.stream = stream
		fresh.volume_db = SILENT_DB
		fresh.play()
		_tween.tween_property(fresh, "volume_db", 0.0, fade)
		current_music_id = str(what) if not (what is AudioStream) else ""
	else:
		current_music_id = ""
	_tween.chain().tween_callback(old.stop)

func play_sfx(stream: AudioStream) -> void:
	if stream == null:
		return
	for p in _sfx:
		if not p.playing:
			p.stream = stream
			p.play()
			return
	# Every player is busy: steal the first one.
	_sfx[0].stream = stream
	_sfx[0].play()

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
