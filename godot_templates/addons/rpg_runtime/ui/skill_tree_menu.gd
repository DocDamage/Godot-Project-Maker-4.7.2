class_name RpgSkillTreeMenu
extends Control
## The skill trees (1.5.0), opened from the pause menu's Skills: one tab per tree, the skills on
## their grid with lines from what each one requires (bright when met), the points of the actor,
## and the skill in focus: its rank, what it gives, what it still needs. Confirming a skill (or
## Learn) learns a rank; Unlearn gives one back; Reset unlearns the tree for its price. With a
## party, the first button pages through the members. Built in code; every control is on one
## vertical focus ring, and left / right moves along the tabs and along a row of skills.

signal closed

const CELL := Vector2(64, 40)
const BUTTON := Vector2(56, 28)
const LINE_MET := Color(1.0, 0.85, 0.35)
const LINE_UNMET := Color(1, 1, 1, 0.3)
## The keys of the stats a bonus names, for its text.
const STAT_KEYS := {"max_hp": "UI_HP", "max_mp": "UI_MP", "attack": "UI_ATTACK", "defense": "UI_DEFENSE", "speed": "UI_SPEED", "magic": "UI_MAGIC", "resistance": "UI_RESISTANCE"}

var actor_index := 0
var tree_id: StringName = &""
var selected: StringName = &""

var _box: VBoxContainer
var _pager: Button
var _tabs: HBoxContainer
var _points: Label
var _board: Control
var _detail: Label
var _learn: Button
var _unlearn: Button
var _reset: Button
var _back: Button
var _skill_buttons: Dictionary = {}  # skill id -> Button

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
	_box = VBoxContainer.new()
	_box.custom_minimum_size = Vector2(300, 0)
	panel.add_child(_box)
	var heading := Label.new()
	heading.text = tr("UI_SKILLS")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_box.add_child(heading)
	_pager = Button.new()
	_pager.name = "Member"
	_pager.pressed.connect(page.bind(1))
	_box.add_child(_pager)
	_tabs = HBoxContainer.new()
	_tabs.name = "Tabs"
	_box.add_child(_tabs)
	_points = Label.new()
	_points.name = "Points"
	_box.add_child(_points)
	_board = Control.new()
	_board.name = "Board"
	_board.draw.connect(_draw_lines)
	_box.add_child(_board)
	_detail = Label.new()
	_detail.name = "Detail"
	_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.custom_minimum_size = Vector2(280, 48)
	_box.add_child(_detail)
	var row := HBoxContainer.new()
	_box.add_child(row)
	_learn = _button(row, "Learn", "UI_LEARN", func() -> void: learn())
	_unlearn = _button(row, "Unlearn", "UI_UNLEARN", func() -> void: unlearn())
	_reset = _button(row, "Reset", "UI_RESET", func() -> void: reset())
	_back = _button(_box, "Back", "UI_BACK", close)
	var state := RpgUtil.state()
	if state != null and tree_id == &"" and not state.skill_tree_ids().is_empty():
		tree_id = state.skill_tree_ids()[0]
	rebuild()

func _button(parent: Control, node_name: String, key: String, action: Callable) -> Button:
	var b := Button.new()
	b.name = node_name
	b.text = tr(key)
	b.pressed.connect(action)
	parent.add_child(b)
	return b

## The actor whose trees are shown.
func actor_id() -> StringName:
	var state := RpgUtil.state()
	if state == null:
		return &""
	var members := state.party_ids()
	return members[clampi(actor_index, 0, members.size() - 1)] if not members.is_empty() else &""

## The button of a skill on the board (null for one not shown).
func skill_button(skill_id: StringName) -> Button:
	var b: Button = _skill_buttons.get(skill_id)
	return b

func page(by: int) -> void:
	var state := RpgUtil.state()
	if state == null or state.party_ids().size() < 2:
		return
	actor_index = (actor_index + by + state.party_ids().size()) % state.party_ids().size()
	rebuild()

func set_tree(new_tree: StringName) -> void:
	tree_id = new_tree
	selected = &""
	rebuild()

