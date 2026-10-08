class_name RpgEquipPicker
extends Control
## Chooses what an actor wears in one slot. One button per candidate in the inventory (and "Take
## off" when the slot is worn); the stat changes of the focused choice show above the buttons, green
## for a gain and red for a loss, and nothing changes until a button is pressed. Built in code, so a
## runtime upgrade is enough to get it. Used by the status menu (per slot) and the inventory menu
## (per item).

const GAIN_COLOR := "#6fd16f"
const LOSS_COLOR := "#ff6b6b"
const STAT_KEYS := {
	&"max_hp": "UI_HP", &"attack": "UI_ATTACK", &"defense": "UI_DEFENSE", &"speed": "UI_SPEED",
	&"magic": "UI_MAGIC", &"resistance": "UI_RESISTANCE", &"move_speed": "UI_MOVE_SPEED",
}
const SLOT_KEYS := {&"weapon": "UI_SLOT_WEAPON", &"armor": "UI_SLOT_ARMOR", &"accessory": "UI_SLOT_ACCESSORY"}

signal closed(changed: bool)

## Set before add_child.
var actor_id: StringName = &"hero"
var slot: StringName = &"weapon"
var focus_item: StringName = &""  # the choice that starts focused (the inventory menu's item)

var changed := false
var _choices: Array[Button] = []
var _preview: RichTextLabel = null
var _choice_items: Dictionary = {}  # Button -> item id (&"" for "Take off")

## The translation key of a slot's name.
static func slot_key(slot_id: StringName) -> String:
	var key: String = SLOT_KEYS.get(slot_id, "UI_EQUIPMENT")
	return key

## "Attack +3" / "Defense -1" / "Move speed +10" (the stat name is translated).
static func delta_text(stat_name: StringName, delta: float) -> String:
	var key: String = STAT_KEYS.get(stat_name, "")
	var shown := roundi(delta)
	var sign_text := "+" if delta > 0.0 else "-"
	var magnitude := str(absi(shown)) if absf(delta - float(shown)) < 0.05 else "%.1f" % absf(delta)
	var shown_name := String(TranslationServer.translate(key)) if key != "" else String(stat_name)
	return "%s %s%s" % [shown_name, sign_text, magnitude]

## The preview of a change as BBCode: one coloured line per changed stat, or "No change".
static func preview_bbcode(delta: Dictionary) -> String:
	if delta.is_empty():
		return String(TranslationServer.translate("UI_NO_CHANGE"))
	var lines: PackedStringArray = []
	for stat_name: Variant in delta:
		var amount: float = RpgUtil.to_float(delta[stat_name])
		var color := GAIN_COLOR if amount > 0.0 else LOSS_COLOR
		lines.append("[color=%s]%s[/color]" % [color, delta_text(StringName(str(stat_name)), amount)])
	return "\n".join(lines)

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	process_mode = Node.PROCESS_MODE_ALWAYS
	var dim := ColorRect.new()
	dim.name = "Dim"
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center)
	var panel := PanelContainer.new()
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(200, 0)
	panel.add_child(box)
	var heading := Label.new()
	heading.name = "Heading"
	heading.text = "%s: %s" % [tr("UI_EQUIP"), tr(slot_key(slot))]
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	var list := VBoxContainer.new()
	list.name = "Choices"
	box.add_child(list)
	_preview = RichTextLabel.new()
	_preview.name = "Preview"
	_preview.bbcode_enabled = true
	_preview.fit_content = true
	_preview.scroll_active = false
	_preview.custom_minimum_size = Vector2(190, 36)
	box.add_child(_preview)
	_fill(list)
	var back := Button.new()
	back.name = "Back"
	back.text = tr("UI_BACK")
	back.pressed.connect(close)
	box.add_child(back)
	var ring: Array = _choices.duplicate()
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	var start: Button = back
	for button in _choices:
		if _choice_items[button] == focus_item and focus_item != &"":
			start = button
	if start == back and not _choices.is_empty():
		start = _choices[0]
	start.grab_focus.call_deferred()
	var start_item: StringName = _choice_items.get(start, &"")
	_show_preview(start_item, start != back)

func _fill(list: VBoxContainer) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var worn := state.equipped_in(actor_id, slot)
	var seen: Dictionary = {}
	for entry in state.inventory.slots:
		var item_id: StringName = entry["item_id"]
		var def: RpgItemDefinition = state.items.get(item_id)
		if seen.has(item_id) or RpgGameState.slot_of(def) != slot:
			continue
		seen[item_id] = true
		_add_choice(list, "Choice_%s" % item_id, tr(def.display_name), item_id)
	if worn != &"":
		_add_choice(list, "TakeOff", tr("UI_TAKE_OFF"), &"")
	if _choices.is_empty():
		var none := Label.new()
		none.name = "Nothing"
		none.text = tr("UI_NOTHING_TO_EQUIP")
		list.add_child(none)

func _add_choice(list: VBoxContainer, node_name: String, text: String, item_id: StringName) -> void:
	var b := Button.new()
	b.name = node_name
	b.text = text
	b.pressed.connect(_choose.bind(item_id))
	b.focus_entered.connect(_show_preview.bind(item_id, true))
	list.add_child(b)
	_choices.append(b)
	_choice_items[b] = item_id

func _show_preview(item_id: StringName, is_choice: bool) -> void:
	var state := RpgUtil.state()
	if _preview == null or state == null:
		return
	_preview.text = preview_bbcode(state.equip_preview(actor_id, slot, item_id)) if is_choice else ""

func _choose(item_id: StringName) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var ok: bool = state.unequip(actor_id, slot) if item_id == &"" else state.equip(actor_id, item_id)
	if not ok:
		RpgUtil.notify(tr("UI_CANNOT_EQUIP"))
		return
	changed = true
	close()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	closed.emit(changed)
	queue_free()
