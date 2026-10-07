class_name RpgSettingsMenu
extends Control
## Volume sliders, fullscreen, text speed, UI scale and the Controls remap list.

const SPEEDS := ["slow", "normal", "fast", "instant"]
const SCALES := [1.0, 1.25, 1.5]
const SLIDERS := {"MasterSlider": "master", "MusicSlider": "music", "SfxSlider": "sfx", "UiSlider": "ui"}

var _capturing_action := ""
var _capturing_button: Button = null
var _capturing_old: InputEvent = null

func _settings() -> Node:
	return RpgUtil.settings()

func _ready() -> void:
	var s := _settings()
	for slider_name in SLIDERS.keys():
		var slider := get_node("%" + slider_name) as HSlider
		slider.min_value = 0.0
		slider.max_value = 1.0
		slider.step = 0.05
		slider.value = float(s.volumes[SLIDERS[slider_name]]) if s != null else 0.8
		slider.value_changed.connect(_on_volume.bind(SLIDERS[slider_name]))
	var fullscreen := get_node("%Fullscreen") as CheckButton
	fullscreen.button_pressed = s != null and s.fullscreen
	fullscreen.toggled.connect(_on_fullscreen)
	var speed := get_node("%TextSpeed") as OptionButton
	speed.clear()
	for sp in SPEEDS:
		speed.add_item(tr("UI_SPEED_" + sp.to_upper()))
	speed.select(SPEEDS.find(s.text_speed) if s != null else 1)
	speed.item_selected.connect(_on_speed)
	var scale := get_node("%UiScale") as OptionButton
	scale.clear()
	for sc in SCALES:
		scale.add_item("%d%%" % int(sc * 100.0))
	scale.select(maxi(0, SCALES.find(s.ui_scale)) if s != null else 0)
	scale.item_selected.connect(_on_scale)
	(get_node("%Back") as Button).pressed.connect(close)
	_build_controls()
	_wire_focus()
	_focus_first.call_deferred()

func _on_volume(value: float, bus: String) -> void:
	var s := _settings()
	if s != null:
		s.set_volume(bus, value)

func _on_fullscreen(on: bool) -> void:
	var s := _settings()
	if s != null:
		s.set_fullscreen(on)

func _on_speed(index: int) -> void:
	var s := _settings()
	if s != null:
		s.set_text_speed(SPEEDS[index])

func _on_scale(index: int) -> void:
	var s := _settings()
	if s != null:
		s.set_ui_scale(SCALES[index])

func _build_controls() -> void:
	var list := get_node("%Controls") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	var s := _settings()
	if s == null:
		return
	for action in s.remappable_actions():
		var row := HBoxContainer.new()
		row.name = "Row_%s" % action
		var label := Label.new()
		label.text = tr(RpgStrings.action_label(action))
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		var button := Button.new()
		button.name = "Bind_%s" % action
		button.custom_minimum_size = Vector2(120, 0)
		button.text = _binding_text(action)
		button.pressed.connect(_start_capture.bind(action, button))
		row.add_child(button)
		list.add_child(row)

func _binding_text(action: String) -> String:
	var parts: PackedStringArray = []
	var s := _settings()
	for ev in InputMap.action_get_events(action):
		parts.append(s.event_text(ev) if s != null else ev.as_text())
	return " / ".join(parts) if not parts.is_empty() else "-"

func _wire_focus() -> void:
	RpgMenuUtil.wire_vertical(RpgMenuUtil.focusables(self))

func _focus_first() -> void:
	(get_node("%MasterSlider") as Control).grab_focus()

func _start_capture(action: String, button: Button) -> void:
	_capturing_action = action
	_capturing_button = button
	var current := InputMap.action_get_events(action)
	_capturing_old = current[0] if not current.is_empty() else null
	button.text = tr("UI_PRESS_KEY")

func _input(event: InputEvent) -> void:
	if _capturing_action == "":
		return
	var accept := false
	if event is InputEventKey and event.pressed and not event.echo:
		accept = true
	elif event is InputEventJoypadButton and event.pressed:
		accept = true
	if not accept:
		return
	get_viewport().set_input_as_handled()
	var s := _settings()
	var action := _capturing_action
	var button := _capturing_button
	_capturing_action = ""
	if s != null:
		var copy := event.duplicate() as InputEvent
		if copy is InputEventKey:
			var k := copy as InputEventKey
			if k.physical_keycode == 0:
				k.physical_keycode = k.keycode
		s.rebind(action, _capturing_old, copy)
	if button != null:
		button.text = _binding_text(action)

func _unhandled_input(event: InputEvent) -> void:
	if _capturing_action == "" and event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	var s := _settings()
	if s != null:
		s.save_settings()
	queue_free()
