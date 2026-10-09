@tool
extends "data_tab.gd"
## The Quests tab (T13.19): the quests in res://game/data/quests. A stage list with a form (id,
## title, description, condition with the inline checker, where it leads, its target entity with
## a picker from the open map, its rewards), the quest's own id, title and rewards, a read-only
## graph of the stages (one node per stage, one edge per `next`), a test against a pretend game
## state, and JSON export and import. Every change is one undo step.

const QUESTS_DIR := "res://game/data/quests"
const DialogueTab := preload("dialogue_tab.gd")
const NODE_SPACING := Vector2(170, 0)
const NODE_WIDTH := 120.0
const GRAPH_MARGIN := 14.0
const DONE_NODE := "done"

var quest: RpgQuestDefinition = null
var test_state: RpgGameState = RpgGameState.new()
var quests_dir := QUESTS_DIR  # tests point the tab at their own folder

var _stages: ItemList
var _quest_id: LineEdit
var _quest_title: LineEdit
var _quest_rewards: TextEdit
var _stage_id: LineEdit
var _stage_title: LineEdit
var _description: LineEdit
var _condition: LineEdit
var _condition_note: Label
var _next: LineEdit
var _target: LineEdit
var _target_pick: OptionButton
var _stage_rewards: TextEdit
var _problems: Label
var _graph: GraphEdit
var _toggles: VBoxContainer
var _gold: SpinBox
var _test_result: Label

func _init() -> void:
	name = "Quests"
	build_top([["New", new_quest]])
	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)
	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(170, 0)
	split.add_child(left)
	_stages = ItemList.new()
	_stages.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_stages.item_selected.connect(func(_index: int) -> void: _show_stage())
	left.add_child(_stages)
	var stage_buttons := HBoxContainer.new()
	left.add_child(stage_buttons)
	button(stage_buttons, "Add", add_stage)
	button(stage_buttons, "Remove", remove_stage)
	button(stage_buttons, "Up", func() -> void: move_stage(-1))
	button(stage_buttons, "Down", func() -> void: move_stage(1))
	var right := VSplitContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(right)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.custom_minimum_size = Vector2(0, 160)
	right.add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_quest_id = _quest_field(form, "Quest id", "id")
	_quest_title = _quest_field(form, "Quest title (a text key)", "title")
	_quest_rewards = _rewards_edit(form, "Quest rewards", func(text: String) -> void: set_quest_property("rewards", parse_rewards(text)))
	var rule := HSeparator.new()
	form.add_child(rule)
	_stage_id = _stage_field(form, "Stage id", "id")
	_stage_title = _stage_field(form, "Stage title (a text key)", "title")
	_description = _stage_field(form, "Description (a text key)", "description")
	_condition = _stage_field(form, "Finished when", "complete_when")
	_condition.placeholder_text = "a condition, e.g. flag:npc.talked; empty = only an event finishes it"
	_condition.text_changed.connect(func(text: String) -> void: _condition_note.text = DialogueTab.condition_preview(text, test_state))
	_condition_note = note(form)
	_next = _stage_field(form, "Then (a stage id, or done; empty = the stage below)", "next")
	var target_row := HBoxContainer.new()
	_target = LineEdit.new()
	_target.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_target.placeholder_text = "the entity the minimap marks"
	_target.text_submitted.connect(func(text: String) -> void: edit_stage(selected_stage(), "target", text))
	_target.focus_exited.connect(func() -> void: edit_stage(selected_stage(), "target", _target.text))
	target_row.add_child(_target)
	_target_pick = OptionButton.new()
	_target_pick.tooltip_text = "The entities of the map that is open"
	_target_pick.item_selected.connect(func(index: int) -> void:
		if index > 0:
			edit_stage(selected_stage(), "target", _target_pick.get_item_text(index)))
	target_row.add_child(_target_pick)
	row(form, "Target", target_row)
	_stage_rewards = _rewards_edit(form, "Stage rewards", func(text: String) -> void: edit_stage(selected_stage(), "rewards", parse_rewards(text)))
	_problems = note(form)
	var lower := HSplitContainer.new()
	lower.custom_minimum_size = Vector2(0, 170)
	right.add_child(lower)
	_graph = GraphEdit.new()
	_graph.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_graph.custom_minimum_size = Vector2(240, 120)
	_graph.minimap_enabled = false
	_graph.right_disconnects = false
	_graph.show_menu = false  # a picture of the stages: nothing to zoom, snap or arrange
	_graph.resized.connect(_frame_graph)
	lower.add_child(_graph)
	var test_box := VBoxContainer.new()
	test_box.custom_minimum_size = Vector2(170, 0)
	lower.add_child(test_box)
	var test_title := Label.new()
	test_title.text = "Test (a pretend game state)"
	test_box.add_child(test_title)
	_toggles = VBoxContainer.new()
	test_box.add_child(_toggles)
	_gold = SpinBox.new()
	_gold.max_value = 999999
	_gold.prefix = "gold "
	_gold.value_changed.connect(func(value: float) -> void:
		test_state.gold = int(value)
		run_test())
	test_box.add_child(_gold)
	button(test_box, "Test", func() -> void: run_test())
	_test_result = Label.new()
	_test_result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	test_box.add_child(_test_result)
	build_status()