## Builds the tabs and the board again and refocuses the selected skill.
func rebuild() -> void:
	var state := RpgUtil.state()
	for child in _tabs.get_children():
		_tabs.remove_child(child)
		child.queue_free()
	for child in _board.get_children():
		_board.remove_child(child)
		child.queue_free()
	_skill_buttons.clear()
	var tabs: Array[Button] = []
	var tree: RpgSkillTree = state.skill_tree_of(tree_id) if state != null else null
	var who := actor_id()
	_pager.visible = state != null and state.party_ids().size() > 1
	if _pager.visible:
		_pager.text = "< %s (%d/%d) >" % [state.actor_name(who), actor_index + 1, state.party_ids().size()]
	if state != null:
		for each_id in state.skill_tree_ids():
			var each := state.skill_tree_of(each_id)
			var tab := Button.new()
			tab.name = "Tree_%s" % each_id
			tab.toggle_mode = true
			tab.text = tr(each.title) if each.title != "" else String(each_id)
			tab.set_pressed_no_signal(each_id == tree_id)
			tab.pressed.connect(set_tree.bind(each_id))
			_tabs.add_child(tab)
			tabs.append(tab)
	var skills_in_order: Array[Button] = []
	if tree != null:
		var ranks := state.ranks_of(who, tree_id)
		var size := Vector2.ZERO
		var cells: Array = []
		for row in tree.skills:
			cells.append([RpgSkillTree.cell_of(row).y, RpgSkillTree.cell_of(row).x, StringName(str(row.get("id", "")))])
		cells.sort()
		for entry: Array in cells:
			var skill_id: StringName = entry[2]
			var row := tree.skill(skill_id)
			var b := Button.new()
			b.name = "Skill_%s" % skill_id
			b.custom_minimum_size = BUTTON
			b.size = BUTTON
			b.position = Vector2(RpgSkillTree.cell_of(row)) * CELL
			b.clip_text = true
			b.text = "%s %d/%d" % [tr(str(row.get("title", skill_id))), RpgSkillTree.rank_in(ranks, skill_id), RpgSkillTree.max_rank_of(row)]
			b.tooltip_text = tr(str(row.get("title", skill_id)))
			b.focus_entered.connect(_select.bind(skill_id))
			b.pressed.connect(_on_skill_pressed.bind(skill_id))
			_board.add_child(b)
			_skill_buttons[skill_id] = b
			skills_in_order.append(b)
			size = size.max(b.position + BUTTON)
		_board.custom_minimum_size = size
		_points.text = tr("UI_SKILL_POINTS") % state.points_of(who)
		_reset.text = tr("UI_RESET_COST") % tree.reset_gold if tree.reset_gold > 0 else tr("UI_RESET")
		_reset.visible = tree.reset_gold >= 0
	else:
		_board.custom_minimum_size = Vector2.ZERO
		_points.text = ""
		_detail.text = tr("UI_NO_SKILL_TREES")
	_learn.visible = tree != null
	_unlearn.visible = tree != null
	if tree == null:
		_reset.visible = false
	var ring: Array = []
	if _pager.visible:
		ring.append(_pager)
	ring.append_array(tabs)
	ring.append_array(skills_in_order)
	for b: Button in [_learn, _unlearn, _reset, _back]:
		if b.visible:
			ring.append(b)
	RpgMenuUtil.wire_vertical(ring)
	_wire_sideways(tabs)
	_wire_rows(skills_in_order)
	_board.queue_redraw()
	var start: Button = _back
	if selected != &"" and _skill_buttons.has(selected):
		start = _skill_buttons[selected]
	elif not skills_in_order.is_empty():
		start = skills_in_order[0]
	if is_inside_tree():
		start.grab_focus.call_deferred()
	if selected != &"":
		_describe(selected)

func _wire_sideways(buttons: Array[Button]) -> void:
	for i in buttons.size():
		buttons[i].focus_neighbor_left = buttons[i].get_path_to(buttons[(i - 1 + buttons.size()) % buttons.size()])
		buttons[i].focus_neighbor_right = buttons[i].get_path_to(buttons[(i + 1) % buttons.size()])

## Left and right along a row of the board: the skills of the same row, in column order.
func _wire_rows(buttons: Array[Button]) -> void:
	var rows: Dictionary = {}
	for b in buttons:
		var y := roundi(b.position.y)
		if not rows.has(y):
			rows[y] = [] as Array[Button]
		var row_buttons: Array[Button] = rows[y]
		row_buttons.append(b)
	for y: Variant in rows:
		var row_buttons: Array[Button] = rows[y]
		_wire_sideways(row_buttons)

## Lines from each skill to what it requires: bright when the rank is there.
func _draw_lines() -> void:
	var state := RpgUtil.state()
	var tree: RpgSkillTree = state.skill_tree_of(tree_id) if state != null else null
	if tree == null:
		return
	var ranks := state.ranks_of(actor_id(), tree_id)
	for row in tree.skills:
		var to := skill_button(StringName(str(row.get("id", ""))))
		var needs := RpgSkillTree.requires_of(row)
		for other: Variant in needs:
			var from := skill_button(StringName(str(other)))
			if from == null or to == null:
				continue
			var met := RpgSkillTree.rank_in(ranks, StringName(str(other))) >= RpgUtil.to_int(needs[other])
			_board.draw_line(from.position + Vector2(BUTTON.x / 2.0, BUTTON.y), to.position + Vector2(BUTTON.x / 2.0, 0), LINE_MET if met else LINE_UNMET, 2.0)

func _select(skill_id: StringName) -> void:
	selected = skill_id
	_describe(skill_id)

func _on_skill_pressed(skill_id: StringName) -> void:
	selected = skill_id
	learn()

func _describe(skill_id: StringName) -> void:
	var state := RpgUtil.state()
	var tree: RpgSkillTree = state.skill_tree_of(tree_id) if state != null else null
	if tree == null:
		return
	_detail.text = detail_text(state, tree, actor_id(), skill_id)

