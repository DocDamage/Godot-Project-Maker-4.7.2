class_name RpgJournalMenu
extends Control
## The quest journal: Active and Completed tabs, one button per quest, and the stages of the quest
## in focus (finished ones ticked, the current one marked with how far along it is). Confirming an
## active quest tracks it on the HUD (the tracked one is marked); failed quests are listed with the
## completed ones, marked. One vertical focus ring (tabs, quests, Back); left / right switches the
## tab.

const ACTIVE := &"active"
const FINISHED := &"finished"

var tab: StringName = ACTIVE

var _rows: Array[Button] = []
var _row_quests: Dictionary = {}  # Button -> quest id

func _ready() -> void:
	(get_node("%Back") as Button).pressed.connect(close)
	(get_node("%ActiveTab") as Button).pressed.connect(set_tab.bind(ACTIVE))
	(get_node("%DoneTab") as Button).pressed.connect(set_tab.bind(FINISHED))
	_rebuild()

## The quest buttons, in order.
func rows() -> Array[Button]:
	return _rows

func quest_of(button: Button) -> StringName:
	var quest_id: StringName = _row_quests.get(button, &"")
	return quest_id

func set_tab(new_tab: StringName) -> void:
	tab = new_tab
	_rebuild()

func _rebuild() -> void:
	var list := get_node("%List") as VBoxContainer
	for child in list.get_children():
		list.remove_child(child)
		child.queue_free()
	_rows.clear()
	_row_quests.clear()
	var active_tab := get_node("%ActiveTab") as Button
	var done_tab := get_node("%DoneTab") as Button
	active_tab.set_pressed_no_signal(tab == ACTIVE)
	done_tab.set_pressed_no_signal(tab == FINISHED)
	var desc := get_node("%Description") as Label
	var back := get_node("%Back") as Button
	var state := RpgUtil.state()
	if state != null:
		for quest_id in state.journal_ids(tab == FINISHED):
			var def: RpgQuestDefinition = state.quest_defs[quest_id]
			var b := Button.new()
			b.name = "Quest_%s" % quest_id
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.text = row_text(state, quest_id)
			b.focus_entered.connect(_describe.bind(quest_id))
			b.pressed.connect(_on_pressed.bind(quest_id))
			list.add_child(b)
			_rows.append(b)
			_row_quests[b] = quest_id
	desc.text = ""
	if _rows.is_empty():
		desc.text = tr("UI_NO_QUESTS_ACTIVE") if tab == ACTIVE else tr("UI_NO_QUESTS_DONE")
	var ring: Array = [active_tab, done_tab]
	ring.append_array(_rows)
	ring.append(back)
	RpgMenuUtil.wire_vertical(ring)
	active_tab.focus_neighbor_left = active_tab.get_path_to(done_tab)
	active_tab.focus_neighbor_right = active_tab.get_path_to(done_tab)
	done_tab.focus_neighbor_left = done_tab.get_path_to(active_tab)
	done_tab.focus_neighbor_right = done_tab.get_path_to(active_tab)
	var start: Button = _rows[0] if not _rows.is_empty() else (active_tab if tab == ACTIVE else done_tab)
	start.grab_focus.call_deferred()

## A quest's button: its title, and "(failed)" or "Tracked" after it.
static func row_text(state: RpgGameState, quest_id: StringName) -> String:
	var def: RpgQuestDefinition = state.quest_defs.get(quest_id)
	var text := String(TranslationServer.translate(def.title if def != null else String(quest_id)))
	if state.quest_is_failed(quest_id):
		text += " " + String(TranslationServer.translate("UI_QUEST_FAILED_MARK"))
	elif state.quest_is_active(quest_id) and state.tracked_quest == quest_id:
		text += "  [" + String(TranslationServer.translate("UI_QUEST_TRACKED")) + "]"
	return text

## Confirming an active quest tracks it (again: tracks nothing); the rows say which one is.
func _on_pressed(quest_id: StringName) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	if state.quest_is_active(quest_id):
		state.track_quest(quest_id if state.tracked_quest != quest_id else &"")
		for b in _rows:
			b.text = row_text(state, quest_of(b))
	_describe(quest_id)

func _describe(quest_id: StringName) -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	(get_node("%Description") as Label).text = detail_text(state, quest_id)

## The title and the stages of a quest: "[x] done stage", "> current stage (5/8)", and "Ready to
## turn in" under it when it is; later stages are not shown yet. A failed quest says so.
static func detail_text(state: RpgGameState, quest_id: StringName) -> String:
	var def: RpgQuestDefinition = state.quest_defs.get(quest_id)
	if def == null:
		return ""
	var lines: PackedStringArray = [TranslationServer.translate(def.title)]
	var current := def.stage_index(StringName(state.quest_state(quest_id)))
	var finished := state.quest_is_done(quest_id)
	for i in def.stages.size():
		var text := String(TranslationServer.translate(str(def.stage(i).get("description", ""))))
		if finished or i < current:
			lines.append("[x] " + text)
		elif i == current:
			lines.append("> " + RpgQuestTracker.step_text(state, quest_id))
	if state.quest_is_failed(quest_id):
		lines.append(String(TranslationServer.translate("UI_QUEST_FAILED_MARK")))
	return "\n".join(lines)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