func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and test_state != null and is_instance_valid(test_state):
		test_state.free()

func _quest_field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_quest_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_quest_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

func _stage_field(parent: Control, label_text: String, key: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: edit_stage(selected_stage(), key, text.strip_edges()))
	edit.focus_exited.connect(func() -> void: edit_stage(selected_stage(), key, edit.text.strip_edges()))
	row(parent, label_text, edit)
	return edit

func _rewards_edit(parent: Control, label_text: String, commit: Callable) -> TextEdit:
	var edit := TextEdit.new()
	edit.custom_minimum_size = Vector2(0, 46)
	edit.placeholder_text = "one per line: gold 25, experience 5, potion x2"
	edit.focus_exited.connect(func() -> void: commit.call(edit.text))
	row(parent, label_text, edit)
	return edit

static func _typed(property: String, text: String) -> Variant:
	return StringName(text.strip_edges()) if property == "id" else text.strip_edges()

# ---------------------------------------------------------------- files

func folder() -> String:
	return quests_dir

func context_object() -> Object:
	return quest

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgQuestDefinition
	if res == null:
		say("%s is not a quest." % path)
		return false
	quest = res
	file_path = path
	dirty = false
	_refresh(0)
	say("%s: %d stages." % [path.get_file(), quest.stages.size()])
	return true

