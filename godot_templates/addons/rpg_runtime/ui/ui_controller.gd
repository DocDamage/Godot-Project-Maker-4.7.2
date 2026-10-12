class_name RpgUiController
extends Node
## Created by boot under SceneRouter. Opens the pause menu on `menu` during gameplay.

var _layer: CanvasLayer = null
var _menu: Control = null
var _closed_frame := -1

var _pending_shop: StringName = &""

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var bus := RpgUtil.events()
	if bus != null:
		bus.shop_requested.connect(_on_shop_requested)
		bus.dialogue_finished.connect(_on_dialogue_finished)

func is_pause_open() -> bool:
	return _menu != null and is_instance_valid(_menu)

func _in_gameplay() -> bool:
	var router := RpgUtil.router()
	if router == null or router.get("current_map") == null or router.is_busy():
		return false
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box != null and box.call("is_open"):
		return false
	var combat := router.combat
	if combat != null and combat.is_in_combat():
		return false
	return not RpgSequenceRunner.running()

func _input(event: InputEvent) -> void:
	# Backing out of a menu ticks (the pause menu and its submenus live under this node).
	if is_pause_open() and event.is_action_pressed("ui_cancel"):
		RpgMenuUtil.play_ui(&"sfx_ui_cancel")

func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("menu"):
		return
	if is_pause_open() or _closed_frame == Engine.get_process_frames() or not _in_gameplay():
		return
	get_viewport().set_input_as_handled()
	open_pause()

# ------------------------------------------------------------------ shops (T12.46)

## `open_shop:<id>` while a dialogue is open waits for it to close; otherwise the shop opens now.
func _on_shop_requested(shop_id: StringName) -> void:
	_pending_shop = shop_id
	var box := RpgUtil.service(&"rpg_dialogue_box")
	if box == null or not box.call("is_open"):
		_open_pending_shop.call_deferred()

func _on_dialogue_finished(_resource: Resource) -> void:
	if _pending_shop != &"":
		_open_pending_shop_later.call_deferred()

# Two physics frames let the dialogue box hand the player their controls back before the pause.
func _open_pending_shop_later() -> void:
	for i in 3:
		await get_tree().physics_frame
	_open_pending_shop()

func _open_pending_shop() -> void:
	var shop_id := _pending_shop
	_pending_shop = &""
	if shop_id != &"":
		open_shop(shop_id)

## Pauses the tree and shows the shop with this id (game/data/shops/<id>.tres). Returns the menu,
## or null when the shop or the menu scene is missing, another menu is open, or the shop is
## closed (a shop with opening hours says so in a toast instead).
func open_shop(shop_id: StringName) -> Control:
	if is_pause_open():
		return null
	var shop := RpgShopDefinition.load_shop(shop_id)
	if shop == null:
		push_error("[RPG-DATA] shop %s not found in %s" % [shop_id, RpgShopDefinition.SHOPS_DIR])
		return null
	var closed := shop.closed_reason()  # "" for every shop without opening hours
	if closed != "":
		RpgUtil.notify(closed)
		return null
	return _open_menu("shop_menu", {"shop": shop})

## Pauses the tree and shows a menu of its own (the save menu at a save station, the credits
## after the last dialogue); the game goes on when it closes. Null when another menu is open or
## the scene is missing.
func open_menu(menu_name: String, args: Dictionary = {}) -> Control:
	if is_pause_open():
		return null
	var menu := _open_menu(menu_name, args)
	if menu != null:
		menu.tree_exited.connect(_resume)
	return menu

func _resume() -> void:
	if not is_inside_tree():
		return
	get_tree().paused = false
	RpgUtil.emit(&"game_paused", [false])

## Pauses the tree and shows the pause menu. Returns the menu (null when the scene is missing).
func open_pause() -> Control:
	return _open_menu("pause_menu", {})

func _open_menu(menu_name: String, args: Dictionary) -> Control:
	var path := RpgMenuUtil.scene_path(menu_name)
	if not ResourceLoader.exists(path):
		push_error("[RPG-UI] %s is missing" % path)
		return null
	if _layer == null:
		_layer = CanvasLayer.new()
		_layer.layer = 60
		_layer.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(_layer)
	_menu = (load(path) as PackedScene).instantiate() as Control
	for key: Variant in args.keys():  # before add_child, so _ready() already sees them
		_menu.set(StringName(str(key)), args[key])
	_layer.add_child(_menu)
	_menu.tree_exited.connect(_on_closed)
	get_tree().paused = true
	RpgUtil.emit(&"game_paused", [true])
	return _menu

func _on_closed() -> void:
	_menu = null
	_closed_frame = Engine.get_process_frames()
