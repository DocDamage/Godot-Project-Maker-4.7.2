class_name RpgPauseMenu
extends Control
## Opens on `menu` during gameplay and pauses the tree. Resume, Inventory, Status, Save, Load,
## Settings, Title. `cancel` closes it.

signal closed

var _submenu: Control = null

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var save := RpgUtil.autoload(&"SaveManager")
	(get_node("%Load") as Button).disabled = save == null or not save.any_save()
	(get_node("%Resume") as Button).pressed.connect(close)
	(get_node("%Inventory") as Button).pressed.connect(_open.bind("inventory_menu", {}))
	(get_node("%Status") as Button).pressed.connect(_open.bind("status_menu", {}))
	(get_node("%Save") as Button).pressed.connect(_open.bind("save_load_menu", {"mode": "save"}))
	(get_node("%Load") as Button).pressed.connect(_open.bind("save_load_menu", {"mode": "load"}))
	(get_node("%Settings") as Button).pressed.connect(_open.bind("settings_menu", {}))
	(get_node("%Title") as Button).pressed.connect(_to_title)
	_focus_resume.call_deferred()

func _focus_resume() -> void:
	(get_node("%Resume") as Button).grab_focus()

func _open(menu_name: String, args: Dictionary) -> void:
	if _submenu != null:
		return
	var menu := RpgMenuUtil.open_submenu(self, menu_name, args)
	if menu == null:
		return
	_submenu = menu
	menu.tree_exited.connect(_on_submenu_closed)

func _on_submenu_closed() -> void:
	_submenu = null
	if is_inside_tree():
		_focus_resume.call_deferred()

func _unhandled_input(event: InputEvent) -> void:
	if _submenu == null and event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func _to_title() -> void:
	close()
	var router := RpgUtil.router()
	if router != null:
		router.go_to(RpgMenuUtil.TITLE_SCENE)

## Unpauses the tree and removes the menu.
func close() -> void:
	get_tree().paused = false
	RpgUtil.emit(&"game_paused", [false])
	closed.emit()
	queue_free()
