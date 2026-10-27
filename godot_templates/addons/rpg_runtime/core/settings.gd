class_name RpgSettingsStore
extends Node
## Autoload "RpgSettings": volumes, fullscreen, text speed, UI scale and input remapping,
## stored in user://settings.cfg.

signal changed
## The kind of device used last changed (RpgInputGlyphs.KEYBOARD or a pad layout, T12.55).
signal input_device_changed(device: String)

const TEXT_SPEEDS := {"slow": 20.0, "normal": 40.0, "fast": 80.0, "instant": 0.0}
const UI_SCALES := [1.0, 1.25, 1.5]
const BUSES: Array[String] = ["master", "music", "sfx", "ui"]
const BUS_NAMES := {"master": "Master", "music": "Music", "sfx": "SFX", "ui": "UI"}
const DEFAULT_VOLUME := 0.8

var path: String = "user://settings.cfg"
var volumes := {"master": DEFAULT_VOLUME, "music": DEFAULT_VOLUME, "sfx": DEFAULT_VOLUME, "ui": DEFAULT_VOLUME}
var fullscreen := false
var text_speed := "normal"
var ui_scale := 1.0
var autosave := true  # an automatic save when a map is entered (SaveManager.autosave)
var screen_shake := true  # camera shake and hit-stop of the action RPG
var language := ""  # a locale of generated/i18n ("de"), or "" for the system's (T12.56)
var day_night := false  # the time-of-day cycle of outdoor maps (T12.62), off by default
var minimap := true  # the HUD minimap (T12.64)
var quest_tracker := true  # the HUD's quest tracker (1.5.0)

var _defaults := {}  # action -> Array[InputEvent], captured before user bindings are applied
## The kind of device used last: prompts show its glyphs (not saved; a keyboard at start).
var input_device: String = RpgInputGlyphs.KEYBOARD

func _ready() -> void:
	load_settings()
	apply()

func _input(event: InputEvent) -> void:
	note_input(event)

## Remembers the device `event` comes from; emits `input_device_changed` when it is a new one.
func note_input(event: InputEvent) -> void:
	var device := RpgInputGlyphs.device_of(event)
	if device != "" and device != input_device:
		input_device = device
		input_device_changed.emit(device)

## Characters per second; 0 means instant.
func text_cps() -> float:
	return RpgUtil.to_float(TEXT_SPEEDS.get(text_speed, 40.0))

func set_volume(bus: String, value: float) -> void:
	if not BUSES.has(bus):
		return
	volumes[bus] = clampf(value, 0.0, 1.0)
	_apply_volume(bus)
	changed.emit()

func set_fullscreen(on: bool) -> void:
	fullscreen = on
	_apply_fullscreen()
	changed.emit()

func set_text_speed(speed: String) -> void:
	if TEXT_SPEEDS.has(speed):
		text_speed = speed
		changed.emit()

func set_minimap(on: bool) -> void:
	minimap = on
	changed.emit()

func set_quest_tracker(on: bool) -> void:
	quest_tracker = on
	changed.emit()

func set_day_night(on: bool) -> void:
	day_night = on
	changed.emit()

func set_screen_shake(on: bool) -> void:
	screen_shake = on
	changed.emit()

func set_autosave(on: bool) -> void:
	autosave = on
	changed.emit()

## Switches the game's language; "" follows the system. Labels whose text is a key change at
## once; screens that set their text in code refresh on NOTIFICATION_TRANSLATION_CHANGED.
func set_language(locale: String) -> void:
	language = locale
	_apply_language()
	changed.emit()

## The locale in effect for `language`.
func effective_locale() -> String:
	return language if language != "" else OS.get_locale()

func set_ui_scale(scale: float) -> void:
	ui_scale = scale if UI_SCALES.has(scale) else 1.0
	_apply_ui_scale()
	changed.emit()

func apply() -> void:
	for bus in BUSES:
		_apply_volume(bus)
	_apply_fullscreen()
	_apply_ui_scale()
	_apply_language()

func _apply_language() -> void:
	if TranslationServer.get_locale() != effective_locale():
		TranslationServer.set_locale(effective_locale())

func _apply_volume(bus: String) -> void:
	var bus_name: String = BUS_NAMES[bus]
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	var v: float = volumes[bus]
	AudioServer.set_bus_volume_db(idx, linear_to_db(v) if v > 0.0 else -80.0)

func _apply_fullscreen() -> void:
	if DisplayServer.get_name() == "headless":
		return
	var mode := DisplayServer.WINDOW_MODE_FULLSCREEN if fullscreen else DisplayServer.WINDOW_MODE_WINDOWED
	if DisplayServer.window_get_mode() != mode:
		DisplayServer.window_set_mode(mode)

func _apply_ui_scale() -> void:
	if is_inside_tree():
		get_tree().root.content_scale_factor = ui_scale

# ---------------------------------------------------------------- files

func save_settings() -> bool:
	var cfg := ConfigFile.new()
	for bus in BUSES:
		cfg.set_value("audio", bus, volumes[bus])
	cfg.set_value("video", "fullscreen", fullscreen)
	cfg.set_value("text", "speed", text_speed)
	cfg.set_value("text", "language", language)
	cfg.set_value("access", "ui_scale", ui_scale)
	cfg.set_value("game", "autosave", autosave)
	cfg.set_value("game", "screen_shake", screen_shake)
	cfg.set_value("game", "day_night", day_night)
	cfg.set_value("game", "minimap", minimap)
	cfg.set_value("game", "quest_tracker", quest_tracker)
	var bindings := _stored_bindings()
	for action: String in bindings.keys():
		cfg.set_value("input", action, bindings[action])
	return cfg.save(path) == OK

