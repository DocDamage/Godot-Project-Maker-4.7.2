class_name RpgArcadeHighScoreTable
extends Control
## The high-score table as a screen: the ten best runs, and, for a run that made the table, a
## field for the name. `closed` carries the name typed ("" when none was asked for).

signal closed(player_name: String)

var _name_edit: LineEdit = null
var _done := false

## One line per entry: [place, name, score, stage] as text.
static func lines(table: Array[Dictionary]) -> Array:
	var out: Array = []
	for i in table.size():
		var entry := table[i]
		out.append([
			"%2d." % (i + 1),
			RpgUtil.to_str(entry.get("name", "")),
			str(RpgUtil.to_int(entry.get("score", 0))),
			RpgArcadeStrings.t("ARC_STAGE", [RpgUtil.to_int(entry.get("stage", 1), 1)]),
		])
	return out

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	# (with the offsets: a control that is in the tree keeps its size otherwise, which is none)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

## Shows `table`. With `ask_name` a name is asked for (the run made the table) and `closed`
## carries it; `score` is the score of that run.
func show_table(table: Array[Dictionary], ask_name: bool = false, score: int = 0) -> void:
	for child in get_children():
		child.queue_free()
	_done = false
	_name_edit = null
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.75)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var box := VBoxContainer.new()
	box.name = "Box"
	center.add_child(box)
	var heading := Label.new()
	heading.name = "Heading"
	heading.text = RpgArcadeStrings.t("ARC_HIGH_SCORES")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	var grid := GridContainer.new()
	grid.name = "Rows"
	grid.columns = 4
	box.add_child(grid)
	for line: Array in lines(table):
		for cell: Variant in line:
			var label := Label.new()
			label.text = RpgUtil.to_str(cell)
			grid.add_child(label)
	if table.is_empty():
		var none := Label.new()
		none.name = "Empty"
		none.text = RpgArcadeStrings.t("ARC_NO_SCORES")
		box.add_child(none)
	if ask_name:
		var prompt := Label.new()
		prompt.name = "Prompt"
		prompt.text = "%s  (%d)" % [RpgArcadeStrings.t("ARC_NEW_HIGH_SCORE"), score]
		box.add_child(prompt)
		_name_edit = LineEdit.new()
		_name_edit.name = "Name"
		_name_edit.max_length = RpgArcadeHighScores.NAME_LENGTH
		_name_edit.text = RpgArcadeHighScores.DEFAULT_NAME
		_name_edit.text_submitted.connect(_on_submitted)
		box.add_child(_name_edit)
		_name_edit.grab_focus.call_deferred()
	var ok := Button.new()
	ok.name = "Ok"
	ok.text = RpgArcadeStrings.t("ARC_OK")
	ok.pressed.connect(close)
	box.add_child(ok)
	RpgMenuUtil.attach_sounds([ok])
	if not ask_name:
		ok.grab_focus.call_deferred()

func _on_submitted(_text: String) -> void:
	close()

## Cancel closes a table that asks for nothing.
func _unhandled_input(event: InputEvent) -> void:
	if _name_edit == null and not _done and (event.is_action_pressed(&"ui_cancel") or (InputMap.has_action(&"cancel") and event.is_action_pressed(&"cancel"))):
		accept_event()
		close()

func close() -> void:
	if _done:
		return
	_done = true
	closed.emit(RpgArcadeHighScores.clean_name(_name_edit.text) if _name_edit != null else "")
