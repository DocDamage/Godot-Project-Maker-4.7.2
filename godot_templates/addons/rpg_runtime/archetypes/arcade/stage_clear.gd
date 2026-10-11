class_name RpgArcadeStageClear
extends Control
## The tally after a stage: a bonus for the time left under the par time and one for every life,
## added to the score. It closes on a press of accept or by itself after HOLD_S.

signal finished

const TIME_BONUS_PER_S := 100
const LIFE_BONUS := 1000
const HOLD_S := 4.0

var _left := HOLD_S
var _done := false

## The bonus of a stage cleared in `time_s` with `lives` left: {time_bonus, life_bonus, total}.
static func tally(time_s: float, par_time_s: float, lives: int) -> Dictionary:
	var spare := maxi(0, ceili(par_time_s - time_s)) if par_time_s > 0.0 else 0
	var time_bonus := spare * TIME_BONUS_PER_S
	var life_bonus := maxi(0, lives) * LIFE_BONUS
	return {"time_bonus": time_bonus, "life_bonus": life_bonus, "total": time_bonus + life_bonus}

## The lines of the tally, as [label, value] pairs.
static func rows(bonus: Dictionary, score: int) -> Array:
	return [
		[RpgArcadeStrings.t("ARC_TIME_BONUS"), str(RpgUtil.to_int(bonus.get("time_bonus", 0)))],
		[RpgArcadeStrings.t("ARC_LIFE_BONUS"), str(RpgUtil.to_int(bonus.get("life_bonus", 0)))],
		[RpgArcadeStrings.t("ARC_SCORE"), str(score)],
	]

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_preset(Control.PRESET_FULL_RECT)

## Shows the tally of the stage `stage_title`; `score` is the score with the bonus in it.
func show_tally(stage_title: String, bonus: Dictionary, score: int) -> void:
	for child in get_children():
		child.queue_free()
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.6)
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var box := VBoxContainer.new()
	box.name = "Box"
	center.add_child(box)
	var heading := Label.new()
	heading.name = "Heading"
	heading.text = "%s  %s" % [stage_title, RpgArcadeStrings.t("ARC_STAGE_CLEAR")]
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	var grid := GridContainer.new()
	grid.name = "Rows"
	grid.columns = 2
	box.add_child(grid)
	for row: Array in rows(bonus, score):
		var label := Label.new()
		label.text = RpgUtil.to_str(row[0])
		grid.add_child(label)
		var value := Label.new()
		value.text = RpgUtil.to_str(row[1])
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		grid.add_child(value)
	_left = HOLD_S
	_done = false

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
