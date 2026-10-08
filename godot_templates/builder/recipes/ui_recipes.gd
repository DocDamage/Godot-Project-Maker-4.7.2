extends RefCounted
## Builds the UI scenes under res://generated/scenes/ui/: dialogue box, title screen, pause menu,
## inventory, status, save/load, settings, notification and the basic HUD. Scripts live in
## addons/rpg_runtime/ui/ and find their nodes by unique name (%Name).

const RECIPE_VERSION := 6

const SceneUtil := preload("../lib/scene_util.gd")
const UiUtil := preload("../lib/ui_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const UI_DIR := "res://generated/scenes/ui/"
const SCRIPTS := "res://addons/rpg_runtime/ui/"

const SCENES: Array[String] = [
	"dialogue_box", "title_screen", "pause_menu", "inventory_menu", "status_menu",
	"save_load_menu", "settings_menu", "notification", "hud_basic", "game_over",
]

static func scene_path(scene_name: String) -> String:
	return UI_DIR + scene_name + ".tscn"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for s in SCENES:
		out.append(scene_path(s))
	return out

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "scenes": SCENES, "title_music": _title_music(ctx)})

## The asset id of the title music (sound slot music_title), "" for none.
func _title_music(ctx: BuildContext) -> String:
	return JsonUtil.to_str(ctx.section("sounds").get("music_title", ""))

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for scene_name in SCENES:
		var root: Node = call("_build_" + scene_name)
		if scene_name == "title_screen" and _title_music(ctx) != "":
			root.set_meta("music_asset_id", _title_music(ctx))
		var err := SceneUtil.save_scene(root, scene_path(scene_name))
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": scene_path(scene_name), "err": err}, scene_path(scene_name)))
	return issues

# ---------------------------------------------------------------- menus

func _menu_buttons(box: Control, names_keys: Array) -> Array:
	var buttons: Array = []
	for pair: Array in names_keys:
		var button_name: String = pair[0]
		var button_key: String = pair[1]
		buttons.append(UiUtil.button(box, button_name, button_key))
	UiUtil.wire_vertical(buttons)
	return buttons

func _build_title_screen() -> Node:
	var root := UiUtil.control_root("TitleScreen", SCRIPTS + "title_screen.gd")
	var bg := ColorRect.new()
	bg.name = "Background"
	bg.color = Color("#10131a")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var box := UiUtil.center_panel(root, Vector2(200, 0))
	var title := UiUtil.label(box, "Title", "", true)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var version := UiUtil.label(box, "Version", "", true)  # the game version (filled in at runtime)
	version.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_menu_buttons(box, [
		["NewGame", "UI_NEW_GAME"], ["Continue", "UI_CONTINUE"], ["Load", "UI_LOAD"],
		["Settings", "UI_SETTINGS"], ["Quit", "UI_QUIT"],
	])
	return root

func _build_game_over() -> Node:
	var root := UiUtil.control_root("GameOver", SCRIPTS + "game_over.gd")
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	UiUtil.dim_background(root, 0.75)
	var box := UiUtil.center_panel(root, Vector2(220, 0))
	var title := UiUtil.label(box, "Title", "UI_GAME_OVER_TITLE")
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_menu_buttons(box, [
		["Continue", "UI_GAME_OVER_CONTINUE"], ["Retry", "UI_GAME_OVER_RETRY"], ["Quit", "UI_GAME_OVER_QUIT"],
	])
	return root

func _build_pause_menu() -> Node:
	var root := UiUtil.control_root("PauseMenu", SCRIPTS + "pause_menu.gd")
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	UiUtil.dim_background(root)
	var box := UiUtil.center_panel(root, Vector2(160, 0))
	var info := UiUtil.label(box, "Info", "", true)  # the map and the play time (filled in at runtime)
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_menu_buttons(box, [
		["Resume", "UI_RESUME"], ["Inventory", "UI_INVENTORY"], ["Status", "UI_STATUS"],
		["Save", "UI_SAVE"], ["Load", "UI_LOAD"], ["Settings", "UI_SETTINGS"], ["Title", "UI_TITLE"],
	])
	return root

