@tool
extends VBoxContainer
## The Dialogue tab (T12.61): edit the dialogue resources in res://game/data/dialogue line by line
## (speaker, portrait, text with a BBCode preview, condition, events, choices, jump), with undo
## through the editor, problems flagged inline, a test player against a scratch game state whose
## flags and items you toggle, and JSON export and import.

const DIALOGUE_DIR := "res://game/data/dialogue"
const CATALOG := "res://rpggen/asset_catalog.json"
const JsonIo := preload("../tools/json_io.gd")
const NO_PORTRAIT := "(none)"

var plugin: EditorPlugin = null
var dialogue: RpgDialogueResource = null
var dialogue_path := ""
var dirty := false
var test_state: RpgGameState = RpgGameState.new()
var portraits: Dictionary = {}  # label -> resource path of a PORTRAIT asset

var _files: OptionButton
var _lines: ItemList
var _id: LineEdit
var _speaker: LineEdit
var _portrait: OptionButton
var _text: TextEdit
var _preview: RichTextLabel
var _condition: LineEdit
var _condition_note: Label
var _events: TextEdit
var _events_note: Label
var _choices: TextEdit
var _choices_note: Label
var _next: LineEdit
var _status: Label
var _toggles: VBoxContainer
var _test_text: RichTextLabel
var _test_buttons: HBoxContainer
var _player: RpgDialogueRunner = null
var _loading := false

func _init() -> void:
	name = "Dialogue"
	var top := HBoxContainer.new()
	_files = OptionButton.new()
	_files.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_files.item_selected.connect(func(index: int) -> void: open(_files.get_item_text(index)))
	top.add_child(_files)
	for spec: Array in [["Reload", rescan], ["Save", save], ["Export JSON", _export_dialog], ["Import JSON", _import_dialog]]:
		var button := Button.new()
		button.text = str(spec[0])
		var action: Callable = spec[1]
		button.pressed.connect(action)
		top.add_child(button)
	add_child(top)
	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(split)
	_lines = ItemList.new()
	_lines.custom_minimum_size = Vector2(160, 0)
	_lines.item_selected.connect(func(_index: int) -> void: _show_line())
	split.add_child(_lines)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	split.add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_id = _line_edit(form, "Id (for jumps)", "id")
	_speaker = _line_edit(form, "Speaker", "speaker")
	_portrait = OptionButton.new()
	_portrait.add_item(NO_PORTRAIT)  # filled by rescan(); a line without one shows this
	_portrait.item_selected.connect(_on_portrait)
	_row(form, "Portrait", _portrait)
	_text = TextEdit.new()
	_text.custom_minimum_size = Vector2(0, 70)
	_text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_text.focus_exited.connect(func() -> void: _commit("text", _text.text))
	_text.text_changed.connect(func() -> void: _preview.text = _text.text)
	_row(form, "Text", _text)
	_preview = RichTextLabel.new()
	_preview.bbcode_enabled = true
	_preview.fit_content = true
	_row(form, "Preview", _preview)
	_condition = _line_edit(form, "Condition", "condition")
	_condition.text_changed.connect(func(text: String) -> void: _condition_note.text = condition_preview(text, test_state))
	_condition_note = _note(form)
	_events = TextEdit.new()
	_events.custom_minimum_size = Vector2(0, 50)
	_events.placeholder_text = "one event per line: give_item:potion:2, set_flag:npc.met=true"
	_events.focus_exited.connect(func() -> void: _commit("events", parse_events(_events.text)))
	_row(form, "Events", _events)
	_events_note = _note(form)
	_choices = TextEdit.new()
	_choices.custom_minimum_size = Vector2(0, 50)
	_choices.placeholder_text = "one choice per line: text | next line id | condition"
	_choices.focus_exited.connect(func() -> void: _commit("choices", parse_choices(_choices.text)))
	_row(form, "Choices", _choices)
	_choices_note = _note(form)
	_next = _line_edit(form, "Then go to", "next")
	var test_box := VBoxContainer.new()
	var test_title := Label.new()
	test_title.text = "Test (a scratch game state: toggle what the conditions ask for)"
	test_box.add_child(test_title)
	_toggles = VBoxContainer.new()
	test_box.add_child(_toggles)
	_test_text = RichTextLabel.new()
	_test_text.bbcode_enabled = true
	_test_text.fit_content = true
	test_box.add_child(_test_text)
	_test_buttons = HBoxContainer.new()
	test_box.add_child(_test_buttons)
	var restart := Button.new()
	restart.text = "Play from the start"
	restart.pressed.connect(play_from_start)
	test_box.add_child(restart)
	form.add_child(test_box)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)

func _ready() -> void:
	rescan()

# ---------------------------------------------------------------- small builders