func save() -> bool:
	if quest == null or file_path == "":
		return false
	var err := ResourceSaver.save(quest, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

func new_quest() -> String:
	var made := RpgQuestDefinition.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_quest")
	made.id = StringName(path.get_file().get_basename())
	made.title = "QUEST_%s_TITLE" % String(made.id).to_upper()
	made.stages = [{"id": "start", "description": "QUEST_%s_START" % String(made.id).to_upper(), "complete_when": ""}]
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(quest.to_dict(), "  ", false) + "\n" if quest != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not (RpgUtil.to_dict(parsed).get("stages") is Array):
		say("%s is not quest JSON." % json_path.get_file())
		return ""
	var made := RpgQuestDefinition.from_dict(RpgUtil.to_dict(parsed))
	DirAccess.make_dir_recursive_absolute(folder())
	var target := folder().path_join(json_path.get_file().get_basename() + ".tres")
	if ResourceSaver.save(made, target) != OK:
		say("Could not save %s." % target)
		return ""
	file_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- showing

func selected_stage() -> int:
	var picked := _stages.get_selected_items()
	return picked[0] if not picked.is_empty() else -1

func select_stage(index: int) -> void:
	if index >= 0 and index < _stages.item_count:
		_stages.select(index)
		_show_stage()

## "⚠ 2. chest · open the chest" (the mark when a problem names the stage).
func stage_label(index: int) -> String:
	var stage := quest.stage(index)
	var stage_id := str(stage.get("id", ""))
	var marked := false
	for problem in problems():
		if problem.begins_with("stage %d " % (index + 1)):
			marked = true
	var text := str(stage.get("description", ""))
	return "%s%d. %s%s" % ["⚠ " if marked else "", index + 1, stage_id, " · " + text.left(30) if text != "" else ""]

## Everything that is wrong with the quest: the definition's problems, and a target that the
## open map does not have (only when a map with entities is open).
func problems() -> Array[String]:
	if quest == null:
		return []
	var out := quest.problems()
	var entities := map_entities()
	if not entities.is_empty():
		for i in quest.stages.size():
			var target := str(quest.stage(i).get("target", ""))
			if target != "" and not entities.has(target):
				out.append("stage %d (%s) points at the unknown entity '%s'" % [i + 1, str(quest.stage(i).get("id", "")), target])
	return out

func _refresh(select: int = -1) -> void:
	var keep := select if select >= 0 else selected_stage()
	_stages.clear()
	if quest == null:
		return
	for i in quest.stages.size():
		_stages.add_item(stage_label(i))
	if keep >= 0 and keep < _stages.item_count:
		_stages.select(keep)
	_loading = true
	_quest_id.text = String(quest.id)
	_quest_title.text = quest.title
	_quest_rewards.text = rewards_text(quest.rewards)
	_loading = false
	_show_stage()
	_problems.text = "\n".join(PackedStringArray(problems()))
	_rebuild_graph()
	_refresh_toggles()
	run_test()

func _show_stage() -> void:
	var stage := quest.stage(selected_stage()) if quest != null else {}
	_loading = true
	_stage_id.text = str(stage.get("id", ""))
	_stage_title.text = str(stage.get("title", ""))
	_description.text = str(stage.get("description", ""))
	_condition.text = str(stage.get("complete_when", ""))
	_condition_note.text = DialogueTab.condition_preview(_condition.text, test_state)
	_next.text = str(stage.get("next", ""))
	_target.text = str(stage.get("target", ""))
	_stage_rewards.text = rewards_text(RpgUtil.to_dict(stage.get("rewards", {})))
	_target_pick.clear()
	_target_pick.add_item("(pick)")
	for entity in map_entities():
		_target_pick.add_item(entity)
	_loading = false

# ---------------------------------------------------------------- edits (one undo step each)

func _apply_stages(value: Array) -> void:
	var typed: Array[Dictionary] = []
	for raw: Variant in value:
		typed.append(RpgUtil.to_dict(raw).duplicate(true))
	quest.stages = typed
	dirty = true
	_refresh()

func _apply_quest(value: Array) -> void:
	quest.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func _set_stages(action_name: String, stages: Array) -> void:
	record(action_name, &"_apply_stages", stages, quest.stages.duplicate(true))

## One key of stage `index`; an empty text takes an optional key away.
func edit_stage(index: int, key: String, value: Variant) -> void:
	if _loading or quest == null or index < 0 or index >= quest.stages.size():
		return
	var stages: Array = quest.stages.duplicate(true)
	var stage := RpgUtil.to_dict(stages[index])
	var empty := (value is String and str(value) == "") or (value is Dictionary and RpgUtil.to_dict(value).is_empty())
	if stage.get(key, "" if value is String else {}) == value or (empty and not stage.has(key)):
		return
	if empty and key not in ["id", "description", "complete_when"]:
		stage.erase(key)
	else:
		stage[key] = value
	_set_stages("Edit quest stage", stages)

func set_quest_property(property: String, value: Variant) -> void:
	if _loading or quest == null or quest.get(property) == value:
		return
	record("Edit quest", &"_apply_quest", [property, value], [property, quest.get(property)])

func add_stage() -> void:
	if quest == null:
		return
	var stages: Array = quest.stages.duplicate(true)
	var n := stages.size() + 1
	var ids := quest.stage_ids()
	while ids.has(StringName("stage_%d" % n)):
		n += 1
	stages.append({"id": "stage_%d" % n, "description": "", "complete_when": ""})
	_set_stages("Add quest stage", stages)
	_stages.select(quest.stages.size() - 1)
	_show_stage()

func remove_stage() -> void:
	var index := selected_stage()
	if quest == null or index < 0:
		return
	var stages: Array = quest.stages.duplicate(true)
	stages.remove_at(index)
	_set_stages("Remove quest stage", stages)

func move_stage(by: int) -> void:
	var index := selected_stage()
	var to := index + by
	if quest == null or index < 0 or to < 0 or to >= quest.stages.size():
		return
	var stages: Array = quest.stages.duplicate(true)
	var moved: Variant = stages[index]
	stages.remove_at(index)
	stages.insert(to, moved)
	_set_stages("Move quest stage", stages)
	_stages.select(to)
	_show_stage()

# ---------------------------------------------------------------- rewards as text

## "gold 25", "experience 5" and "<item id> x<qty>" lines -> {gold, experience, items}.
static func parse_rewards(text: String) -> Dictionary:
	var out := {}
	var reward_items: Array = []
	for raw in text.split("\n"):
		var line := raw.strip_edges()
		if line == "":
			continue
		var words := line.split(" ", false)
		if words.size() == 2 and words[0] in ["gold", "experience"] and words[1].is_valid_int():
			out[words[0]] = words[1].to_int()
			continue
		var qty := 1
		var item_id := line
		var at := line.rfind(" x")
		if at > 0 and line.substr(at + 2).is_valid_int():
			qty = line.substr(at + 2).to_int()
			item_id = line.substr(0, at).strip_edges()
		reward_items.append({"item_id": item_id, "qty": qty})
	if not reward_items.is_empty():
		out["items"] = reward_items
	return out

static func rewards_text(rewards: Dictionary) -> String:
	var rows: PackedStringArray = []
	for key: String in ["gold", "experience"]:
		if RpgUtil.to_int(rewards.get(key, 0)) != 0:
			rows.append("%s %d" % [key, RpgUtil.to_int(rewards[key])])
	var reward_items: Variant = rewards.get("items", [])
	if reward_items is Array:
		var list: Array = reward_items
		for entry: Variant in list:
			var item := RpgUtil.to_dict(entry)
			rows.append("%s x%d" % [str(item.get("item_id", "")), RpgUtil.to_int(item.get("qty", 1))])
	return "\n".join(rows)

# ---------------------------------------------------------------- the graph

## One node per stage (and "done"), one connection per stage to where it leads. Read-only: the
## layout is a row in stage order, and nothing can be dragged or connected by hand.
func _rebuild_graph() -> void:
	_graph.clear_connections()
	for child in _graph.get_children():
		if child is GraphNode:
			_graph.remove_child(child)
			child.queue_free()
	if quest == null:
		return
	var names: Array[String] = []
	for stage_id in quest.stage_ids():
		names.append(String(stage_id))
	for i in names.size():
		_graph.add_child(_graph_node("stage_%d" % i, names[i], i, true))
	_graph.add_child(_graph_node(DONE_NODE, "done", names.size(), false))
	for i in names.size():
		var following := quest.next_of(i)
		var to := quest.stage_index(following) if following != &"" else -1
		var to_name := "stage_%d" % to if to >= 0 else DONE_NODE
		if following == &"" or to >= 0:
			_graph.connect_node("stage_%d" % i, 0, to_name, 0)
	_frame_graph.call_deferred()

## Shows the first stage in the corner of the graph (a GraphEdit keeps whatever scroll position
## its first layout gave it, which can leave every node out of view).
func _frame_graph() -> void:
	if is_inside_tree():  # after the graph has laid its nodes out
		await get_tree().process_frame
		await get_tree().process_frame
	if is_instance_valid(_graph):
		_graph.scroll_offset = Vector2(-GRAPH_MARGIN, -GRAPH_MARGIN)

func _graph_node(node_name: String, title: String, column: int, has_output: bool) -> GraphNode:
	var node := GraphNode.new()
	node.name = node_name
	node.title = title
	node.draggable = false
	node.custom_minimum_size = Vector2(NODE_WIDTH, 0)
	node.position_offset = NODE_SPACING * column
	var label := Label.new()
	label.text = " "
	node.add_child(label)
	node.set_slot(0, true, 0, Color.WHITE, has_output, 0, Color.WHITE)
	return node

## The titles of the graph's stage nodes, in order (without "done").
func graph_nodes() -> Array[String]:
	var out: Array[String] = []
	for child in _graph.get_children():
		if child is GraphNode and child.name != DONE_NODE:
			out.append((child as GraphNode).title)
	return out

## [[from title, to title]] of the graph's connections, in stage order.
func graph_edges() -> Array[Array]:
	var titles := {}
	for child in _graph.get_children():
		if child is GraphNode:
			titles[String(child.name)] = (child as GraphNode).title
	var out: Array[Array] = []
	for connection: Dictionary in _graph.get_connection_list():
		out.append([titles.get(str(connection["from_node"]), ""), titles.get(str(connection["to_node"]), "")])
	out.sort()
	return out

# ---------------------------------------------------------------- the test

## The flag and item atoms the stages' conditions mention.
func test_atoms() -> Array[String]:
	var found: Array[String] = []
	if quest == null:
		return found
	for stage in quest.stages:
		for token in str(stage.get("complete_when", "")).split(" ", false):
			var atom := token.get_slice(">=", 0)
			if (atom.begins_with("flag:") or atom.begins_with("item:")) and not found.has(atom):
				found.append(atom)
	found.sort()
	return found

func set_test_atom(atom: String, on: bool) -> void:
	DialogueTab.set_test_atom(test_state, atom, on)
	run_test()

func _refresh_toggles() -> void:
	for child in _toggles.get_children():
		_toggles.remove_child(child)
		child.queue_free()
	for atom in test_atoms():
		var box := CheckBox.new()
		box.text = atom
		box.button_pressed = RpgCondition.evaluate_on(atom, test_state)
		box.toggled.connect(func(on: bool) -> void: set_test_atom(atom, on))
		_toggles.add_child(box)

## The stage the quest reaches with the pretend state ("done" when it finishes), also shown.
func run_test() -> String:
	if quest == null:
		return ""
	var reached := quest.reached(test_state)
	_test_result.text = "The quest finishes." if reached == RpgQuestDefinition.DONE else "It stops at the stage '%s'." % reached
	_condition_note.text = DialogueTab.condition_preview(_condition.text, test_state)
	return reached
