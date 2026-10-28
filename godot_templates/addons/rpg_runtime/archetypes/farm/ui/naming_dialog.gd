class_name RpgNamingDialog
extends CanvasLayer
## Names an animal of the farm (T18.13): a box over the game with what the animal is, its name
## (the name the plan's list gives, editable with the keyboard), an on-screen keyboard for a
## gamepad (shown when the last input came from one: RpgSettings.input_device), and OK. It needs
## no scene: `open()` makes it. The game is paused while it is open; `named` gives the name, or
## the one it started with when it was left empty.

signal named(text: String)

const LAYER := 70
const MAX_LENGTH := 12
## The keys of the on-screen keyboard, a row each; DEL takes the last letter away.
const ROWS: Array[String] = ["ABCDEFGHIJ", "KLMNOPQRST", "UVWXYZ -'"]
const DEL := "DEL"

var edit: LineEdit = null
var keyboard: GridContainer = null
var ok: Button = null
var _start := ""
var _paused_before := false

## Opens a box for the animal of `what` ("Hen") called `start` under `parent` (the tree's root
## when null). Returns it; listen to `named`.
static func open(what: String, start: String, parent: Node = null) -> RpgNamingDialog:
	var made := RpgNamingDialog.new()
	made.name = "NamingDialog"
	made._start = start
	made._build(what)
	var holder := parent if parent != null else RpgUtil.tree().root
	holder.add_child(made)
	return made

func _build(what: String) -> void:
	layer = LAYER
	process_mode = Node.PROCESS_MODE_ALWAYS
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	add_child(panel)
	var column := VBoxContainer.new()
	panel.add_child(column)
	var title := Label.new()
	title.name = "Title"
	title.text = RpgFarmStrings.t("FARM_NAME_ANIMAL", [what])
	column.add_child(title)
	edit = LineEdit.new()
	edit.name = "Name"
	edit.text = _start
	edit.max_length = MAX_LENGTH
	edit.custom_minimum_size = Vector2(140, 0)
	edit.text_submitted.connect(func(_text: String) -> void: confirm())
	column.add_child(edit)
	keyboard = GridContainer.new()
	keyboard.name = "Keyboard"
	keyboard.columns = 10
	for row in ROWS:
		for letter: String in row:
			_key(letter, letter if letter != " " else "_")
	_key(DEL, "<")
	column.add_child(keyboard)
	ok = Button.new()
	ok.name = "OK"
	ok.text = RpgFarmStrings.t("FARM_OK")
	ok.pressed.connect(confirm)
	column.add_child(ok)

func _key(what: String, shown: String) -> void:
	var key := Button.new()
	key.name = "Key_" + ("DEL" if what == DEL else str(what.unicode_at(0)))
	key.text = shown
	key.focus_mode = Control.FOCUS_ALL
	key.pressed.connect(press.bind(what))
	keyboard.add_child(key)

func _ready() -> void:
	var tree := get_tree()
	_paused_before = tree.paused
	tree.paused = true
	var settings := RpgUtil.settings()
	keyboard.visible = settings != null and settings.input_device != RpgInputGlyphs.KEYBOARD
	if keyboard.visible:
		(keyboard.get_child(0) as Control).grab_focus.call_deferred()
	else:
		edit.grab_focus.call_deferred()
		edit.caret_column = edit.text.length()

## A key of the on-screen keyboard: a letter is added (the first one capital, the others small),
## DEL takes the last one away.
func press(what: String) -> void:
	if what == DEL:
		edit.text = edit.text.left(maxi(0, edit.text.length() - 1))
		return
	if edit.text.length() >= MAX_LENGTH:
		return
	edit.text += what if edit.text.is_empty() else what.to_lower()

## The name as it stands (the starting one when the box is empty); `named` is emitted and the box
## closes.
func confirm() -> void:
	var text := edit.text.strip_edges()
	if text.is_empty():
		text = _start
	var tree := get_tree()
	if tree != null and not _paused_before:  # a pause it did not make is not its to lift
		tree.paused = false
	named.emit(text)
	queue_free()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		confirm()