func _build_inventory_menu() -> Node:
	var root := UiUtil.control_root("InventoryMenu", SCRIPTS + "inventory_menu.gd")
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	UiUtil.dim_background(root, 0.85)
	var box := UiUtil.center_panel(root, Vector2(300, 0))
	UiUtil.label(box, "Heading", "UI_INVENTORY")
	var grid := GridContainer.new()
	grid.name = "Grid"
	grid.columns = 6
	UiUtil.unique(grid)
	box.add_child(grid)
	var desc := UiUtil.label(box, "Description", "UI_SELECT_ITEM", true)
	desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	desc.custom_minimum_size = Vector2(280, 40)
	var row := HBoxContainer.new()
	row.name = "Buttons"
	box.add_child(row)
	var use_button := UiUtil.button(row, "Use", "UI_USE")
	var back := UiUtil.button(row, "Back", "UI_BACK")
	use_button.focus_neighbor_left = use_button.get_path_to(back)
	use_button.focus_neighbor_right = use_button.get_path_to(back)
	back.focus_neighbor_left = back.get_path_to(use_button)
	back.focus_neighbor_right = back.get_path_to(use_button)
	use_button.focus_neighbor_top = use_button.get_path_to(back)
	use_button.focus_neighbor_bottom = use_button.get_path_to(back)
	back.focus_neighbor_top = back.get_path_to(use_button)
	back.focus_neighbor_bottom = back.get_path_to(use_button)
	return root

func _build_status_menu() -> Node:
	var root := UiUtil.control_root("StatusMenu", SCRIPTS + "status_menu.gd")
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	UiUtil.dim_background(root, 0.85)
	var box := UiUtil.center_panel(root, Vector2(220, 0))
	UiUtil.label(box, "Heading", "UI_STATUS")
	var stats := VBoxContainer.new()
	stats.name = "Stats"
	UiUtil.unique(stats)
	box.add_child(stats)
	var back := UiUtil.button(box, "Back", "UI_BACK")
	UiUtil.wire_vertical([back])
	return root

func _build_save_load_menu() -> Node:
	var root := UiUtil.control_root("SaveLoadMenu", SCRIPTS + "save_load_menu.gd")
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	UiUtil.dim_background(root, 0.85)
	var box := UiUtil.center_panel(root, Vector2(320, 0))
	UiUtil.label(box, "Heading", "UI_SAVE", true)
	var rows: Array = []
	for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
		rows.append(["Slot%d" % slot, "UI_AUTOSAVE" if slot == RpgSaveManager.AUTOSAVE_SLOT else "UI_SLOT"])
	rows.append(["Back", "UI_BACK"])
	_menu_buttons(box, rows)
	return root

func _slider_row(box: Control, row_name: String, text_key: String) -> void:
	var row := HBoxContainer.new()
	row.name = row_name + "Row"
	box.add_child(row)
	var label := Label.new()
	label.name = "Label"
	label.text = text_key
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(label)
	var slider := HSlider.new()
	slider.name = row_name
	slider.custom_minimum_size = Vector2(120, 0)
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	UiUtil.unique(slider)
	row.add_child(slider)

func _option_row(box: Control, row_name: String, text_key: String) -> void:
	var row := HBoxContainer.new()
	row.name = row_name + "Row"
	box.add_child(row)
	var label := Label.new()
	label.name = "Label"
	label.text = text_key
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(label)
	var option := OptionButton.new()
	option.name = row_name
	UiUtil.unique(option)
	row.add_child(option)

