class_name RpgAchievementsMenu
extends Control
## The achievements (1.5.0), opened from the pause menu: how many are unlocked and their points,
## then one row each, unlocked first marked [x], with how far along a locked one is ("Wolf
## hunter: 3/5"); a secret one shows "???" until it is unlocked. Built in code; the rows are
## buttons, so the gamepad scrolls through them, and Back closes it.

signal closed

var _list: VBoxContainer
var _total: Label
var _back: Button
var _rows: Array[Button] = []

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.85)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(300, 0)
	panel.add_child(box)
	var heading := Label.new()
	heading.text = tr("UI_ACHIEVEMENTS")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	_total = Label.new()
	_total.name = "Total"
	_total.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_total)
	var scroll := ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(290, 150)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	_list = VBoxContainer.new()
	_list.name = "List"
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_list)
	_back = Button.new()
	_back.name = "Back"
	_back.text = tr("UI_BACK")
	_back.pressed.connect(close)
	box.add_child(_back)
	rebuild()

## The rows, in order: unlocked first, then by id.
func rows() -> Array[Button]:
	return _rows

func rebuild() -> void:
	for child in _list.get_children():
		_list.remove_child(child)
		child.queue_free()
	_rows.clear()
	var state := RpgUtil.state()
	if state == null:
		return
	var ids := state.achievement_ids()
	var unlocked := ids.filter(func(each: StringName) -> bool: return state.achievement_unlocked(each))
	_total.text = tr("UI_ACHIEVEMENTS_TOTAL") % [unlocked.size(), ids.size(), state.achievement_points()]
	var ordered: Array = unlocked.duplicate()
	ordered.append_array(ids.filter(func(each: StringName) -> bool: return not state.achievement_unlocked(each)))
	for achievement_id: StringName in ordered:
		var b := Button.new()
		b.name = "Achievement_%s" % achievement_id
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.flat = true
		b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		b.custom_minimum_size = Vector2(280, 0)
		b.text = row_text(state, achievement_id)
		var def: RpgAchievement = state.achievement_defs[achievement_id]
		if def.icon != null and (state.achievement_unlocked(achievement_id) or not def.secret):
			b.icon = def.icon
			b.expand_icon = true
		_list.add_child(b)
		_rows.append(b)
	if _rows.is_empty():
		var none := Label.new()
		none.text = tr("UI_NO_ACHIEVEMENTS")
		_list.add_child(none)
	var ring: Array = []
	ring.append_array(_rows)
	ring.append(_back)
	RpgMenuUtil.wire_vertical(ring)
	var start: Button = _rows[0] if not _rows.is_empty() else _back
	if is_inside_tree():
		start.grab_focus.call_deferred()

## "[x] Title (10)\nDescription", or for a locked one "[ ] Title: 3/5\nDescription" (its counts,
## when its condition counts something); a locked secret is "[ ] ???".
static func row_text(state: RpgGameState, achievement_id: StringName) -> String:
	var def: RpgAchievement = state.achievement_defs.get(achievement_id)
	if def == null:
		return ""
	var done := state.achievement_unlocked(achievement_id)
	if def.secret and not done:
		return "[ ] " + String(TranslationServer.translate("UI_SECRET"))
	var title := String(TranslationServer.translate(def.title if def.title != "" else String(achievement_id)))
	var text := "%s %s (%d)" % ["[x]" if done else "[ ]", title, def.points]
	if not done:
		var parts: PackedStringArray = []
		for count in RpgQuestDefinition.progress_of(def.when, state):
			parts.append("%d/%d" % [mini(RpgUtil.to_int(count["have"]), RpgUtil.to_int(count["need"])), RpgUtil.to_int(count["need"])])
		if not parts.is_empty():
			text += ": " + ", ".join(parts)
	if def.description != "":
		text += "\n" + String(TranslationServer.translate(def.description))
	return text

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	closed.emit()
	queue_free()
