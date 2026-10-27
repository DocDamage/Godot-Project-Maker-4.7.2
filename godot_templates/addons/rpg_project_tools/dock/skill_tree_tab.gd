@tool
extends "data_tab.gd"
## The Skills tab (1.5.0): the skill trees in res://game/data/skill_trees. The tree's id, title,
## points per row and the price of a reset; its skills in a list with a form (id, title,
## description, column and row, ranks, cost a rank, what it requires, what a rank gives, the
## battle skill it teaches); a picture of the grid with a line from each requirement; what is
## wrong with the tree; JSON export and import. Every change is one undo step.

const TREES_DIR := "res://game/data/skill_trees"
## A skill's box in the picture, and the room a cell takes.
const BOX := Vector2(64, 22)
const PICTURE_CELL := Vector2(74, 34)
const PICTURE_MARGIN := 6.0

var tree: RpgSkillTree = null
var trees_dir := TREES_DIR  # tests point the tab at their own folder

var _skills: ItemList
var _tree_id: LineEdit
var _tree_title: LineEdit
var _per_row: SpinBox
var _reset_gold: SpinBox
var _skill_id: LineEdit
var _skill_title: LineEdit
var _description: LineEdit
var _column: SpinBox
var _row: SpinBox
var _max_rank: SpinBox
var _cost: SpinBox
var _requires: LineEdit
var _bonuses: TextEdit
var _battle_skill: LineEdit
var _problems: Label
var _picture: Control

func _init() -> void:
	name = "Skills"
	build_top([["New", new_tree]])
	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)
	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(150, 0)
	split.add_child(left)
	_skills = ItemList.new()
	_skills.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_skills.item_selected.connect(func(_index: int) -> void: _show_skill())
	left.add_child(_skills)
	var buttons := HBoxContainer.new()
	left.add_child(buttons)
	button(buttons, "Add", add_skill)
	button(buttons, "Remove", remove_skill)
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
	_tree_id = _tree_field(form, "Tree id", "id")
	_tree_title = _tree_field(form, "Tree title (a text key)", "title")
	_per_row = _spin(form, "Points that open each next row (0: all open)", 0, 99, func(value: int) -> void: set_tree_property("points_per_row", value))
	_reset_gold = _spin(form, "Gold a reset costs (-1: no reset)", -1, 999999, func(value: int) -> void: set_tree_property("reset_gold", value))
	form.add_child(HSeparator.new())
	_skill_id = _skill_field(form, "Skill id", "id")
	_skill_title = _skill_field(form, "Title (a text key)", "title")
	_description = _skill_field(form, "Description (a text key)", "description")
	_column = _spin(form, "Column", 0, 20, func(value: int) -> void: _edit_cell(value, -1))
	_row = _spin(form, "Row", 0, 20, func(value: int) -> void: _edit_cell(-1, value))
	_max_rank = _spin(form, "Ranks", 1, 99, func(value: int) -> void: edit_skill(selected_skill(), "max_rank", value))
	_cost = _spin(form, "Points a rank", 0, 99, func(value: int) -> void: edit_skill(selected_skill(), "cost", value))
	_requires = _skill_field(form, "Requires (skill rank, ...: blade 2, guard)", "requires")
	_bonuses = TextEdit.new()
	_bonuses.custom_minimum_size = Vector2(0, 46)
	_bonuses.placeholder_text = "one per line, what a rank gives: attack +2, speed x1.1"
	_bonuses.focus_exited.connect(func() -> void: edit_skill(selected_skill(), "bonuses", parse_bonuses(_bonuses.text)))
	row(form, "Bonuses", _bonuses)
	_battle_skill = _skill_field(form, "Teaches the battle skill (its id; empty: none)", "skill")
	_problems = note(form)
	_picture = Control.new()
	_picture.custom_minimum_size = Vector2(0, 120)
	_picture.clip_contents = true
	_picture.draw.connect(_draw_picture)
	right.add_child(_picture)
	build_status()

func _tree_field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_tree_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_tree_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

func _skill_field(parent: Control, label_text: String, key: String) -> LineEdit:
	var edit := LineEdit.new()
	var commit := func(text: String) -> void:
		var value: Variant = parse_requires(text) if key == "requires" else text.strip_edges()
		edit_skill(selected_skill(), key, value)
	edit.text_submitted.connect(commit)
	edit.focus_exited.connect(func() -> void: commit.call(edit.text))
	row(parent, label_text, edit)
	return edit

func _spin(parent: Control, label_text: String, low: int, high: int, commit: Callable) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = low
	spin.max_value = high
	spin.rounded = true
	spin.value_changed.connect(func(value: float) -> void:
		if not _loading:
			commit.call(roundi(value)))
	row(parent, label_text, spin)
	return spin

static func _typed(property: String, text: String) -> Variant:
	return StringName(text.strip_edges()) if property == "id" else text.strip_edges()

# ---------------------------------------------------------------- files

func folder() -> String:
	return trees_dir

