class_name RpgRaceResults
extends Control
## The screen after a race: who came in where, in what time and for how many points, the parts
## the player won, and the table of the championship. After the last race its heading names
## the champion; for a player who is out it says so. It closes on a press of accept or by
## itself after HOLD_S.

signal finished

const HOLD_S := 10.0
## How large a driver's face is shown beside its name.
const PORTRAIT_PX := 20.0

var _left := HOLD_S
var _done := false

## A time as a screen shows it: 83.456 is "1:23.46".
static func time_text(time_s: float) -> String:
	var hundredths := roundi(maxf(0.0, time_s) * 100.0)
	@warning_ignore("integer_division")
	return "%d:%02d.%02d" % [hundredths / 6000, hundredths / 100 % 60, hundredths % 100]

## The lines of a race, a row of the championship's `record` each: the place, the driver, its
## time (a dash for a car that had not finished) and the points of the place.
static func race_lines(rows: Array[Dictionary]) -> Array[PackedStringArray]:
	var out: Array[PackedStringArray] = []
	for row in rows:
		var finished_it := RpgUtil.to_bool(row.get("finished", false))
		out.append(PackedStringArray([
			"%d." % RpgUtil.to_int(row.get("place", 0)),
			RpgChampionship.driver_name(RpgUtil.to_str(row.get("driver", ""))),
			time_text(RpgUtil.to_float(row.get("time_s", 0.0))) if finished_it else "-",
			"+%d" % RpgUtil.to_int(row.get("points", 0)),
		]))
	return out

## The lines of the championship's table: the place, the driver and its points.
static func table_lines(table: Array[Dictionary]) -> Array[PackedStringArray]:
	var out: Array[PackedStringArray] = []
	for row in table:
		out.append(PackedStringArray([
			"%d." % RpgUtil.to_int(row.get("place", 0)),
			RpgChampionship.driver_name(RpgUtil.to_str(row.get("driver", ""))),
			str(RpgUtil.to_int(row.get("points", 0))),
		]))
	return out

## The line of the parts won in a race ("" for none): "Parts won: Speed, Tyres".
static func parts_text(parts: Array[String]) -> String:
	if parts.is_empty():
		return ""
	var names := PackedStringArray()
	for part in parts:
		names.append(RpgRacingStrings.t("RACE_PART_" + part.to_upper()))
	return RpgRacingStrings.t("RACE_PARTS_WON", [", ".join(names)])

## The heading of the screen: the track, or the champion after the last race, or that the
## player is out.
static func heading_text(track_title: String, table: Array[Dictionary], is_last: bool, is_out: bool) -> String:
	if is_out:
		return RpgRacingStrings.t("RACE_ELIMINATED")
	if is_last and not table.is_empty():
		return RpgRacingStrings.t("RACE_CHAMPION", [RpgChampionship.driver_name(RpgUtil.to_str(table[0].get("driver", "")))])
	return RpgRacingStrings.t("RACE_RESULTS", [track_title])

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	# (with the offsets: a control that is in the tree keeps its size otherwise, which is none)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

## Shows the race of `track_title`: its `rows` (RpgChampionship.record), the `parts` won in
## it and the championship's `table`. `is_last`: it was the last race; `is_out`: the player is
## out of the championship.
func show_results(track_title: String, rows: Array[Dictionary], parts: Array[String], table: Array[Dictionary], is_last: bool = false, is_out: bool = false) -> void:
	for child in get_children():
		child.queue_free()
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.7)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	var center := CenterContainer.new()
	center.name = "Center"
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var box := VBoxContainer.new()
	box.name = "Box"
	center.add_child(box)
	var head := Label.new()
	head.name = "Heading"
	head.text = heading_text(track_title, table, is_last, is_out)
	head.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(head)
	var halves := HBoxContainer.new()
	halves.name = "Halves"
	halves.add_theme_constant_override(&"separation", 32)
	box.add_child(halves)
	_grid(halves, "Race", RpgRacingStrings.t("RACE_THIS_RACE"), race_lines(rows), rows)
	_grid(halves, "Table", RpgRacingStrings.t("RACE_TABLE"), table_lines(table), table)
	var won := parts_text(parts)
	if won != "":
		var parts_label := Label.new()
		parts_label.name = "Parts"
		parts_label.text = won
		parts_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		box.add_child(parts_label)
	_left = HOLD_S
	_done = false

## A titled grid of `lines`; the line of the player is in another colour.
func _grid(parent: Control, grid_name: String, title: String, lines: Array[PackedStringArray], rows: Array[Dictionary]) -> void:
	var column := VBoxContainer.new()
	column.name = grid_name
	parent.add_child(column)
	var caption := Label.new()
	caption.name = "Title"
	caption.text = title
	column.add_child(caption)
	var grid := GridContainer.new()
	grid.name = "Rows"
	grid.columns = lines[0].size() if not lines.is_empty() else 1
	grid.add_theme_constant_override(&"h_separation", 12)
	column.add_child(grid)
	for i in lines.size():
		var mine := RpgUtil.to_bool(rows[i].get("player", false))
		for n in lines[i].size():
			var cell := Label.new()
			cell.text = lines[i][n]
			if n >= 2:
				cell.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
				cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			if mine:
				cell.add_theme_color_override(&"font_color", Color(1.0, 0.9, 0.4))
			var face := RpgRacePeople.portrait_of(RpgUtil.to_str(rows[i].get("driver", ""))) if n == 1 else null
			if face == null:
				grid.add_child(cell)
				continue
			# the driver's face beside its name (T18.19)
			var named := HBoxContainer.new()
			named.name = "Driver%d" % i
			var picture := TextureRect.new()
			picture.name = "Portrait"
			picture.texture = face
			picture.custom_minimum_size = Vector2(PORTRAIT_PX, PORTRAIT_PX)
			picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			picture.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
			named.add_child(picture)
			named.add_child(cell)
			grid.add_child(named)

## The text of the heading (tests).
func heading_shown() -> String:
	var label := get_node_or_null("Center/Box/Heading") as Label
	return label.text if label != null else ""

## The texts of a grid, row by row: "Race" or "Table" (tests).
func grid_texts(grid_name: String) -> Array[PackedStringArray]:
	var out: Array[PackedStringArray] = []
	var grid := get_node_or_null("Center/Box/Halves/%s/Rows" % grid_name) as GridContainer
	if grid == null:
		return out
	var line := PackedStringArray()
	for child in grid.get_children():
		if child.is_queued_for_deletion():
			continue
		var label := child as Label
		if label == null:
			label = child.get_child(child.get_child_count() - 1) as Label  # a face and a name
		if label != null:
			line.append(label.text)
			if line.size() == grid.columns:
				out.append(line)
				line = PackedStringArray()
	return out

func _process(delta: float) -> void:
	_left -= delta
	if _left <= 0.0:
		close()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(&"ui_accept"):
		accept_event()
		close()

func close() -> void:
	if _done:
		return
	_done = true
	finished.emit()
