class_name RpgArcadeContinueScreen
extends Control
## After the last life: "Game over", a countdown, Continue and Quit to title. It does nothing
## itself: it emits `chosen` and RpgArcadeMode carries the choice out. The countdown running out
## is Quit.

signal chosen(go_on: bool)

const COUNTDOWN_S := 9.0

var seconds_left := COUNTDOWN_S
var _done := false
var _count: Label = null

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var shade := ColorRect.new()
	shade.color = Color(0, 0, 0, 0.7)
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
	heading.text = RpgArcadeStrings.t("ARC_GAME_OVER")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	_count = Label.new()
	_count.name = "Countdown"
	_count.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_count)
	var go_on := Button.new()
	go_on.name = "Continue"
	go_on.text = RpgArcadeStrings.t("ARC_CONTINUE")
	go_on.pressed.connect(choose.bind(true))
	box.add_child(go_on)
	var quit := Button.new()
	quit.name = "Quit"
	quit.text = RpgArcadeStrings.t("ARC_QUIT")
	quit.pressed.connect(choose.bind(false))
	box.add_child(quit)
	RpgMenuUtil.wire_vertical([go_on, quit])
	go_on.grab_focus.call_deferred()
	_show_count()

func _show_count() -> void:
	if _count != null:
		_count.text = RpgArcadeStrings.t("ARC_CONTINUE_IN", [ceili(maxf(0.0, seconds_left))])

func _process(delta: float) -> void:
	advance(delta)

## One step of the countdown.
func advance(delta: float) -> void:
	if _done:
		return
	seconds_left -= delta
	_show_count()
	if seconds_left <= 0.0:
		choose(false)

func choose(go_on: bool) -> void:
	if _done:
		return
	_done = true
	chosen.emit(go_on)
