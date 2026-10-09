@tool
extends "data_tab.gd"
## The Cutscenes tab (T13.19): the sequences in res://game/data/sequences. A step list, a form
## per step (the kinds of RpgSequence.STEP_KINDS; every other command as JSON), entity ids checked
## against the map that is open, JSON export and import, and Test: the sequence plays in the game
## when one is running from the editor, otherwise it is only checked. Every change is one undo
## step.

const SEQUENCES_DIR := "res://game/data/sequences"
const ContentChecks := preload("../tools/content_checks.gd")
const OTHER_KIND := "other (JSON)"
const DEBUG_MESSAGE := "rpg_sequence:run"

var sequence: RpgSequence = null
var sequences_dir := SEQUENCES_DIR  # tests point the tab at their own folder
## Sends a message to the running game: the plugin's debugger link (`send(message, data) -> bool`,
## true when a game took it). Null in tests and without a running game.
var debug_link: Object = null

var _steps: ItemList
var _kind: OptionButton
var _new_kind: OptionButton
var _fields: VBoxContainer
var _json: TextEdit
var _step_note: Label
var _skippable: CheckBox
var _field_edits: Dictionary = {}  # argument -> its LineEdit / CheckBox / OptionButton / TextEdit

func _init() -> void:
	name = "Cutscenes"
	build_top([["New", new_sequence], ["Test", func() -> void: run_test()]])
	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)
	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(190, 0)
	split.add_child(left)
	_steps = ItemList.new()
	_steps.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_steps.item_selected.connect(func(_index: int) -> void: _show_step())
	left.add_child(_steps)
	var add_row := HBoxContainer.new()
	left.add_child(add_row)
	_new_kind = OptionButton.new()
	for entry in RpgSequence.STEP_KINDS:
		_new_kind.add_item(str(entry["kind"]))
	add_row.add_child(_new_kind)
	button(add_row, "Add", func() -> void: add_step(_new_kind.get_item_text(_new_kind.selected)))
	var step_buttons := HBoxContainer.new()
	left.add_child(step_buttons)
	button(step_buttons, "Remove", remove_step)
	button(step_buttons, "Up", func() -> void: move_step(-1))
	button(step_buttons, "Down", func() -> void: move_step(1))
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_kind = OptionButton.new()
	for entry in RpgSequence.STEP_KINDS:
		_kind.add_item(str(entry["kind"]))
	_kind.add_item(OTHER_KIND)
	_kind.item_selected.connect(func(index: int) -> void: set_step_kind(selected_step(), _kind.get_item_text(index)))
	row(form, "Kind", _kind)
	_fields = VBoxContainer.new()
	form.add_child(_fields)
	_json = TextEdit.new()
	_json.custom_minimum_size = Vector2(0, 60)
	_json.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_json.focus_exited.connect(func() -> void: set_step_json(selected_step(), _json.text))
	row(form, "The step as JSON", _json)
	_step_note = note(form)
	_skippable = CheckBox.new()
	_skippable.text = "Cancel skips the rest of this cutscene"
	_skippable.toggled.connect(func(on: bool) -> void: set_skippable(on))
	form.add_child(_skippable)
	build_status()

# ---------------------------------------------------------------- files

func folder() -> String:
	return sequences_dir

func context_object() -> Object:
	return sequence

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgSequence
	if res == null:
		say("%s is not a sequence." % path)
		return false
	sequence = res
	file_path = path
	dirty = false
	_refresh(0)
	say("%s: %d steps." % [path.get_file(), sequence.commands.size()])
	return true