## The skill's title and rank, its description, what the next rank gives and why it cannot be
## learned now (what it needs, a row not open yet, no points, or fully learned).
static func detail_text(state: RpgGameState, tree: RpgSkillTree, who: StringName, skill_id: StringName) -> String:
	var row := tree.skill(skill_id)
	if row.is_empty():
		return ""
	var ranks := state.ranks_of(who, tree.id)
	var rank := RpgSkillTree.rank_in(ranks, skill_id)
	var lines: PackedStringArray = [
		"%s  %s" % [TranslationServer.translate(str(row.get("title", skill_id))), TranslationServer.translate("UI_RANK") % [rank, RpgSkillTree.max_rank_of(row)]],
	]
	var description := str(row.get("description", ""))
	if description != "":
		lines.append(TranslationServer.translate(description))
	var gives := bonus_text(RpgUtil.to_array(row.get("bonuses", [])))
	if gives != "":
		lines.append(gives)
	match tree.learn_problem(ranks, state.points_of(who), skill_id):
		RpgSkillTree.MAX_RANK:
			lines.append(TranslationServer.translate("UI_MAX_RANK"))
		RpgSkillTree.NEEDS:
			var parts: PackedStringArray = []
			var lacking := tree.missing(ranks, skill_id)
			for other: Variant in lacking:
				parts.append("%s %d" % [TranslationServer.translate(str(tree.skill(StringName(str(other))).get("title", other))), RpgUtil.to_int(lacking[other])])
			lines.append(TranslationServer.translate("UI_SKILL_NEEDS") % ", ".join(parts))
		RpgSkillTree.ROW_LOCKED:
			lines.append(TranslationServer.translate("UI_ROW_LOCKED") % tree.row_needs(RpgSkillTree.cell_of(row).y))
		RpgSkillTree.NO_POINTS:
			lines.append(TranslationServer.translate("UI_NO_POINTS"))
	return "\n".join(lines)

## "+2 Defense, x1.1 Attack": what one rank gives.
static func bonus_text(bonuses: Array) -> String:
	var parts: PackedStringArray = []
	for raw: Variant in bonuses:
		var bonus := RpgUtil.to_dict(raw)
		var stat := str(bonus.get("stat", ""))
		var stat_name := String(TranslationServer.translate(str(STAT_KEYS.get(stat, stat))))
		if bonus.has("add"):
			var add := RpgUtil.to_float(bonus["add"])
			parts.append("%s%s %s" % ["+" if add >= 0.0 else "-", _number(absf(add)), stat_name])
		if bonus.has("mul"):
			parts.append("x%s %s" % [_number(RpgUtil.to_float(bonus["mul"])), stat_name])
	return ", ".join(parts)

## 2 for 2.0, 1.5 for 1.5.
static func _number(value: float) -> String:
	return str(roundi(value)) if is_equal_approx(value, roundf(value)) else str(snappedf(value, 0.01))

## Learns a rank of the selected skill, or says why not. Returns RpgSkillTree's code.
func learn() -> String:
	var state := RpgUtil.state()
	if state == null or selected == &"":
		return RpgSkillTree.UNKNOWN
	var why := state.learn_skill(actor_id(), tree_id, selected)
	if why == RpgSkillTree.OK:
		var tree := state.skill_tree_of(tree_id)
		RpgUtil.notify(tr("UI_SKILL_LEARNED") % tr(str(tree.skill(selected).get("title", selected))))
	else:
		RpgUtil.notify(refusal_text(why))
	rebuild()
	return why

func unlearn() -> String:
	var state := RpgUtil.state()
	if state == null or selected == &"":
		return RpgSkillTree.UNKNOWN
	var why := state.unlearn_skill(actor_id(), tree_id, selected)
	if why != RpgSkillTree.OK:
		RpgUtil.notify(refusal_text(why))
	rebuild()
	return why

func reset() -> String:
	var state := RpgUtil.state()
	if state == null:
		return RpgSkillTree.UNKNOWN
	var why := state.reset_skill_tree(actor_id(), tree_id)
	if why != RpgSkillTree.OK:
		RpgUtil.notify(refusal_text(why))
	rebuild()
	return why

func refusal_text(why: String) -> String:
	match why:
		RpgSkillTree.NO_POINTS:
			return tr("UI_NO_POINTS")
		RpgSkillTree.MAX_RANK:
			return tr("UI_MAX_RANK")
		RpgSkillTree.NEEDS:
			return tr("UI_SKILL_NEEDS") % "…"
		RpgSkillTree.ROW_LOCKED:
			return tr("UI_ROW_LOCKED_SHORT")
		RpgSkillTree.NEEDED:
			return tr("UI_SKILL_NEEDED")
		RpgSkillTree.NOT_LEARNED:
			return tr("UI_SKILL_NOT_LEARNED")
		RpgShopDefinition.NOT_ENOUGH_GOLD:
			return tr("UI_NOT_ENOUGH_GOLD")
	return tr("UI_CANNOT_TRADE")

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	closed.emit()
	queue_free()
