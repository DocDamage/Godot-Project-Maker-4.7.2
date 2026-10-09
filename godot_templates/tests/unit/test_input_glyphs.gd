extends RefCounted
## Input glyphs (T12.55): the device used last, pad layouts, remapped keys, text fallbacks.

const Fixtures := preload("../lib/fixtures.gd")
const ACTION := "glyph_test_action"

static func _key(code: Key) -> InputEventKey:
	var ev := InputEventKey.new()
	ev.physical_keycode = code
	ev.pressed = true
	return ev

static func _button(index: JoyButton, device: int = 0) -> InputEventJoypadButton:
	var ev := InputEventJoypadButton.new()
	ev.button_index = index
	ev.device = device
	ev.pressed = true
	return ev

static func _bind(events: Array) -> void:
	if InputMap.has_action(ACTION):
		InputMap.erase_action(ACTION)
	InputMap.add_action(ACTION)
	for ev: InputEvent in events:
		InputMap.action_add_event(ACTION, ev)

static func _unbind() -> void:
	if InputMap.has_action(ACTION):
		InputMap.erase_action(ACTION)

func test_switching_devices_changes_the_glyph_and_tells_the_prompts(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	_bind([_key(KEY_E), _button(JOY_BUTTON_A)])
	var seen: Array[String] = []
	settings.input_device_changed.connect(func(device: String) -> void: seen.append(device))
	t.eq(settings.input_device, RpgInputGlyphs.KEYBOARD, "a keyboard until something else is used")
	t.eq(RpgInputGlyphs.glyph(ACTION), "[E]")
	settings.note_input(_button(JOY_BUTTON_X))  # a pad with no name the helper knows
	t.eq(settings.input_device, RpgInputGlyphs.PAD)
	t.eq(RpgInputGlyphs.glyph(ACTION), "[Pad 0]", "an unknown pad: a neutral text glyph")
	settings.note_input(_button(JOY_BUTTON_Y))  # the same device again: no new signal
	settings.note_input(_key(KEY_SPACE))
	t.eq(RpgInputGlyphs.glyph(ACTION), "[E]", "back on the keyboard")
	t.eq(seen, [RpgInputGlyphs.PAD, RpgInputGlyphs.KEYBOARD])
	var released := _key(KEY_E)
	released.pressed = false
	var drift := InputEventJoypadMotion.new()
	drift.axis = JOY_AXIS_LEFT_X
	drift.axis_value = 0.2
	settings.note_input(released)
	settings.note_input(drift)
	settings.note_input(InputEventMouseMotion.new())
	t.eq(seen.size(), 2, "releases, stick drift and mouse motion do not switch the device")
	_unbind()
	Fixtures.uninstall("RpgSettings")

func test_a_remapped_key_is_shown(t) -> void:
	_bind([_key(KEY_E)])
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.KEYBOARD), "[E]")
	InputMap.action_erase_events(ACTION)
	InputMap.action_add_event(ACTION, _key(KEY_F))  # what the settings remap does
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.KEYBOARD), "[F]")
	_unbind()

func test_pad_layouts_come_from_the_joy_name(t) -> void:
	t.eq(RpgInputGlyphs.layout_for_name("Xbox Series Controller"), RpgInputGlyphs.XBOX)
	t.eq(RpgInputGlyphs.layout_for_name("XInput Controller"), RpgInputGlyphs.XBOX)
	t.eq(RpgInputGlyphs.layout_for_name("PS5 Controller"), RpgInputGlyphs.PLAYSTATION)
	t.eq(RpgInputGlyphs.layout_for_name("Sony DualSense"), RpgInputGlyphs.PLAYSTATION)
	t.eq(RpgInputGlyphs.layout_for_name("Nintendo Switch Pro Controller"), RpgInputGlyphs.NINTENDO)
	t.eq(RpgInputGlyphs.layout_for_name("Generic USB Gamepad"), RpgInputGlyphs.PAD)
	t.eq(RpgInputGlyphs.layout_for_name(""), RpgInputGlyphs.PAD)