func context_object() -> Object:
	return tree

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgSkillTree
	if res == null:
		say("%s is not a skill tree." % path)
		return false
	tree = res
	file_path = path
	dirty = false
	_refresh(0)
	say("%s: %d skills." % [path.get_file(), tree.skills.size()])
	return true

func save() -> bool:
	if tree == null or file_path == "":
		return false
	var err := ResourceSaver.save(tree, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

## A new tree with one skill, saved at once.
func new_tree() -> String:
	var made := RpgSkillTree.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_tree")
	made.id = StringName(path.get_file().get_basename())
	made.title = "SKILLS_%s_TITLE" % String(made.id).to_upper()
	var skills: Array[Dictionary] = [{"id": "first", "title": "First skill", "cell": [0, 0], "max_rank": 1, "cost": 1}]
	made.skills = skills
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(tree.to_dict(), "  ", false) + "\n" if tree != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not (RpgUtil.to_dict(parsed).get("skills") is Array):
		say("%s is not skill tree JSON." % json_path.get_file())
		return ""
	var made := RpgSkillTree.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)))
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

func selected_skill() -> int:
	var picked := _skills.get_selected_items()
	return picked[0] if not picked.is_empty() else -1

func select_skill(index: int) -> void:
	if index >= 0 and index < _skills.item_count:
		_skills.select(index)
		_show_skill()

## "⚠ blade (0, 0)" (the mark when a problem names the skill).
func skill_label(index: int) -> String:
	var skill := tree.skills[index]
	var skill_id := str(skill.get("id", ""))
	var cell := RpgSkillTree.cell_of(skill)
	var marked := problems().any(func(problem: String) -> bool: return problem.contains("(%s)" % skill_id))
	return "%s%s (%d, %d)" % ["⚠ " if marked else "", skill_id, cell.x, cell.y]

func problems() -> Array[String]:
	return tree.problems() if tree != null else [] as Array[String]

func _refresh(select: int = -1) -> void:
	var keep := select if select >= 0 else selected_skill()
	_skills.clear()
	if tree == null:
		return
	for i in tree.skills.size():
		_skills.add_item(skill_label(i))
	if keep >= 0 and keep < _skills.item_count:
		_skills.select(keep)
	_loading = true
	_tree_id.text = String(tree.id)
	_tree_title.text = tree.title
	_per_row.value = tree.points_per_row
	_reset_gold.value = tree.reset_gold
	_loading = false
	_show_skill()
	_problems.text = "\n".join(PackedStringArray(problems()))
	_picture.queue_redraw()

func _show_skill() -> void:
	var index := selected_skill()
	var skill: Dictionary = tree.skills[index] if tree != null and index >= 0 else {}
	_loading = true
	_skill_id.text = str(skill.get("id", ""))
	_skill_title.text = str(skill.get("title", ""))
	_description.text = str(skill.get("description", ""))
	var cell := RpgSkillTree.cell_of(skill)
	_column.value = cell.x
	_row.value = cell.y
	_max_rank.value = RpgSkillTree.max_rank_of(skill)
	_cost.value = RpgSkillTree.cost_of(skill) if skill.has("cost") else 1
	_requires.text = requires_text(RpgSkillTree.requires_of(skill))
	_bonuses.text = bonuses_text(RpgUtil.to_array(skill.get("bonuses", [])))
	_battle_skill.text = str(skill.get("skill", ""))
	_loading = false
	_picture.queue_redraw()

## The tree as boxes on its grid, a line from each requirement, the selected skill outlined.
func _draw_picture() -> void:
	_picture.draw_rect(Rect2(Vector2.ZERO, _picture.size), Color(0, 0, 0, 0.25))
	if tree == null:
		return
	var font := _picture.get_theme_default_font()
	var font_size := _picture.get_theme_default_font_size()
	for skill in tree.skills:
		var to := box_of(skill)
		var needs := RpgSkillTree.requires_of(skill)
		for other: Variant in needs:
			var needed := tree.skill(StringName(str(other)))
			if not needed.is_empty():
				var from := box_of(needed)
				_picture.draw_line(from.position + Vector2(BOX.x / 2.0, BOX.y), to.position + Vector2(BOX.x / 2.0, 0), Color(1, 0.85, 0.35), 2.0)
	var selected := selected_skill()
	for i in tree.skills.size():
		var box := box_of(tree.skills[i])
		_picture.draw_rect(box, Color(0.2, 0.25, 0.35))
		_picture.draw_rect(box, Color.WHITE if i == selected else Color(1, 1, 1, 0.4), false, 2.0 if i == selected else 1.0)
		_picture.draw_string(font, box.position + Vector2(4, BOX.y - 6), str(tree.skills[i].get("id", "")), HORIZONTAL_ALIGNMENT_LEFT, BOX.x - 8, mini(font_size, 12))

## Where a skill's box is in the picture.
static func box_of(skill: Dictionary) -> Rect2:
	var cell := RpgSkillTree.cell_of(skill)
	return Rect2(Vector2(PICTURE_MARGIN, PICTURE_MARGIN) + Vector2(cell) * PICTURE_CELL, BOX)

# ---------------------------------------------------------------- edits (one undo step each)

