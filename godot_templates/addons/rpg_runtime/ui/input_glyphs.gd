class_name RpgInputGlyphs
extends RefCounted
## Text glyphs for input prompts (T12.55, ARCHITECTURE §26): "[E]" on a keyboard, "[A]" on an
## Xbox pad, "[Cross]" on a PlayStation pad, "[B]" on a Nintendo pad.
##
## The device is the one used last (RpgSettings tracks it and emits `input_device_changed`). A
## pad's layout comes from its name; a pad of unknown make gets neutral names ("[Pad 0]"). The
## glyph is the first binding of `action` for that kind of device, read from the InputMap when it
## is asked for, so a remapped key shows at once. No glyph art is bundled: the glyphs are text.

const KEYBOARD := "keyboard"  # keyboard and mouse
const XBOX := "xbox"
const PLAYSTATION := "playstation"
const NINTENDO := "nintendo"
const PAD := "pad"  # a controller whose make is not known
const PAD_LAYOUTS: Array[String] = [XBOX, PLAYSTATION, NINTENDO, PAD]

## A pad axis must move this far to count as using the pad (stick drift does not).
const AXIS_THRESHOLD := 0.5

# Joy name fragments (lower case) -> layout. Checked in this order.
const NAME_HINTS := [
	[PLAYSTATION, ["playstation", "dualshock", "dualsense", "ps3", "ps4", "ps5", "sony"]],
	[NINTENDO, ["nintendo", "switch", "joy-con", "joycon", "pro controller"]],
	[XBOX, ["xbox", "xinput", "microsoft", "x-box"]],
]

# Button names by JoyButton index (SDL positions: 0 is the bottom face button).
const BUTTONS := {
	XBOX: ["A", "B", "X", "Y", "View", "Xbox", "Menu", "LS", "RS", "LB", "RB"],
	PLAYSTATION: ["Cross", "Circle", "Square", "Triangle", "Create", "PS", "Options", "L3", "R3", "L1", "R1"],
	NINTENDO: ["B", "A", "Y", "X", "-", "Home", "+", "LS", "RS", "L", "R"],
}
const DPAD := {
	JOY_BUTTON_DPAD_UP: "D-pad Up",
	JOY_BUTTON_DPAD_DOWN: "D-pad Down",
	JOY_BUTTON_DPAD_LEFT: "D-pad Left",
	JOY_BUTTON_DPAD_RIGHT: "D-pad Right",
}
const TRIGGERS := {
	XBOX: ["LT", "RT"],
	PLAYSTATION: ["L2", "R2"],
	NINTENDO: ["ZL", "ZR"],
	PAD: ["Left trigger", "Right trigger"],
}
const MOUSE := {
	MOUSE_BUTTON_LEFT: "Left click",
	MOUSE_BUTTON_RIGHT: "Right click",
	MOUSE_BUTTON_MIDDLE: "Middle click",
}

## The kind of device `event` comes from (KEYBOARD or a pad layout), or "" when it says nothing
## (a release, a small stick movement, mouse motion).
static func device_of(event: InputEvent) -> String:
	if event is InputEventKey:
		return KEYBOARD if (event as InputEventKey).pressed else ""
	if event is InputEventMouseButton:
		return KEYBOARD if (event as InputEventMouseButton).pressed else ""
	if event is InputEventJoypadButton:
		return layout_of(event.device) if (event as InputEventJoypadButton).pressed else ""
	if event is InputEventJoypadMotion:
		var motion := event as InputEventJoypadMotion
		return layout_of(event.device) if absf(motion.axis_value) >= AXIS_THRESHOLD else ""
	return ""

static func is_pad(device: String) -> bool:
	return PAD_LAYOUTS.has(device)

## The layout of joypad `device`, from the name the system gives it.
static func layout_of(device: int) -> String:
	return layout_for_name(Input.get_joy_name(device))

static func layout_for_name(joy_name: String) -> String:
	var lowered := joy_name.to_lower()
	for entry: Array in NAME_HINTS:
		for fragment: String in entry[1]:
			if lowered.contains(fragment):
				return entry[0]
	return PAD