func _row(parent: Control, label_text: String, field: Control) -> void:
	var label := Label.new()
	label.text = label_text
	parent.add_child(label)
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(field)

func _line_edit(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: _commit(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: _commit(property, _typed(property, edit.text)))
	_row(parent, label_text, edit)
	return edit

func _note(parent: Control) -> Label:
	var note := Label.new()
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.add_theme_color_override("font_color", Color(1.0, 0.65, 0.3))
	parent.add_child(note)
	return note

static func _typed(property: String, text: String) -> Variant:
	return StringName(text.strip_edges()) if property in ["id", "next"] else text

# ---------------------------------------------------------------- files

## The dialogue files of the project, sorted.
static func dialogue_files(folder: String = DIALOGUE_DIR) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(folder)
	if dir == null:
		return found
	for file_name in dir.get_files():
		var clean := file_name.trim_suffix(".remap")
		if clean.ends_with(".tres") and not found.has(folder.path_join(clean)):
			found.append(folder.path_join(clean))
	found.sort()
	return found

func rescan() -> void:
	portraits = portrait_assets(JsonIo.read(CATALOG))
	_portrait.clear()
	_portrait.add_item(NO_PORTRAIT)
	var labels := portraits.keys()
	labels.sort()
	for label: String in labels:
		_portrait.add_item(label)
	_files.clear()
	var files := dialogue_files()
	for file_path in files:
		_files.add_item(file_path)
	if dialogue_path in files:
		_files.select(files.find(dialogue_path))
	elif not files.is_empty():
		open(files[0])
	else:
		_status.text = "No dialogue yet: put .tres files (RpgDialogueResource) in %s, or import JSON." % DIALOGUE_DIR

## label -> texture path of every PORTRAIT image of the catalog.
static func portrait_assets(catalog: Variant) -> Dictionary:
	var out := {}
	if not (catalog is Dictionary):
		return out
	var data: Dictionary = catalog
	var assets: Array = data.get("assets", [])
	for raw: Variant in assets:
		if not (raw is Dictionary):
			continue
		var asset: Dictionary = raw
		var detected: Dictionary = asset.get("detected", {})
		var overrides: Dictionary = asset.get("overrides", {})
		var facets := detected.merged(overrides, true)
		if str(facets.get("role", "")) == "PORTRAIT" and str(asset.get("kind", "image")) == "image":
			var file := "res://" + str(asset.get("path", ""))
			out[file.get_file().get_basename()] = file
	return out

func open(file_path: String) -> bool:
	var res := ResourceLoader.load(file_path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgDialogueResource
	if res == null:
		_status.text = "%s is not a dialogue resource." % file_path
		return false
	dialogue = res
	dialogue_path = file_path
	dirty = false
	_refresh_lines()
	if not dialogue.lines.is_empty():
		_lines.select(0)
		_show_line()
	_refresh_toggles()
	play_from_start()
	_status.text = "%s: %d lines." % [file_path.get_file(), dialogue.lines.size()]
	return true

## Writes the resource (the editor's undo history stays).
func save() -> bool:
	if dialogue == null or dialogue_path == "":
		return false
	var err := ResourceSaver.save(dialogue, dialogue_path)
	dirty = err != OK
	_status.text = "Saved %s." % dialogue_path.get_file() if err == OK else "Could not save (error %d)." % err
	return err == OK

func _export_dialog() -> void:
	if dialogue == null:
		return
	var json_path := dialogue_path.get_basename() + ".json"
	var f := FileAccess.open(json_path, FileAccess.WRITE)
	if f == null:
		_status.text = "Could not write %s." % json_path
		return
	f.store_string(RpgDialogueJson.to_json(dialogue))
	f.close()
	_status.text = "Exported %s." % json_path

func _import_dialog() -> void:
	var dialog := EditorFileDialog.new()
	dialog.file_mode = EditorFileDialog.FILE_MODE_OPEN_FILE
	dialog.add_filter("*.json", "Dialogue JSON")
	dialog.file_selected.connect(func(json_path: String) -> void:
		import_json(json_path)
		dialog.queue_free())
	add_child(dialog)
	dialog.popup_file_dialog()

## Makes <name>.tres in the dialogue folder from a JSON file (an existing one is replaced).
func import_json(json_path: String) -> String:
	var res := RpgDialogueJson.from_json(FileAccess.get_file_as_string(json_path))
	if res == null:
		_status.text = "%s is not dialogue JSON." % json_path.get_file()
		return ""
	DirAccess.make_dir_recursive_absolute(DIALOGUE_DIR)
	var target := DIALOGUE_DIR.path_join(json_path.get_file().get_basename() + ".tres")
	if ResourceSaver.save(res, target) != OK:
		_status.text = "Could not save %s." % target
		return ""
	dialogue_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- lines

func current_line() -> RpgDialogueLine:
	var picked := _lines.get_selected_items()
	if dialogue == null or picked.is_empty() or picked[0] >= dialogue.lines.size():
		return null
	return dialogue.lines[picked[0]]

## "a · Ana: Hello there…" with a warning sign when the line has a problem.
func line_label(index: int) -> String:
	var line := dialogue.lines[index]
	var head := "%s · " % String(line.id) if line.id != &"" else ""
	var who := "%s: " % line.speaker if line.speaker != "" else ""
	var text := line.text.replace("\n", " ")
	var mark := "⚠ " if not line_problems(line, line_ids(dialogue)).is_empty() else ""
	return "%s%d. %s%s%s" % [mark, index + 1, head, who, text.left(40)]

func _refresh_lines() -> void:
	var keep := _lines.get_selected_items()
	_lines.clear()
	if dialogue == null:
		return
	for i in dialogue.lines.size():
		_lines.add_item(line_label(i))
	if not keep.is_empty() and keep[0] < _lines.item_count:
		_lines.select(keep[0])

func _show_line() -> void:
	var line := current_line()
	if line == null:
		return
	_loading = true
	_id.text = String(line.id)
	_speaker.text = line.speaker
	_portrait.select(0)
	if line.portrait != null:
		for i in _portrait.item_count:
			if portraits.get(_portrait.get_item_text(i), "") == line.portrait.resource_path:
				_portrait.select(i)
	_text.text = line.text
	_preview.text = line.text
	_condition.text = line.condition
	_events.text = "\n".join(line.events)
	_choices.text = choices_text(line.choices)
	_next.text = String(line.next)
	_loading = false
	_update_notes(line)

func _update_notes(line: RpgDialogueLine) -> void:
	_condition_note.text = condition_preview(line.condition, test_state)
	var event_notes: PackedStringArray = []
	for event in line.events:
		var why := RpgDialogueRunner.event_problem(event)
		if why != "":
			event_notes.append("⚠ " + why)
	_events_note.text = "\n".join(event_notes)
	var choice_notes: PackedStringArray = []
	var ids := line_ids(dialogue)
	for choice in line.choices:
		if choice.next != &"" and not ids.has(choice.next):
			choice_notes.append("⚠ no line has the id '%s'" % choice.next)
		for why in RpgCondition.problems(choice.condition):
			choice_notes.append("⚠ " + why)
	_choices_note.text = "\n".join(choice_notes)

func _on_portrait(index: int) -> void:
	var label := _portrait.get_item_text(index)
	var file := str(portraits.get(label, ""))
	var texture: Texture2D = null
	if file != "" and ResourceLoader.exists(file):
		texture = load(file) as Texture2D
	_commit("portrait", texture)

## One change to the selected line, through the editor's undo history when there is one.
func _commit(property: String, value: Variant) -> void:
	var line := current_line()
	if _loading or line == null:
		return
	var old: Variant = line.get(property)
	if old == value:
		return
	if property == "choices":
		var before: Array = old
		var after: Array = value
		if choices_text(before) == choices_text(after):
			return
	var undo := plugin.get_undo_redo() if plugin != null else null
	if undo != null:
		undo.create_action("Edit dialogue line", UndoRedo.MERGE_DISABLE, line)
		undo.add_do_property(line, property, value)
		undo.add_undo_property(line, property, old)
		undo.add_do_method(self, "_after_edit")
		undo.add_undo_method(self, "_after_edit")
		undo.commit_action()
	else:
		line.set(property, value)
		_after_edit()

func _after_edit() -> void:
	dirty = true
	_refresh_lines()
	_show_line()
	_refresh_toggles()

## Sets one property of line `index` (for scripts and tests; the same path as the form).
func edit_line(index: int, property: String, value: Variant) -> void:
	_lines.select(index)
	_show_line()
	_commit(property, value)

# ---------------------------------------------------------------- parsing and checks

static func parse_events(text: String) -> PackedStringArray:
	var out: PackedStringArray = []
	for raw in text.split("\n"):
		if raw.strip_edges() != "":
			out.append(raw.strip_edges())
	return out

## "text | next | condition" per line.
static func parse_choices(text: String) -> Array[RpgDialogueChoice]:
	var out: Array[RpgDialogueChoice] = []
	for raw in text.split("\n"):
		if raw.strip_edges() == "":
			continue
		var parts := raw.split("|")
		var choice := RpgDialogueChoice.new()
		choice.text = parts[0].strip_edges()
		choice.next = StringName(parts[1].strip_edges()) if parts.size() > 1 else &""
		choice.condition = parts[2].strip_edges() if parts.size() > 2 else ""
		out.append(choice)
	return out

static func choices_text(choices: Array) -> String:
	var rows: PackedStringArray = []
	for value: Variant in choices:
		if not (value is RpgDialogueChoice):
			continue
		var choice: RpgDialogueChoice = value
		var row := "%s | %s" % [choice.text, String(choice.next)]
		if choice.condition != "":
			row += " | " + choice.condition
		rows.append(row)
	return "\n".join(rows)

static func line_ids(res: RpgDialogueResource) -> Array[StringName]:
	var ids: Array[StringName] = []
	if res != null:
		for line in res.lines:
			if line.id != &"":
				ids.append(line.id)
	return ids

## Every problem of a line: its condition, events, jump and choices.
static func line_problems(line: RpgDialogueLine, ids: Array[StringName]) -> PackedStringArray:
	var found := RpgCondition.problems(line.condition)
	for event in line.events:
		var why := RpgDialogueRunner.event_problem(event)
		if why != "":
			found.append(why)
	if line.next != &"" and not ids.has(line.next):
		found.append("no line has the id '%s'" % line.next)
	for choice in line.choices:
		found.append_array(RpgCondition.problems(choice.condition))
		if choice.next != &"" and not ids.has(choice.next):
			found.append("no line has the id '%s'" % choice.next)
	return found

## What a condition means with the test state: the problems, or whether the line would show.
static func condition_preview(expr: String, state: RpgGameState) -> String:
	if expr.strip_edges() == "":
		return ""
	var found := RpgCondition.problems(expr)
	if not found.is_empty():
		return "⚠ " + "; ".join(found)
	return "with the test state: %s" % ("shown" if RpgCondition.evaluate_on(expr, state) else "skipped")

## The flag and item atoms the dialogue's conditions mention (the test toggles).
static func test_atoms(res: RpgDialogueResource) -> Array[String]:
	var found: Array[String] = []
	if res == null:
		return found
	var exprs: PackedStringArray = []
	for line in res.lines:
		exprs.append(line.condition)
		for choice in line.choices:
			exprs.append(choice.condition)
	for expr in exprs:
		for token in expr.split(" ", false):
			var atom := token.get_slice(">=", 0)
			if (atom.begins_with("flag:") or atom.begins_with("item:")) and not found.has(atom):
				found.append(atom)
	found.sort()
	return found

## Turns one flag or item of the test state on or off.
static func set_test_atom(state: RpgGameState, atom: String, on: bool) -> void:
	if atom.begins_with("flag:"):
		var body := atom.trim_prefix("flag:")
		var dot := body.rfind(".")
		if dot > 0:
			state.set_flag(body.substr(0, dot), body.substr(dot + 1), on)
	elif atom.begins_with("item:"):
		var id := StringName(atom.trim_prefix("item:"))
		var have := state.inventory.count(id)
		if on and have == 0:
			state.inventory.add(id, 99)
		elif not on and have > 0:
			state.inventory.remove(id, have)

func _refresh_toggles() -> void:
	for child in _toggles.get_children():
		child.queue_free()
	for atom in test_atoms(dialogue):
		var box := CheckBox.new()
		box.text = atom
		box.button_pressed = RpgCondition.evaluate_on(atom, test_state)
		box.toggled.connect(func(on: bool) -> void:
			set_test_atom(test_state, atom, on)
			var line := current_line()
			if line != null:
				_update_notes(line))
		_toggles.add_child(box)

# ---------------------------------------------------------------- the test player

## Plays the dialogue from its first line against the test state (events change the test state
## only).
func play_from_start() -> void:
	_player = RpgDialogueRunner.new()
	_player.condition_check = func(expr: String) -> bool: return RpgCondition.evaluate_on(expr, test_state)
	_player.event_runner = func(event: String) -> bool: return RpgDialogueRunner.execute_event_on(event, test_state)
	if dialogue != null:
		_player.start(dialogue)
	_show_player()

func _show_player() -> void:
	for child in _test_buttons.get_children():
		child.queue_free()
	if _player == null or _player.is_finished():
		_test_text.text = "[i](the end)[/i]"
		return
	var line := _player.current()
	_test_text.text = ("[b]%s[/b]: " % line.speaker if line.speaker != "" else "") + line.text
	var choices := _player.visible_choices()
	if choices.is_empty():
		var next := Button.new()
		next.text = "Next"
		next.pressed.connect(func() -> void:
			_player.advance()
			_show_player())
		_test_buttons.add_child(next)
	for i in choices.size():
		var pick := Button.new()
		pick.text = choices[i].text
		pick.pressed.connect(func() -> void:
			_player.choose(i)
			_show_player())
		_test_buttons.add_child(pick)

## The test player's text now (for tests).
func test_text() -> String:
	return _test_text.text