func _apply_skills(value: Array) -> void:
	var typed: Array[Dictionary] = []
	for raw: Variant in value:
		typed.append(RpgUtil.to_dict(raw).duplicate(true))
	tree.skills = typed
	dirty = true
	_refresh()

func _apply_tree(value: Array) -> void:
	tree.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func _set_skills(action_name: String, skills: Array) -> void:
	record(action_name, &"_apply_skills", skills, tree.skills.duplicate(true))

## One key of skill `index`; an empty value takes an optional key away.
func edit_skill(index: int, key: String, value: Variant) -> void:
	if _loading or tree == null or index < 0 or index >= tree.skills.size():
		return
	var skills: Array = tree.skills.duplicate(true)
	var skill := RpgUtil.to_dict(skills[index])
	var empty: bool = (value is String and str(value) == "") or (value is Dictionary and RpgUtil.to_dict(value).is_empty()) \
		or (value is Array and str(value) == "[]")
	var same: bool = skill.has(key) and typeof(skill[key]) == typeof(value) and skill[key] == value
	if same or (empty and not skill.has(key)):
		return
	if empty and key != "id":
		skill.erase(key)
	else:
		skill[key] = value
	skills[index] = skill
	_set_skills("Edit skill", skills)

func _edit_cell(column: int, row_index: int) -> void:
	var index := selected_skill()
	if tree == null or index < 0:
		return
	var cell := RpgSkillTree.cell_of(tree.skills[index])
	edit_skill(index, "cell", [column if column >= 0 else cell.x, row_index if row_index >= 0 else cell.y])

func set_tree_property(property: String, value: Variant) -> void:
	if _loading or tree == null:
		return
	var old: Variant = tree.get(property)
	if typeof(old) == typeof(value) and old == value:
		return
	record("Edit skill tree", &"_apply_tree", [property, value], [property, old])

## A new skill on the first free cell of the bottom row.
func add_skill() -> void:
	if tree == null:
		return
	var skills: Array = tree.skills.duplicate(true)
	var n := skills.size() + 1
	while tree.skill_ids().has(StringName("skill_%d" % n)):
		n += 1
	var bottom := 0
	for skill in tree.skills:
		bottom = maxi(bottom, RpgSkillTree.cell_of(skill).y)
	var column := 0
	for skill in tree.skills:
		if RpgSkillTree.cell_of(skill).y == bottom:
			column = maxi(column, RpgSkillTree.cell_of(skill).x + 1)
	skills.append({"id": "skill_%d" % n, "title": "", "cell": [column, bottom], "max_rank": 1, "cost": 1})
	_set_skills("Add skill", skills)
	select_skill(tree.skills.size() - 1)

func remove_skill() -> void:
	var index := selected_skill()
	if tree == null or index < 0:
		return
	var skills: Array = tree.skills.duplicate(true)
	skills.remove_at(index)
	_set_skills("Remove skill", skills)

# ---------------------------------------------------------------- the texts of the form

## "blade 2, guard" -> {"blade": 2, "guard": 1}.
static func parse_requires(text: String) -> Dictionary:
	var out := {}
	for part in text.split(",", false):
		var words := part.strip_edges().split(" ", false)
		if words.is_empty():
			continue
		out[words[0]] = words[1].to_int() if words.size() > 1 and words[1].is_valid_int() else 1
	return out

static func requires_text(requires: Dictionary) -> String:
	var parts: PackedStringArray = []
	for skill_id: Variant in requires:
		var rank := RpgUtil.to_int(requires[skill_id])
		parts.append(str(skill_id) if rank == 1 else "%s %d" % [skill_id, rank])
	return ", ".join(parts)

## "attack +2" and "speed x1.1" lines -> [{stat, add}, {stat, mul}] (a line that is neither is
## left out).
static func parse_bonuses(text: String) -> Array:
	var out: Array = []
	for raw in text.replace(",", "\n").split("\n", false):
		var words := raw.strip_edges().split(" ", false)
		if words.size() != 2:
			continue
		var amount := words[1]
		if amount.begins_with("x") and amount.substr(1).is_valid_float():
			out.append({"stat": words[0], "mul": amount.substr(1).to_float()})
		elif amount.is_valid_float():
			out.append({"stat": words[0], "add": _whole(amount.to_float())})
	return out

static func bonuses_text(bonuses: Array) -> String:
	var lines: PackedStringArray = []
	for raw: Variant in bonuses:
		var bonus := RpgUtil.to_dict(raw)
		var stat := str(bonus.get("stat", ""))
		if bonus.has("add"):
			var add := RpgUtil.to_float(bonus["add"])
			lines.append("%s %s%s" % [stat, "+" if add >= 0.0 else "", str(_whole(add))])
		if bonus.has("mul"):
			lines.append("%s x%s" % [stat, str(RpgUtil.to_float(bonus["mul"]))])
	return "\n".join(lines)

## 2 for 2.0 (a whole number stays an int), 1.5 for 1.5.
static func _whole(value: float) -> Variant:
	return roundi(value) if is_equal_approx(value, roundf(value)) else value