## The device prompts are for: the one used last, else a keyboard.
static func current_device() -> String:
	var settings := RpgUtil.settings()
	return settings.input_device if settings != null else KEYBOARD

## The layout to name pad buttons with when no pad was used last: the first connected pad's.
static func pad_layout() -> String:
	var device := current_device()
	if is_pad(device):
		return device
	var pads := Input.get_connected_joypads()
	return layout_of(pads[0]) if not pads.is_empty() else PAD

## "[E]": the glyph of `action` for `device` ("" = the current one).
static func glyph(action: String, device: String = "") -> String:
	var events: Array = InputMap.action_get_events(action) if InputMap.has_action(action) else []
	return "[%s]" % binding_text(events, device if device != "" else current_device())

## The text of the first of `events` that `device` can press; the first event of any kind when
## there is none for it; "?" when there are no events.
static func binding_text(events: Array, device: String) -> String:
	var first: InputEvent = null
	for ev: InputEvent in events:
		if _belongs(ev, device):
			first = ev
			break
	if first == null and not events.is_empty():
		first = events[0]
	if first == null:
		return "?"
	return event_text(first, device if is_pad(device) else pad_layout())

static func _belongs(ev: InputEvent, device: String) -> bool:
	if is_pad(device):
		return ev is InputEventJoypadButton or ev is InputEventJoypadMotion
	return ev is InputEventKey or ev is InputEventMouseButton

## Short text for one binding; pad buttons are named for `layout`.
static func event_text(ev: InputEvent, layout: String = PAD) -> String:
	if ev is InputEventKey:
		return RpgSettingsStore.event_text(ev)
	if ev is InputEventMouseButton:
		var index := (ev as InputEventMouseButton).button_index
		return str(MOUSE.get(index, "Mouse %d" % index))
	if ev is InputEventJoypadButton:
		return button_name((ev as InputEventJoypadButton).button_index, layout)
	if ev is InputEventJoypadMotion:
		var motion := ev as InputEventJoypadMotion
		return axis_name(motion.axis, motion.axis_value, layout)
	return ev.as_text()

static func button_name(index: int, layout: String) -> String:
	if DPAD.has(index):
		return str(DPAD[index])
	var names: Array = BUTTONS.get(layout, [])
	if index >= 0 and index < names.size():
		return str(names[index])
	return "Pad %d" % index  # a pad of unknown make, or a button past the common ones

static func axis_name(axis: int, value: float, layout: String) -> String:
	var triggers: Array = TRIGGERS.get(layout, TRIGGERS[PAD])
	match axis:
		JOY_AXIS_TRIGGER_LEFT:
			return str(triggers[0])
		JOY_AXIS_TRIGGER_RIGHT:
			return str(triggers[1])
		JOY_AXIS_LEFT_X:
			return "Left stick " + ("Left" if value < 0.0 else "Right")
		JOY_AXIS_LEFT_Y:
			return "Left stick " + ("Up" if value < 0.0 else "Down")
		JOY_AXIS_RIGHT_X:
			return "Right stick " + ("Left" if value < 0.0 else "Right")
		JOY_AXIS_RIGHT_Y:
			return "Right stick " + ("Up" if value < 0.0 else "Down")
	return "Axis %d" % axis

## A line of hints: `pairs` is [[actions, text], ...] where actions is one action or an Array of
## them (their glyphs are joined). "[Z] Confirm   [X] Back"
static func hint(pairs: Array, device: String = "") -> String:
	var parts: PackedStringArray = []
	for pair: Array in pairs:
		var actions: Array = pair[0] if pair[0] is Array else [pair[0]]
		var glyphs: PackedStringArray = []
		for action: String in actions:
			if InputMap.has_action(action):
				glyphs.append(glyph(action, device))
		if not glyphs.is_empty():
			parts.append("%s %s" % ["".join(glyphs), str(pair[1])])
	return "   ".join(parts)
