class_name RpgArcadeHud
extends CanvasLayer
## The HUD of the arcade kinds (layer 20): lives, score and multiplier, the name of the stage, and
## the health of a boss while one is on. The kinds add rows of their own with set_row (bombs, the
## weapon, the lap). Shown only while a stage is played.

const MARGIN := 8.0
const BAR_WIDTH := 160.0

var _mode: RpgArcadeMode = null
var _stage: RpgArcadeStage = null
var _boss: RpgArcadeBoss = null
var _lives: Label = null
var _score: Label = null
var _multiplier: Label = null
var _stage_name: Label = null
var _rows: VBoxContainer = null
var _boss_box: VBoxContainer = null
var _boss_name: Label = null
var _boss_bar: ProgressBar = null
var _row_labels: Dictionary = {}

func _ready() -> void:
	layer = 20
	var left := VBoxContainer.new()
	left.name = "Left"
	left.position = Vector2(MARGIN, MARGIN)
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(left)
	_lives = _label(left, "Lives")
	_stage_name = _label(left, "Stage")
	_rows = VBoxContainer.new()
	_rows.name = "Rows"
	_rows.mouse_filter = Control.MOUSE_FILTER_IGNORE
	left.add_child(_rows)
	var right := VBoxContainer.new()
	right.name = "Right"
	right.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	right.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	right.position = Vector2(-MARGIN, MARGIN)
	right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(right)
	_score = _label(right, "Score")
	_score.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_multiplier = _label(right, "Multiplier")
	_multiplier.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_boss_box = VBoxContainer.new()
	_boss_box.name = "Boss"
	_boss_box.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_boss_box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_boss_box.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_boss_box.position = Vector2(0.0, -MARGIN)
	_boss_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_boss_box.visible = false
	add_child(_boss_box)
	_boss_name = _label(_boss_box, "Name")
	_boss_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_boss_bar = ProgressBar.new()
	_boss_bar.name = "Bar"
	_boss_bar.custom_minimum_size = Vector2(BAR_WIDTH, 8.0)
	_boss_bar.show_percentage = false
	_boss_bar.max_value = 1.0
	_boss_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_boss_box.add_child(_boss_bar)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_map_changed)
	bind(RpgArcadeMode.current())

func _label(parent: Control, label_name: String) -> Label:
	var label := Label.new()
	label.name = label_name
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

func _on_map_changed(_map_id: StringName) -> void:
	if _mode == null:
		bind(RpgArcadeMode.current())
	refresh()

## Follows `mode`: its lives, its score and the stages it starts.
func bind(mode: RpgArcadeMode) -> void:
	if mode == null or mode == _mode:
		refresh()
		return
	_mode = mode
	mode.lives.changed.connect(_on_changed)
	mode.score.changed.connect(_on_changed)
	mode.stage_started.connect(_on_stage_started)
	if mode.stage != null:
		_follow(mode.stage)
	refresh()

func _on_changed(_a: Variant = null, _b: Variant = null) -> void:
	refresh()

func _on_stage_started(_index: int) -> void:
	if _mode != null and _mode.stage != null:
		_follow(_mode.stage)
	refresh()

func _follow(stage: RpgArcadeStage) -> void:
	if stage == _stage:
		return
	_stage = stage
	hide_boss()
	stage.boss_started.connect(_on_boss_started)
	stage.cleared.connect(hide_boss)

func _on_boss_started(boss: RpgArcadeBoss) -> void:
	_boss = boss
	boss.health_changed.connect(_on_boss_health)
	boss.finished.connect(hide_boss)
	show_boss(boss.boss_name, boss.fraction())

func _on_boss_health(_health: int, _max_health: int) -> void:
	if _boss != null and is_instance_valid(_boss):
		show_boss(_boss.boss_name, _boss.fraction())

## Shows the health bar of a boss: its name and how much is left (0..1).
func show_boss(boss_name: String, fraction: float) -> void:
	_boss_box.visible = true
	_boss_name.text = tr(boss_name) if boss_name != "" else RpgArcadeStrings.t("ARC_WARNING")
	_boss_bar.value = clampf(fraction, 0.0, 1.0)

func hide_boss() -> void:
	_boss = null
	_boss_box.visible = false

## A row of the kind under the lives ("bombs", "weapon", "lap"); an empty text takes it away.
func set_row(key: String, text: String) -> void:
	var label: Label = _row_labels.get(key)
	if text == "":
		if label != null:
			_row_labels.erase(key)
			label.queue_free()
		return
	if label == null:
		label = _label(_rows, key.to_pascal_case())
		_row_labels[key] = label
	label.text = text

## The text of a row, or "".
func row_text(key: String) -> String:
	var label: Label = _row_labels.get(key)
	return label.text if label != null else ""

func lives_text() -> String:
	return _lives.text

func score_text() -> String:
	return _score.text

func multiplier_text() -> String:
	return _multiplier.text

func stage_text() -> String:
	return _stage_name.text

func boss_shown() -> bool:
	return _boss_box.visible

func boss_fraction() -> float:
	return float(_boss_bar.value)

func refresh() -> void:
	if _lives == null:
		return
	visible = _mode != null and _mode.stage != null and is_instance_valid(_mode.stage)
	if _mode == null:
		return
	_lives.text = "%s: %d" % [RpgArcadeStrings.t("ARC_LIVES"), _mode.lives.count]
	_score.text = "%s: %d" % [RpgArcadeStrings.t("ARC_SCORE"), _mode.score.points]
	_multiplier.text = RpgArcadeStrings.t("ARC_MULTIPLIER", [_mode.score.multiplier])
	_multiplier.visible = _mode.score.multiplier > 1
	_stage_name.text = _mode.stage.title_text() if visible else ""
