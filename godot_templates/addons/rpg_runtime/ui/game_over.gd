class_name RpgGameOver
extends Control
## The game-over screen: "You were defeated" with Continue (only with a save), Try again and Quit
## to title. It does nothing itself: it emits `chosen` and RpgDefeatPolicy carries the choice out.

signal chosen(choice: int)

var _done := false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var continue_button := get_node("%Continue") as Button
	var has_save := RpgDefeatPolicy.latest_save_slot() >= 0
	continue_button.visible = has_save
	continue_button.pressed.connect(_choose.bind(RpgDefeatPolicy.Choice.CONTINUE))
	(get_node("%Retry") as Button).pressed.connect(_choose.bind(RpgDefeatPolicy.Choice.RETRY))
	(get_node("%Quit") as Button).pressed.connect(_choose.bind(RpgDefeatPolicy.Choice.QUIT))
	var buttons := RpgMenuUtil.focusables(self)
	RpgMenuUtil.wire_vertical(buttons)  # also attaches the menu sounds
	_focus_first.call_deferred()

func _focus_first() -> void:
	var buttons := RpgMenuUtil.focusables(self)
	if not buttons.is_empty():
		(buttons[0] as Control).grab_focus()

func _choose(choice: int) -> void:
	if _done:
		return
	_done = true
	chosen.emit(choice)
