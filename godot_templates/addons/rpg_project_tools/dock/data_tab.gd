@tool
extends VBoxContainer
## What the Quests and Cutscenes tabs (T13.19) share: the file row, the status line, one undo step
## per change, and the entity ids of the map that is open in the editor.

const EntityIds := preload("../tools/entity_ids.gd")

var plugin: EditorPlugin = null
## Where changes are recorded: the editor's undo history (set from `plugin`), a plain UndoRedo
## (tests), or null (changes apply directly).
var undo_redo: Object = null
## The map whose entities the pickers offer; null takes the scene open in the editor (tests set it).
var map_root: Node = null
var file_path := ""
var dirty := false

var _files: OptionButton
var _status: Label
var _loading := false

## The row every tab starts with: the file list and its buttons.
func build_top(extra: Array = []) -> void:
	var top := HBoxContainer.new()
	_files = OptionButton.new()
	_files.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_files.item_selected.connect(func(index: int) -> void: open(_files.get_item_text(index)))
	top.add_child(_files)
	var specs: Array = [["Reload", rescan], ["Save", save], ["Export JSON", export_json], ["Import JSON", _import_dialog]]
	specs.append_array(extra)
	for spec: Array in specs:
		var button := Button.new()
		button.text = str(spec[0])
		var action: Callable = spec[1]
		button.pressed.connect(action)
		top.add_child(button)
	add_child(top)

func build_status() -> void:
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)

func status_text() -> String:
	return _status.text if _status != null else ""

func say(text: String) -> void:
	if _status != null:
		_status.text = text

func _ready() -> void:
	if plugin != null and undo_redo == null:
		undo_redo = plugin.get_undo_redo()
	rescan()

# ---------------------------------------------------------------- to be filled in by a tab

func folder() -> String:
	return ""

func open(_path: String) -> bool:
	return false

func save() -> bool:
	return false

func to_json_text() -> String:
	return ""

## Makes the .tres of a JSON file in `folder()`; returns its path, or "".
func import_json(_json_path: String) -> String:
	return ""

func context_object() -> Object:
	return null

# ---------------------------------------------------------------- files

## The .tres files of a folder, sorted.
static func tres_files(dir_path: String) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	for file_name in dir.get_files():
		var clean := file_name.trim_suffix(".remap")
		if clean.ends_with(".tres") and not found.has(dir_path.path_join(clean)):
			found.append(dir_path.path_join(clean))
	found.sort()
	return found

func rescan() -> void:
	_files.clear()
	var files := tres_files(folder())
	for path in files:
		_files.add_item(path)
	if file_path in files:
		_files.select(files.find(file_path))
	elif not files.is_empty():
		open(files[0])
	else:
		say("Nothing in %s yet: use New, or Import JSON." % folder())

func export_json() -> String:
	if file_path == "":
		return ""
	var json_path := file_path.get_basename() + ".json"
	var f := FileAccess.open(json_path, FileAccess.WRITE)
	if f == null:
		say("Could not write %s." % json_path)
		return ""
	f.store_string(to_json_text())
	f.close()
	say("Exported %s." % json_path)
	return json_path

func _import_dialog() -> void:
	var dialog := EditorFileDialog.new()
	dialog.file_mode = EditorFileDialog.FILE_MODE_OPEN_FILE
	dialog.add_filter("*.json", "JSON")
	dialog.file_selected.connect(func(json_path: String) -> void:
		import_json(json_path)
		dialog.queue_free())
	add_child(dialog)
	dialog.popup_file_dialog()

## A name in `folder()` that no file has yet: <base>.tres, <base>_2.tres, ...
func free_path(base: String) -> String:
	var candidate := folder().path_join(base + ".tres")
	var n := 2
	while FileAccess.file_exists(candidate):
		candidate = folder().path_join("%s_%d.tres" % [base, n])
		n += 1
	return candidate

# ---------------------------------------------------------------- undo

## One change as one undo step: `target.method(new_value)` now, `target.method(old_value)` on
## undo. With the editor's history Ctrl+Z takes it back; in a test a plain UndoRedo does.
func record(action_name: String, method: StringName, new_value: Variant, old_value: Variant) -> void:
	if undo_redo is UndoRedo:
		var plain := undo_redo as UndoRedo
		plain.create_action(action_name)
		plain.add_do_method(Callable(self, method).bind(new_value))
		plain.add_undo_method(Callable(self, method).bind(old_value))
		plain.commit_action()
	elif undo_redo != null:  # EditorUndoRedoManager
		undo_redo.call("create_action", action_name, UndoRedo.MERGE_DISABLE, context_object())
		undo_redo.call("add_do_method", self, method, new_value)
		undo_redo.call("add_undo_method", self, method, old_value)
		undo_redo.call("commit_action")
	else:
		call(method, new_value)

# ---------------------------------------------------------------- the open map

## The entity ids of the map that is open in the editor (or of `map_root`), sorted.
func map_entities() -> Array[String]:
	var root := map_root
	if root == null and plugin != null:
		root = EditorInterface.get_edited_scene_root()
	return entities_of(root)

static func entities_of(root: Node) -> Array[String]:
	var out: Array[String] = []
	if root == null:
		return out
	for node in EntityIds.entity_nodes(root):
		var id := str(node.get("entity_id"))
		if id != "" and not out.has(id):
			out.append(id)
	out.sort()
	return out

# ---------------------------------------------------------------- small builders

func row(parent: Control, label_text: String, field: Control) -> void:
	var label := Label.new()
	label.text = label_text
	parent.add_child(label)
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(field)

func note(parent: Control) -> Label:
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_color_override("font_color", Color(1.0, 0.65, 0.3))
	parent.add_child(label)
	return label

func button(parent: Control, text: String, action: Callable) -> Button:
	var made := Button.new()
	made.text = text
	made.pressed.connect(action)
	parent.add_child(made)
	return made