func load_settings() -> void:
	_capture_defaults()
	var cfg := ConfigFile.new()
	if cfg.load(path) != OK:
		return
	for bus in BUSES:
		volumes[bus] = clampf(RpgUtil.to_float(cfg.get_value("audio", bus, DEFAULT_VOLUME)), 0.0, 1.0)
	fullscreen = RpgUtil.to_bool(cfg.get_value("video", "fullscreen", false))
	var speed := str(cfg.get_value("text", "speed", "normal"))
	text_speed = speed if TEXT_SPEEDS.has(speed) else "normal"
	language = str(cfg.get_value("text", "language", ""))
	var scale := RpgUtil.to_float(cfg.get_value("access", "ui_scale", 1.0))
	ui_scale = scale if UI_SCALES.has(scale) else 1.0
	autosave = RpgUtil.to_bool(cfg.get_value("game", "autosave", true))
	screen_shake = RpgUtil.to_bool(cfg.get_value("game", "screen_shake", true))
	day_night = RpgUtil.to_bool(cfg.get_value("game", "day_night", false))
	minimap = RpgUtil.to_bool(cfg.get_value("game", "minimap", true))
	quest_tracker = RpgUtil.to_bool(cfg.get_value("game", "quest_tracker", true))
	if cfg.has_section("input"):
		for action in cfg.get_section_keys("input"):
			if not InputMap.has_action(action):
				continue
			var events: Array[InputEvent] = []
			var raws: Array = cfg.get_value("input", action, [])
			for raw: Variant in raws:
				var ev := deserialize_event(raw)
				if ev != null:
					events.append(ev)
			if events.is_empty():
				continue
			# User bindings replace the project defaults for that action.
			InputMap.action_erase_events(action)
			for ev in events:
				InputMap.action_add_event(action, ev)

# ---------------------------------------------------------------- input

func _capture_defaults() -> void:
	if not _defaults.is_empty():
		return
	for action in InputMap.get_actions():
		if String(action).begins_with("ui_"):
			continue
		_defaults[String(action)] = InputMap.action_get_events(action).duplicate()

## Actions whose current events differ from the project defaults.
func _stored_bindings() -> Dictionary:
	var out := {}
	for action: String in _defaults.keys():
		if not InputMap.has_action(action):
			continue
		var now := InputMap.action_get_events(action)
		var before: Array[InputEvent] = _defaults[action]
		if not _same_events(now, before):
			var list: Array = []
			for ev in now:
				var s := serialize_event(ev)
				if not s.is_empty():
					list.append(s)
			out[action] = list
	return out

func _same_events(a: Array[InputEvent], b: Array[InputEvent]) -> bool:
	if a.size() != b.size():
		return false
	for i in a.size():
		if not a[i].is_match(b[i], true):
			return false
	return true

## Actions that can be remapped (the project's own, not the built-in ui_* ones).
func remappable_actions() -> Array[String]:
	_capture_defaults()
	var out: Array[String] = []
	for action: String in _defaults.keys():
		out.append(action)
	out.sort()
	return out

## Replaces `old_event` of `action` by `new_event` (appends when old_event is null) and saves.
func rebind(action: String, old_event: InputEvent, new_event: InputEvent) -> bool:
	if not InputMap.has_action(action) or new_event == null:
		return false
	_capture_defaults()
	if old_event != null:
		for ev in InputMap.action_get_events(action):
			if ev.is_match(old_event, true):
				InputMap.action_erase_event(action, ev)
				break
	InputMap.action_add_event(action, new_event)
	changed.emit()
	return save_settings()

func reset_bindings() -> void:
	_capture_defaults()
	for action: String in _defaults.keys():
		InputMap.action_erase_events(action)
		for ev: InputEvent in _defaults[action]:
			InputMap.action_add_event(action, ev)
	changed.emit()
	save_settings()

static func serialize_event(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var k := ev as InputEventKey
		var code := k.physical_keycode if k.physical_keycode != 0 else k.keycode
		return {"type": "key", "physical": int(code)}
	if ev is InputEventJoypadButton:
		return {"type": "joy_button", "index": int((ev as InputEventJoypadButton).button_index)}
	if ev is InputEventJoypadMotion:
		var m := ev as InputEventJoypadMotion
		return {"type": "joy_axis", "axis": int(m.axis), "value": m.axis_value}
	if ev is InputEventMouseButton:
		return {"type": "mouse_button", "index": int((ev as InputEventMouseButton).button_index)}
	return {}

static func deserialize_event(d: Variant) -> InputEvent:
	if not (d is Dictionary):
		return null
	var data: Dictionary = d
	match str(data.get("type", "")):
		"key":
			var k := InputEventKey.new()
			k.physical_keycode = RpgUtil.to_int(data.get("physical", 0)) as Key
			return k
		"joy_button":
			var b := InputEventJoypadButton.new()
			b.button_index = RpgUtil.to_int(data.get("index", 0)) as JoyButton
			return b
		"joy_axis":
			var m := InputEventJoypadMotion.new()
			m.axis = RpgUtil.to_int(data.get("axis", 0)) as JoyAxis
			m.axis_value = RpgUtil.to_float(data.get("value", 1.0))
			return m
		"mouse_button":
			var mb := InputEventMouseButton.new()
			mb.button_index = RpgUtil.to_int(data.get("index", 1)) as MouseButton
			return mb
	return null

## Short text for a binding ("E", "Joypad Button 0").
static func event_text(ev: InputEvent) -> String:
	if ev is InputEventKey:
		var k := ev as InputEventKey
		var code := k.physical_keycode if k.physical_keycode != 0 else k.keycode
		if DisplayServer.get_name() == "headless":  # no keyboard layout to ask
			return OS.get_keycode_string(code)
		return OS.get_keycode_string(DisplayServer.keyboard_get_keycode_from_physical(code))
	return ev.as_text()