func _build_settings_menu() -> Node:
	var root := UiUtil.control_root("SettingsMenu", SCRIPTS + "settings_menu.gd")
	root.process_mode = Node.PROCESS_MODE_ALWAYS
	UiUtil.dim_background(root, 0.85)
	var box := UiUtil.center_panel(root, Vector2(360, 0))
	UiUtil.label(box, "Heading", "UI_SETTINGS")
	var scroll := ScrollContainer.new()
	scroll.name = "Scroll"
	scroll.custom_minimum_size = Vector2(340, 190)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)
	var inner := VBoxContainer.new()
	inner.name = "Inner"
	inner.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(inner)
	_slider_row(inner, "MasterSlider", "UI_VOLUME_MASTER")
	_slider_row(inner, "MusicSlider", "UI_VOLUME_MUSIC")
	_slider_row(inner, "SfxSlider", "UI_VOLUME_SFX")
	_slider_row(inner, "UiSlider", "UI_VOLUME_UI")
	var fullscreen := CheckButton.new()
	fullscreen.name = "Fullscreen"
	fullscreen.text = "UI_FULLSCREEN"
	UiUtil.unique(fullscreen)
	inner.add_child(fullscreen)
	var autosave := CheckButton.new()
	autosave.name = "Autosave"
	autosave.text = "UI_AUTOSAVE"
	UiUtil.unique(autosave)
	inner.add_child(autosave)
	var shake := CheckButton.new()
	shake.name = "ScreenShake"
	shake.text = "UI_SCREEN_SHAKE"
	UiUtil.unique(shake)
	inner.add_child(shake)
	_option_row(inner, "TextSpeed", "UI_TEXT_SPEED")
	_option_row(inner, "UiScale", "UI_UI_SCALE")
	UiUtil.label(inner, "ControlsHeading", "UI_CONTROLS")
	var controls := VBoxContainer.new()
	controls.name = "Controls"
	UiUtil.unique(controls)
	inner.add_child(controls)
	UiUtil.button(box, "Back", "UI_BACK")
	return root

# ---------------------------------------------------------------- overlays

func _build_dialogue_box() -> Node:
	var root := CanvasLayer.new()
	root.name = "DialogueBox"
	root.layer = 50
	SceneUtil.attach_script(root, SCRIPTS + "dialogue_box.gd")
	var panel := PanelContainer.new()
	panel.name = "Panel"
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_left = 8.0
	panel.offset_right = -8.0
	panel.offset_top = -92.0
	panel.offset_bottom = -8.0
	UiUtil.unique(panel)
	root.add_child(panel)
	var row := HBoxContainer.new()
	row.name = "Row"
	panel.add_child(row)
	var portrait := TextureRect.new()
	portrait.name = "Portrait"
	portrait.custom_minimum_size = Vector2(56, 56)
	portrait.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	portrait.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	portrait.visible = false
	UiUtil.unique(portrait)
	row.add_child(portrait)
	var column := VBoxContainer.new()
	column.name = "Column"
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(column)
	UiUtil.label(column, "Speaker", "", true)
	var body := RichTextLabel.new()
	body.name = "Body"
	body.bbcode_enabled = false
	body.fit_content = false
	body.scroll_active = false
	body.custom_minimum_size = Vector2(0, 40)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	UiUtil.unique(body)
	column.add_child(body)
	var choices := VBoxContainer.new()
	choices.name = "Choices"
	UiUtil.unique(choices)
	column.add_child(choices)
	return root

func _build_notification() -> Node:
	var root := UiUtil.control_root("Notification", SCRIPTS + "notification.gd")
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var stack := VBoxContainer.new()
	stack.name = "Stack"
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	stack.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	stack.offset_left = -200.0
	stack.offset_right = -8.0
	stack.offset_top = 8.0
	UiUtil.unique(stack)
	root.add_child(stack)
	return root

func _build_hud_basic() -> Node:
	var root := CanvasLayer.new()
	root.name = "HudBasic"
	root.layer = 20
	SceneUtil.attach_script(root, SCRIPTS + "hud_basic.gd")
	var gold := Label.new()
	gold.name = "Gold"
	gold.position = Vector2(8, 6)
	gold.text = "UI_GOLD"
	UiUtil.unique(gold)
	root.add_child(gold)
	return root
