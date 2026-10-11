class_name RpgShmupHud
extends RpgArcadeHud
## The HUD of a shoot-em-up: the arcade HUD with the bombs left, the weapon with its level and
## the high score. A game that scrolls up is played in the middle of a wide screen, and the
## HUD uses the two strips beside the play area as panels, as an arcade board does: the high
## score, the stage, the bombs and the weapon on the left, the score and the lives on the right.
## A game that scrolls right (or a screen with no room beside the play area) keeps the HUD over
## the picture.

## A strip narrower than this is no panel.
const MIN_PANEL := 48.0
const PANEL_COLOR := Color(0.05, 0.05, 0.09)

## The game scrolls up: the HUD goes into the strips beside the play area when there are any.
@export var panels: bool = false

var _high: Label = null
var _best := 0
var _panel_width := 0.0

func _ready() -> void:
	super._ready()
	_high = Label.new()
	_high.name = "HighScore"
	_high.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var left := get_node("Left") as Control
	var right := get_node("Right") as Control
	if panels and lay_out_panels(_view_size()):
		left.add_child(_high)
		left.move_child(_high, 0)
		_lives.reparent(right)
	else:
		_high.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		right.add_child(_high)
	read_best()
	refresh()

func _view_size() -> Vector2:
	var viewport := get_viewport()
	return viewport.get_visible_rect().size if viewport != null else Vector2.ZERO

## Puts a panel on each strip beside the play area of a screen of `view` px. False (and no
## panel) when the strips are narrower than MIN_PANEL.
func lay_out_panels(view: Vector2) -> bool:
	var area := RpgShmupMath.play_area(view, "vertical")
	var side := (view.x - area.size.x) * 0.5
	if side < MIN_PANEL:
		return false
	_panel_width = side
	for at: Array in [["PanelLeft", 0.0], ["PanelRight", view.x - side]]:
		var panel := ColorRect.new()
		panel.name = RpgUtil.to_str(at[0])
		panel.color = PANEL_COLOR
		panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
		panel.position = Vector2(RpgUtil.to_float(at[1]), 0.0)
		panel.size = Vector2(side, view.y)
		add_child(panel)
		move_child(panel, 0)
	return true

## How wide each side panel is, in px (0 without panels).
func panel_width() -> float:
	return _panel_width

## Reads the best score of the table again (a new stage, a finished run).
func read_best() -> void:
	var table := RpgArcadeHighScores.read()
	_best = RpgUtil.to_int(table[0].get("score", 0)) if not table.is_empty() else 0

func high_score_text() -> String:
	return _high.text if _high != null else ""

func _on_stage_started(index: int) -> void:
	read_best()
	super._on_stage_started(index)

func refresh() -> void:
	super.refresh()
	if _high == null:
		return
	var now := _mode.score.points if _mode != null else 0
	_high.text = RpgShmupStrings.t("SHM_HIGH", [maxi(_best, now)])

func _process(_delta: float) -> void:
	show_ship(_ship())

func _ship() -> RpgShmupShip:
	var mode := RpgArcadeMode.current()
	if mode is RpgShmupMode:
		var found := (mode as RpgShmupMode).ship
		return found if found != null and is_instance_valid(found) else null
	return null

## Fills the rows from `ship` (none takes them away).
func show_ship(ship: RpgShmupShip) -> void:
	var blast := ship.bomb() if ship != null else null
	var gun := ship.weapon() if ship != null else null
	set_row("bombs", RpgShmupStrings.t("SHM_BOMBS", [blast.count]) if blast != null else "")
	set_row("weapon", RpgShmupStrings.t("SHM_WEAPON", [RpgShmupStrings.weapon_name(gun.kind), gun.level]) if gun != null else "")
