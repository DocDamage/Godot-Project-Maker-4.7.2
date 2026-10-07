class_name RpgTitleScreen
extends Control
## Title: New Game, Continue (disabled without a save), Load, Settings, Quit.

var _submenu: Control = null

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
	(get_node("%Quit") as Button).pressed.connect(_on_quit)
	RpgMenuUtil.attach_sounds(RpgMenuUtil.focusables(self))
	_start_music()
	_focus_initial.call_deferred()

## The title music: the scene's `music_asset_id` meta (set by the builder from the sound slots).
func _start_music() -> void:
	var wanted := str(get_meta("music_asset_id", ""))
	var router := RpgUtil.router()
	var audio: Variant = router.get("audio") if router != null else null
	if wanted != "" and audio != null and wanted != str(audio.get("current_music_id")):
		audio.call("play_music", wanted)

func _save_manager() -> Node:
	return RpgUtil.autoload(&"SaveManager")

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
