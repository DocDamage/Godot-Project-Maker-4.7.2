class_name RpgTitleScreen
extends Control
## Title: New Game, Continue (disabled without a save), Load, Settings, Credits, Quit.

var _submenu: Control = null
var _hint: Label = null  # "[Enter] Select" for the device used last (T12.55)

func _ready() -> void:
	(get_node("%Title") as Label).text = str(ProjectSettings.get_setting("application/config/name", "Game"))
	var version := str(ProjectSettings.get_setting("application/config/version", ""))
	var version_label := get_node_or_null("%Version") as Label
	if version_label != null:
		version_label.text = "v" + version if version != "" else ""
		version_label.visible = version != ""
	var save := _save_manager()
	var has_save: bool = save != null and save.any_save()
	var continue_button := get_node("%Continue") as Button
	continue_button.disabled = not has_save
	(get_node("%Load") as Button).disabled = not has_save
	(get_node("%NewGame") as Button).pressed.connect(_on_new_game)
	continue_button.pressed.connect(_on_continue)
	(get_node("%Load") as Button).pressed.connect(_on_load)
	(get_node("%Settings") as Button).pressed.connect(_on_settings)
	var credits := get_node_or_null("%Credits") as Button  # projects built before the credits have none
	if credits != null:
		credits.pressed.connect(_open.bind("credits_menu", {}))
	(get_node("%Quit") as Button).pressed.connect(_on_quit)
	# a kind of game may add entries of its own (the high scores of an arcade game, T16.07)
	var router := RpgUtil.router()
	var mode: Node = router.combat if router != null else null
	if mode != null and mode.has_method(&"customize_title_screen"):
		mode.call(&"customize_title_screen", self)
	RpgMenuUtil.attach_sounds(RpgMenuUtil.focusables(self))
	_add_hint()
	_start_music()
	_focus_initial.call_deferred()

func _add_hint() -> void:
	_hint = Label.new()
	_hint.name = "InputHint"
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_hint)
	_hint.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	_update_hint()
	_hint.offset_top = -_hint.get_minimum_size().y - 4.0
	var settings := RpgUtil.settings()
	if settings != null:
		settings.input_device_changed.connect(_on_input_device_changed)

func hint_text() -> String:
	return RpgInputGlyphs.hint([["ui_accept", tr("UI_HINT_SELECT")]])

func _update_hint() -> void:
	if _hint != null:
		_hint.text = hint_text()

## The title music: the scene's `music_asset_id` meta (set by the builder from the sound slots).
func _start_music() -> void:
	var wanted := str(get_meta("music_asset_id", ""))
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if wanted != "" and audio != null and wanted != str(audio.get("current_music_id")):
		audio.call("play_music", wanted)

func _save_manager() -> RpgSaveManager:
	return RpgUtil.save_manager()

func _focus_initial() -> void:
	var continue_button := get_node("%Continue") as Button
	if not continue_button.disabled:
		continue_button.grab_focus()
	else:
		(get_node("%NewGame") as Button).grab_focus()

func _on_new_game() -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	if state == null or router == null:
		push_error("[RPG-UI] GameState or SceneRouter is missing")
		return
	state.new_game()
	router.go_to(state.current_map, state.current_spawn)

## Loads the most recently saved slot.
func _on_continue() -> void:
	var save := _save_manager()
	if save == null:
		return
	var best_slot := -1
	var best_time := ""
	for slot in range(save.AUTOSAVE_SLOT, save.SLOTS + 1):
		var h: Dictionary = save.header(slot)
		if h.is_empty():
			continue
		var stamp := str(h.get("saved_at", ""))
		if best_slot < 0 or stamp > best_time:
			best_slot = slot
			best_time = stamp
	if best_slot < 0 or not save.load(best_slot):
		RpgUtil.notify(tr("UI_LOAD_FAILED"))

func _on_load() -> void:
	_open("save_load_menu", {"mode": "load"})

func _on_settings() -> void:
	_open("settings_menu", {})

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
	_focus_initial.call_deferred()

func _on_quit() -> void:
	get_tree().quit()

func _on_input_device_changed(_device: String) -> void:
	_update_hint()

func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSLATION_CHANGED and is_node_ready():
		_update_hint()  # the hint is set in code, so it does not follow the locale by itself
