class_name RpgQuestTracker
extends Control
## The HUD's quest tracker (1.5.0), under the minimap in the top-right corner: the tracked quest
## (GameState.tracked_quest), what its current stage asks, how far along it is ("Logs 5/8",
## counted live) and "Ready to turn in" when it is. Boot adds it; RpgSettings.quest_tracker turns
## it off, and it hides itself when no quest is tracked or no map is active.

const WIDTH := 160.0
const MARGIN := 8.0
## Below the minimap (RpgMinimap.VIEW is 84 high).
const TOP := MARGIN + 84.0 + 6.0
const UPDATE_S := 0.5
const BACK := Color(0, 0, 0, 0.55)

var _box: VBoxContainer = null
var _title: Label = null
var _step: Label = null
var _since := 0.0

func _ready() -> void:
	name = "QuestTracker"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_TOP_RIGHT)
	offset_left = -WIDTH - MARGIN
	offset_right = -MARGIN
	offset_top = TOP
	var panel := PanelContainer.new()
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = BACK
	style.set_content_margin_all(4)
	panel.add_theme_stylebox_override("panel", style)
	panel.custom_minimum_size = Vector2(WIDTH, 0)
	add_child(panel)
	_box = VBoxContainer.new()
	_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(_box)
	_title = _label("Title")
	_step = _label("Step")
	_step.modulate = Color(1, 1, 1, 0.85)
	visible = false
	var bus := RpgUtil.events()
	if bus != null:
		for signal_name: StringName in [&"quest_changed", &"item_added", &"item_removed", &"gold_changed", &"variable_changed", &"map_entered"]:
			bus.connect(signal_name, _on_changed)

func _label(node_name: String) -> Label:
	var label := Label.new()
	label.name = node_name
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size = Vector2(WIDTH - 8.0, 0)
	_box.add_child(label)
	return label

func _on_changed(_a: Variant = null, _b: Variant = null) -> void:
	refresh.call_deferred()  # after the quests have moved on

func _process(delta: float) -> void:
	_since += delta
	if _since < UPDATE_S:
		return
	_since = 0.0
	refresh()

## Shows the tracked quest again, or hides the tracker.
func refresh() -> void:
	var state := RpgUtil.state()
	var settings := RpgUtil.settings()
	var router := RpgUtil.router()
	var on_map := router != null and router.get("current_map") != null
	var quest_id: StringName = state.tracked_quest if state != null else &""
	if (settings != null and not settings.quest_tracker) or not on_map or state == null or not state.quest_is_active(quest_id):
		visible = false
		return
	var def: RpgQuestDefinition = state.quest_defs.get(quest_id)
	_title.text = TranslationServer.translate(def.title if def != null and def.title != "" else String(quest_id))
	_step.text = step_text(state, quest_id)
	_step.visible = _step.text != ""
	visible = true

## What the current stage of a quest asks, with how far along it is, and "Ready to turn in"
## below when it is: "Bring logs (5/8)". Empty for a quest without a definition.
static func step_text(state: RpgGameState, quest_id: StringName) -> String:
	var stage := state.quest_current_stage(quest_id)
	if stage.is_empty():
		return ""
	var text := String(TranslationServer.translate(str(stage.get("description", ""))))
	var counts := progress_text(state, quest_id)
	if counts != "":
		text = "%s (%s)" % [text, counts] if text != "" else counts
	if state.quest_ready(quest_id):
		text += "\n" + String(TranslationServer.translate("UI_QUEST_READY"))
	return text

## The counts of the current stage, "Logs 5/8, Gold 30/100" (a variable or a friendship by its
## numbers alone); "" when the stage counts nothing.
static func progress_text(state: RpgGameState, quest_id: StringName) -> String:
	var parts: PackedStringArray = []
	for count in state.quest_progress(quest_id):
		var numbers := "%d/%d" % [mini(RpgUtil.to_int(count["have"]), RpgUtil.to_int(count["need"])), RpgUtil.to_int(count["need"])]
		var what := _what(state, str(count["atom"]), str(count["what"]))
		parts.append("%s %s" % [what, numbers] if what != "" else numbers)
	return ", ".join(parts)

static func _what(state: RpgGameState, atom: String, what: String) -> String:
	if atom.begins_with("item:"):
		var def: RpgItemDefinition = state.items.get(StringName(what))
		return TranslationServer.translate(def.display_name) if def != null and def.display_name != "" else what
	if atom.begins_with("gold"):
		return TranslationServer.translate("UI_GOLD")
	if atom.begins_with("level"):
		return TranslationServer.translate("UI_LEVEL")
	return ""