func test_each_layout_names_the_bottom_button_its_own_way(t) -> void:
	_bind([_key(KEY_E), _button(JOY_BUTTON_A)])
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.XBOX), "[A]")
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.PLAYSTATION), "[Cross]")
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.NINTENDO), "[B]", "Nintendo's bottom button is B")
	t.eq(RpgInputGlyphs.button_name(JOY_BUTTON_DPAD_UP, RpgInputGlyphs.XBOX), "D-pad Up")
	t.eq(RpgInputGlyphs.button_name(JOY_BUTTON_PADDLE1, RpgInputGlyphs.XBOX), "Pad %d" % JOY_BUTTON_PADDLE1)
	t.eq(RpgInputGlyphs.axis_name(JOY_AXIS_TRIGGER_RIGHT, 1.0, RpgInputGlyphs.PLAYSTATION), "R2")
	t.eq(RpgInputGlyphs.axis_name(JOY_AXIS_LEFT_Y, -1.0, RpgInputGlyphs.PAD), "Left stick Up")
	_unbind()

func test_a_device_without_a_binding_falls_back_and_nothing_bound_is_a_question_mark(t) -> void:
	_bind([_key(KEY_E)])
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.XBOX), "[E]", "no pad binding: the key")
	_bind([_button(JOY_BUTTON_B)])
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.KEYBOARD), "[Pad 1]", "no key: the pad button")
	_unbind()
	t.eq(RpgInputGlyphs.glyph(ACTION, RpgInputGlyphs.KEYBOARD), "[?]", "an action that does not exist")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	t.eq(RpgInputGlyphs.event_text(click), "Left click")

func test_the_interaction_prompt_and_hints_use_the_glyphs(t) -> void:
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS) as RpgSettingsStore
	var had_interact := InputMap.has_action("interact")
	var old: Array[InputEvent] = []
	if had_interact:
		old = InputMap.action_get_events("interact")
	if not had_interact:
		InputMap.add_action("interact")
	InputMap.action_erase_events("interact")
	InputMap.action_add_event("interact", _key(KEY_E))
	InputMap.action_add_event("interact", _button(JOY_BUTTON_A))
	var interaction := RpgInteraction.new()
	t.eq(interaction.prompt_text(), "[E]")
	settings.note_input(_button(JOY_BUTTON_A))
	t.eq(interaction.prompt_text(), "[Pad 0]", "the pad used last, of unknown make")
	t.eq(RpgInputGlyphs.hint([["interact", "Talk"], ["no_such_action", "Nothing"]]), "[Pad 0] Talk")
	interaction.free()
	InputMap.action_erase_events("interact")
	for ev in old:
		InputMap.action_add_event("interact", ev)
	if not had_interact:
		InputMap.erase_action("interact")
	Fixtures.uninstall("RpgSettings")

func test_the_battle_hint_follows_the_step(t) -> void:
	var made: Array[String] = []
	var keys := {"confirm": KEY_Z, "cancel": KEY_X, "move_left": KEY_LEFT, "move_right": KEY_RIGHT}
	for action: String in keys:
		if not InputMap.has_action(action):  # the game's config defines them; this project does not
			InputMap.add_action(action)
			InputMap.action_add_event(action, _key(keys[action]))
			made.append(action)
	var ui := RpgBattleUi.new()
	ui._ready()
	t.ok(not ui._hint.visible, "nothing to press while nobody chooses")
	ui._mode = &"target"
	t.ok(ui._hint.visible)
	t.eq(ui._hint.text.count("["), 4, "left and right, confirm, back")
	t.ok(ui._hint.text.begins_with("[Left][Right] "), ui._hint.text)
	ui._mode = &"log"
	t.eq(ui._hint.text.count("["), 1, "just the key that goes on")
	ui._mode = &"none"
	t.ok(not ui._hint.visible)
	ui.free()
	for action in made:
		InputMap.erase_action(action)