func save() -> bool:
	if sequence == null or file_path == "":
		return false
	var err := ResourceSaver.save(sequence, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

func new_sequence() -> String:
	var made := RpgSequence.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_cutscene")
	made.id = StringName(path.get_file().get_basename())
	made.commands = [RpgSequence.new_step("wait")]
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

static func to_dict(res: RpgSequence) -> Dictionary:
	return {"id": String(res.id), "skippable": res.skippable, "commands": res.commands.duplicate(true)}

## A sequence from {"id", "skippable", "commands": [...]} (or from a bare list of commands).
static func from_json(text: String) -> RpgSequence:
	var parsed: Variant = JSON.parse_string(text)
	var raw_commands: Variant = parsed
	var table := RpgUtil.to_dict(parsed)
	if parsed is Dictionary:
		raw_commands = table.get("commands")
	if not (raw_commands is Array):
		return null
	var made := RpgSequence.new()
	made.id = StringName(str(table.get("id", "")))
	made.skippable = RpgUtil.to_bool(table.get("skippable", false))
	var list: Array = raw_commands
	for raw: Variant in list:
		if raw is Dictionary:
			made.commands.append(_plain(RpgUtil.to_dict(raw)))
	return made

## The value of JSON text, or null when it is not JSON (what a person types is often not, and
## that is no error to log).
static func parse_json(text: String) -> Variant:
	var json := JSON.new()
	return json.data if json.parse(text) == OK else null

## JSON has only one kind of number: whole ones become integers again ([2.0, 0.0] -> [2, 0]).
static func _plain(value: Variant) -> Variant:
	if value is float:
		var number: float = value
		return roundi(number) if float(roundi(number)) == number else number
	if value is Array:
		var out: Array = []
		for item: Variant in RpgUtil.to_array(value):
			out.append(_plain(item))
		return out
	if value is Dictionary:
		var table := {}
		var source: Dictionary = value
		for key: Variant in source:
			table[key] = _plain(source[key])
		return table
	return value

func to_json_text() -> String:
	return JSON.stringify(to_dict(sequence), "  ", false) + "\n" if sequence != null else ""

func import_json(json_path: String) -> String:
	var made := from_json(FileAccess.get_file_as_string(json_path))
	if made == null:
		say("%s is not sequence JSON." % json_path.get_file())
		return ""
	if made.id == &"":
		made.id = StringName(json_path.get_file().get_basename())
	DirAccess.make_dir_recursive_absolute(folder())
	var target := folder().path_join(json_path.get_file().get_basename() + ".tres")
	if ResourceSaver.save(made, target) != OK:
		say("Could not save %s." % target)
		return ""
	file_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- checks

## The problems of the sequence: its commands (RpgSequence.problems_of and what they refer to),
## and the actors the open map does not have (only when a map with entities is open).
func problems() -> Array[String]:
	if sequence == null:
		return []
	var out := ContentChecks.sequence_problems(sequence.commands, {"sequences": folder()})
	var entities := map_entities()
	if not entities.is_empty():
		out.append_array(RpgSequence.entity_problems(sequence.commands, entities))
	return out

## The problems that name step `index` ("command 3 (...)").
func step_problems(index: int) -> Array[String]:
	var out: Array[String] = []
	for problem in problems():
		if problem.begins_with("command %d " % (index + 1)):
			out.append(problem)
	return out

## "⚠ 2. face · bob" (the mark when the step has a problem).
func step_label(index: int) -> String:
	var command := RpgUtil.to_dict(sequence.commands[index])
	var cmd := str(command.get("cmd", ""))
	var kind := RpgSequence.step_kind(cmd)
	var shown := str(kind.get("kind", cmd))
	var about := ""
	for key: String in ["entity", "dialogue", "item", "slot", "seconds", "name", "label", "sequence", "event"]:
		if command.has(key):
			about = " · " + str(command[key])
			break
	return "%s%d. %s%s" % ["⚠ " if not step_problems(index).is_empty() else "", index + 1, shown, about]

# ---------------------------------------------------------------- showing

func selected_step() -> int:
	var picked := _steps.get_selected_items()
	return picked[0] if not picked.is_empty() else -1

func select_step(index: int) -> void:
	if index >= 0 and index < _steps.item_count:
		_steps.select(index)
		_show_step()

func _refresh(select: int = -1) -> void:
	var keep := select if select >= 0 else selected_step()
	_steps.clear()
	if sequence == null:
		return
	for i in sequence.commands.size():
		_steps.add_item(step_label(i))
	if keep >= 0 and keep < _steps.item_count:
		_steps.select(keep)
	_loading = true
	_skippable.button_pressed = sequence.skippable
	_loading = false
	_show_step()

func _show_step() -> void:
	for child in _fields.get_children():
		_fields.remove_child(child)
		child.queue_free()
	_field_edits.clear()
	var index := selected_step()
	if sequence == null or index < 0 or index >= sequence.commands.size():
		_json.text = ""
		_step_note.text = ""
		return
	var command := RpgUtil.to_dict(sequence.commands[index])
	var kind := RpgSequence.step_kind(str(command.get("cmd", "")))
	_loading = true
	_kind.select(_kind.item_count - 1)
	for i in _kind.item_count:
		if _kind.get_item_text(i) == str(kind.get("kind", OTHER_KIND)):
			_kind.select(i)
	var fields: Array = kind.get("fields", [])
	for field: Array in fields:
		_add_field(str(field[0]), str(field[1]), command)
	_json.text = JSON.stringify(command, "", false)
	_loading = false
	_step_note.text = "\n".join(PackedStringArray(step_problems(index)))

func _add_field(key: String, type: String, command: Dictionary) -> void:
	var index := selected_step()
	match type:
		"bool":
			var box := CheckBox.new()
			box.text = key
			box.button_pressed = RpgUtil.to_bool(command.get(key, key == "wait"))
			box.toggled.connect(func(on: bool) -> void: set_step_value(index, key, on))
			_fields.add_child(box)
			_field_edits[key] = box
		"dir":
			var pick := OptionButton.new()
			pick.add_item("")
			for direction in RpgSequence.DIRECTIONS:
				pick.add_item(direction)
			pick.select(maxi(0, RpgSequence.DIRECTIONS.find(str(command.get(key, ""))) + 1))
			pick.item_selected.connect(func(at: int) -> void: set_step_text(index, key, type, pick.get_item_text(at)))
			row(_fields, key, pick)
			_field_edits[key] = pick
		"entity":
			var holder := HBoxContainer.new()
			var edit := _line(index, key, type, command)
			edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			holder.add_child(edit)
			var pick := OptionButton.new()
			pick.tooltip_text = "The entities of the map that is open"
			pick.add_item("(pick)")
			pick.add_item("player")
			for entity in map_entities():
				pick.add_item(entity)
			pick.item_selected.connect(func(at: int) -> void:
				if at > 0:
					set_step_text(index, key, type, pick.get_item_text(at)))
			holder.add_child(pick)
			row(_fields, key, holder)
			_field_edits[key] = edit
		"lines":
			var text := TextEdit.new()
			text.custom_minimum_size = Vector2(0, 50)
			text.placeholder_text = "one text (or text key) per line"
			text.text = field_text(type, command.get(key))
			text.focus_exited.connect(func() -> void: set_step_text(index, key, type, text.text))
			row(_fields, key, text)
			_field_edits[key] = text
		_:
			var edit := _line(index, key, type, command)
			row(_fields, key, edit)
			_field_edits[key] = edit

func _line(index: int, key: String, type: String, command: Dictionary) -> LineEdit:
	var edit := LineEdit.new()
	edit.text = field_text(type, command.get(key))
	if type == "pair":
		edit.placeholder_text = "dx, dy in tiles"
	edit.text_submitted.connect(func(text: String) -> void: set_step_text(index, key, type, text))
	edit.focus_exited.connect(func() -> void: set_step_text(index, key, type, edit.text))
	return edit

# ---------------------------------------------------------------- fields as text

## What a field shows for an argument's value ("" when the argument is not there).
static func field_text(type: String, value: Variant) -> String:
	if value == null:
		return ""
	match type:
		"pair":
			var pair := RpgUtil.to_array(value)
			return "%s, %s" % [str(pair[0]), str(pair[1])] if pair.size() == 2 else ""
		"lines":
			var rows: PackedStringArray = []
			for line: Variant in RpgUtil.to_array(value):
				rows.append(str(line))
			return "\n".join(rows)
		"value":
			return JSON.stringify(value)
	return str(value)

## The argument's value for what was typed; null takes the argument away (an empty field, or
## text that is not what the type needs).
static func parse_field(type: String, text: String) -> Variant:
	var clean := text.strip_edges()
	if clean == "":
		return null
	match type:
		"pair":
			var parts := clean.replace(";", ",").split(",", false)
			if parts.size() != 2 or not parts[0].strip_edges().is_valid_int() or not parts[1].strip_edges().is_valid_int():
				return null
			return [parts[0].strip_edges().to_int(), parts[1].strip_edges().to_int()]
		"float":
			return clean.to_float() if clean.is_valid_float() else null
		"int":
			return clean.to_int() if clean.is_valid_int() else null
		"lines":
			var rows: Array = []
			for line in text.split("\n"):
				if line.strip_edges() != "":
					rows.append(line.strip_edges())
			return rows if not rows.is_empty() else null
		"value":
			var parsed: Variant = parse_json(clean)
			return _plain(parsed) if parsed != null else clean
	return clean

# ---------------------------------------------------------------- edits (one undo step each)

func _apply_commands(value: Array) -> void:
	var typed: Array[Dictionary] = []
	for raw: Variant in value:
		typed.append(RpgUtil.to_dict(raw).duplicate(true))
	sequence.commands = typed
	dirty = true
	_refresh()

func _apply_skippable(on: bool) -> void:
	sequence.skippable = on
	dirty = true
	_refresh()

func _set_commands(action_name: String, commands: Array) -> void:
	if commands == sequence.commands:
		return
	record(action_name, &"_apply_commands", commands, sequence.commands.duplicate(true))

func _valid(index: int) -> bool:
	return not _loading and sequence != null and index >= 0 and index < sequence.commands.size()

## One argument of step `index`; null takes it away.
func set_step_value(index: int, key: String, value: Variant) -> void:
	if not _valid(index):
		return
	var commands: Array = sequence.commands.duplicate(true)
	var command := RpgUtil.to_dict(commands[index])
	if value == null:
		command.erase(key)
	else:
		command[key] = value
	_set_commands("Edit cutscene step", commands)

func set_step_text(index: int, key: String, type: String, text: String) -> void:
	set_step_value(index, key, parse_field(type, text))

## Another kind for step `index`: a new step of that kind (its arguments start over).
func set_step_kind(index: int, kind: String) -> void:
	if not _valid(index) or kind == OTHER_KIND:
		return
	var commands: Array = sequence.commands.duplicate(true)
	if str(RpgUtil.to_dict(commands[index]).get("cmd", "")) == str(RpgSequence.new_step(kind).get("cmd", "")):
		return
	commands[index] = RpgSequence.new_step(kind)
	_set_commands("Change cutscene step", commands)

## The whole step from JSON text (any command). False when the text is not an object with "cmd".
func set_step_json(index: int, text: String) -> bool:
	if not _valid(index):
		return false
	var parsed: Variant = parse_json(text)
	if not (parsed is Dictionary) or str(RpgUtil.to_dict(parsed).get("cmd", "")) == "":
		_step_note.text = "⚠ the step must be a JSON object with \"cmd\""
		return false
	var commands: Array = sequence.commands.duplicate(true)
	commands[index] = _plain(parsed)
	_set_commands("Edit cutscene step", commands)
	return true

func add_step(kind: String) -> void:
	if sequence == null or RpgSequence.new_step(kind).is_empty():
		return
	var commands: Array = sequence.commands.duplicate(true)
	var at := selected_step() + 1 if selected_step() >= 0 else commands.size()
	commands.insert(at, RpgSequence.new_step(kind))
	_set_commands("Add cutscene step", commands)
	_steps.select(at)
	_show_step()

func remove_step() -> void:
	var index := selected_step()
	if sequence == null or index < 0:
		return
	var commands: Array = sequence.commands.duplicate(true)
	commands.remove_at(index)
	_set_commands("Remove cutscene step", commands)

func move_step(by: int) -> void:
	var index := selected_step()
	var to := index + by
	if sequence == null or index < 0 or to < 0 or to >= sequence.commands.size():
		return
	var commands: Array = sequence.commands.duplicate(true)
	var moved: Variant = commands[index]
	commands.remove_at(index)
	commands.insert(to, moved)
	_set_commands("Move cutscene step", commands)
	_steps.select(to)
	_show_step()

func set_skippable(on: bool) -> void:
	if _loading or sequence == null or sequence.skippable == on:
		return
	record("Edit cutscene", &"_apply_skippable", on, sequence.skippable)

# ---------------------------------------------------------------- Test

## Checks the sequence; without problems, and with a game running from the editor, plays it
## there. Returns "played", "checked" (nothing to play it in) or "problems".
func run_test() -> String:
	if sequence == null:
		return ""
	var found := problems()
	if not found.is_empty():
		say("%d problem(s): %s" % [found.size(), found[0]])
		return "problems"
	var sent := false
	if debug_link != null and debug_link.has_method("send"):
		sent = RpgUtil.to_bool(debug_link.call("send", DEBUG_MESSAGE, [sequence.commands.duplicate(true), true]))
	say("Playing in the running game." if sent else "No problems. Run the game from the editor to see it play.")
	return "played" if sent else "checked"
