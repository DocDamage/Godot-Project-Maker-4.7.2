@tool
extends EditorDock
## The Asset Library dock (T8.02, T8.03, T8.05): browse, search, drag or double-click assets into
## the map being edited, edit their catalog entry, rebuild what changed, validate the content.

const Index := preload("index.gd")
const AssetItem := preload("asset_item.gd")
const Placement := preload("placement.gd")
const AssetInspector := preload("asset_inspector.gd")
const ValidatorPanel := preload("validator_panel.gd")
const DemoTools := preload("demo_tools.gd")
const DialogueTab := preload("dialogue_tab.gd")
const QuestTab := preload("quest_tab.gd")
const SequenceTab := preload("sequence_tab.gd")
const SkillTreeTab := preload("skill_tree_tab.gd")
const AchievementTab := preload("achievement_tab.gd")
const ItemSetTab := preload("item_set_tab.gd")
const Rebuild := preload("../tools/rebuild.gd")
const CatalogEdit := preload("../tools/catalog_edit.gd")
const JsonIo := preload("../tools/json_io.gd")
const HeightLayers := preload("../tools/height_layers.gd")

const ICON_SIZE := 48
## Seconds a drag stays armed after it ended: the editor adds the dropped scene a moment later.
const DROP_WINDOW := 1.5
const SNAP_CHOICES: Array[String] = ["Off", "8", "Tile", "32", "Custom"]

var plugin: EditorPlugin = null
var placement := Placement.new()

var _built := false
var _entries: Array[Dictionary] = []
var _shown: Array[Dictionary] = []
var _icons: Dictionary = {}  # scene path -> Texture2D
var _fingerprint := ""
var _catalog: Dictionary = {}

var _search: LineEdit
var _category: OptionButton
var _list: AssetItem
var _snap: OptionButton
var _snap_custom: SpinBox
var _ysort: OptionButton
var _flip: CheckBox
var _auto_id: CheckBox
var _status: Label
var _inspector: AssetInspector
var _validator: ValidatorPanel
var _demo_dialog: ConfirmationDialog
var _height: SpinBox

# Drag-and-drop bookkeeping: the scene a drag started with, and the nodes already fixed up.
var _armed_scene := ""
var _armed_until := 0.0
var _handled: Dictionary = {}  # instance id -> true
var _previous_selection: Node = null

func _init() -> void:
	title = "Assets"
	layout_key = "rpg_asset_library"
	default_slot = DOCK_SLOT_RIGHT_UL

func _enter_tree() -> void:
	if not _built:
		_build_ui()
		_built = true
	var fs := EditorInterface.get_resource_filesystem()
	if not fs.filesystem_changed.is_connected(_on_filesystem_changed):
		fs.filesystem_changed.connect(_on_filesystem_changed)
	var selection := EditorInterface.get_selection()
	if not selection.selection_changed.is_connected(_on_selection_changed):
		selection.selection_changed.connect(_on_selection_changed)
	rescan()

func _exit_tree() -> void:
	var fs := EditorInterface.get_resource_filesystem()
	if fs != null and fs.filesystem_changed.is_connected(_on_filesystem_changed):
		fs.filesystem_changed.disconnect(_on_filesystem_changed)
	var selection := EditorInterface.get_selection()
	if selection != null and selection.selection_changed.is_connected(_on_selection_changed):
		selection.selection_changed.disconnect(_on_selection_changed)

# ---------------------------------------------------------------- UI

func _build_ui() -> void:
	var box := VBoxContainer.new()
	box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(box)
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(tabs)
	tabs.add_child(_build_library_tab())
	_validator = ValidatorPanel.new()
	_validator.plugin = plugin
	_validator.name = "Validate"
	tabs.add_child(_validator)
	var dialogue := DialogueTab.new()
	dialogue.plugin = plugin
	tabs.add_child(dialogue)
	var quests := QuestTab.new()  # T13.19
	quests.plugin = plugin
	tabs.add_child(quests)
	for made: VBoxContainer in [SkillTreeTab.new(), AchievementTab.new(), ItemSetTab.new()]:  # 1.5.0
		made.set("plugin", plugin)
		tabs.add_child(made)
	var cutscenes := SequenceTab.new()
	cutscenes.plugin = plugin
	cutscenes.debug_link = plugin.get("debug_link") if plugin != null else null
	tabs.add_child(cutscenes)
	tabs.add_child(_build_project_tab())
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_status)

func _build_library_tab() -> Control:
	var page := VBoxContainer.new()
	page.name = "Library"
	var top := HBoxContainer.new()
	_search = LineEdit.new()
	_search.placeholder_text = "Search name, id or tag"
	_search.clear_button_enabled = true
	_search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_search.text_changed.connect(func(_t: String) -> void: _refresh_list())
	top.add_child(_search)
	var rescan_button := Button.new()
	rescan_button.text = "Rescan"
	rescan_button.pressed.connect(rescan)
	top.add_child(rescan_button)
	page.add_child(top)
	_category = OptionButton.new()
	for c in Index.CATEGORIES:
		_category.add_item(c)
	_category.item_selected.connect(func(_i: int) -> void: _refresh_list())
	page.add_child(_category)

	_list = AssetItem.new()
	_list.icon_mode = ItemList.ICON_MODE_TOP
	_list.max_columns = 0
	_list.same_column_width = true
	_list.fixed_icon_size = Vector2i(ICON_SIZE, ICON_SIZE)
	_list.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.custom_minimum_size = Vector2(0, 180)
	_list.item_selected.connect(_on_item_selected)
	_list.item_activated.connect(_on_item_activated)
	_list.drag_started.connect(_on_drag_started)
	page.add_child(_list)

	page.add_child(_build_settings())
	_inspector = AssetInspector.new()
	_inspector.saved.connect(func(_id: String) -> void: _set_status("Catalog saved. Use Regenerate to rebuild."))
	page.add_child(_inspector)
	return page

func _build_settings() -> Control:
	var box := VBoxContainer.new()
	var snap_row := HBoxContainer.new()
	var snap_label := Label.new()
	snap_label.text = "Snap"
	snap_row.add_child(snap_label)
	_snap = OptionButton.new()
	for s in SNAP_CHOICES:
		_snap.add_item(s)
	_snap.select(2)
	_snap.tooltip_text = "On an isometric map every choice but Off puts what is placed on the middle of the diamond under it."
	_snap.item_selected.connect(func(_i: int) -> void: _apply_settings())
	snap_row.add_child(_snap)
	_snap_custom = SpinBox.new()
	_snap_custom.min_value = 1
	_snap_custom.max_value = 256
	_snap_custom.value = 16
	_snap_custom.value_changed.connect(func(_v: float) -> void: _apply_settings())
	snap_row.add_child(_snap_custom)
	box.add_child(snap_row)
	var ysort_row := HBoxContainer.new()
	var ysort_label := Label.new()
	ysort_label.text = "Y-sort parent"
	ysort_row.add_child(ysort_label)
	_ysort = OptionButton.new()
	_ysort.add_item("Auto")
	_ysort.add_item("Selected")
	_ysort.item_selected.connect(func(_i: int) -> void: _apply_settings())
	ysort_row.add_child(_ysort)
	box.add_child(ysort_row)
	_flip = CheckBox.new()
	_flip.text = "Flip horizontally"
	_flip.toggled.connect(func(_on: bool) -> void: _apply_settings())
	box.add_child(_flip)
	_auto_id = CheckBox.new()
	_auto_id.text = "Assign entity id"
	_auto_id.button_pressed = true
	_auto_id.toggled.connect(func(_on: bool) -> void: _apply_settings())
	box.add_child(_auto_id)
	return box

func _build_project_tab() -> Control:
	var page := VBoxContainer.new()
	page.name = "Project"
	var regenerate := Button.new()
	regenerate.text = "Regenerate affected resources"
	regenerate.tooltip_text = "Saves the open scenes, runs the builder and rescans the project."
	regenerate.pressed.connect(regenerate_now)
	page.add_child(regenerate)
	var generator := Button.new()
	generator.text = "Open generator"
	generator.pressed.connect(_open_generator)
	page.add_child(generator)
	var demo := Button.new()
	demo.text = "Remove demo content"
	demo.pressed.connect(func() -> void: _demo_dialog.popup_centered())
	page.add_child(demo)
	_demo_dialog = ConfirmationDialog.new()
	_demo_dialog.title = "Remove demo content"
	_demo_dialog.dialog_text = "This deletes game/demo/ (if present), removes the demo NPC, chest and enemy from the starter map (and saves it), removes the demo house interior if you did not change it and starts new games without items. Regeneration will not bring them back."
	_demo_dialog.confirmed.connect(_remove_demo)
	page.add_child(_demo_dialog)
	var world := Label.new()
	world.text = "World tools (in the open map, at the centre of the view)"
	world.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	page.add_child(world)
	var walk_in := Button.new()
	walk_in.text = "Add trigger area (walk in)"
	walk_in.tooltip_text = "Adds an area that runs a sequence when the player walks in, and an empty sequence file under game/data/sequences/ to write it in."
	walk_in.pressed.connect(_add_trigger.bind(false))
	page.add_child(walk_in)
	var on_interact := Button.new()
	on_interact.text = "Add trigger area (interact)"
	on_interact.tooltip_text = "Adds an area that runs a sequence when the player presses interact in front of it."
	on_interact.pressed.connect(_add_trigger.bind(true))
	page.add_child(on_interact)
	var zone := Button.new()
	zone.text = "Add encounter zone (over the selection)"
	zone.tooltip_text = "Turn-based games: random battles while the player walks inside it. Select a TileMapLayer to use its painted cells, or some nodes to cover them; with nothing selected it is 6x6 tiles in the middle of the view. Its encounter table under game/data/encounters/ lists every enemy."
	zone.pressed.connect(_add_zone)
	page.add_child(zone)
	for spec: Array in [["gate", "Add gate", "A barrier that a key or a switch opens. Set its Key Item, or select it and add a switch."], ["plate", "Add floor switch", "A plate the player steps on. With a gate selected, the plate opens that gate."], ["lever", "Add lever", "A lever the player pulls. With a gate selected, the lever opens that gate."]]:
		var button := Button.new()
		button.text = spec[1]
		button.tooltip_text = spec[2]
		button.pressed.connect(_add_lock.bind(spec[0]))
		page.add_child(button)
	# what a pack stacks (2026-10-26): blocks, storeys, roofs on layers drawn higher
	var heights := HBoxContainer.new()
	var height_label := Label.new()
	height_label.text = "Height layer at"
	heights.add_child(height_label)
	_height = SpinBox.new()
	_height.min_value = 0
	_height.max_value = 4096
	_height.suffix = "px"
	_height.tooltip_text = "How high the layer is drawn. Suggest gives the top of the highest height layer: its height and as high as its tiles lift (a block 16 px, a storey 20)."
	heights.add_child(_height)
	var suggest := Button.new()
	suggest.text = "Suggest"
	suggest.pressed.connect(_suggest_height)
	heights.add_child(suggest)
	page.add_child(heights)
	var add_height := Button.new()
	add_height.text = "Add height layer"
	add_height.tooltip_text = "Isometric levels: a tile layer drawn higher, for what stands on a block or a storey (the next storey, a roof, a sign on a front). Paint it with the Terrain or the tile tools as any layer; it sorts with the people as its cells' ground does. What you place from the library on a cell with a stack stands on its top."
	add_height.pressed.connect(_add_height_layer)
	page.add_child(add_height)
	return page

func _suggest_height() -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null:
		_set_status("Open a level to suggest the height of its next layer.")
		return
	_height.value = HeightLayers.suggested(root)

func _add_height_layer() -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null or plugin == null or RpgIso.footprint_of(root) == Vector2i.ZERO:
		_set_status("Open an isometric level (a scene with a tile layer of diamonds) to add a height layer.")
		return
	var like: TileMapLayer = null
	for node in EditorInterface.get_selection().get_selected_nodes():
		if node is TileMapLayer:
			like = node as TileMapLayer
	var height := int(_height.value)
	var layer := HeightLayers.add_layer(root, height, plugin.get_undo_redo(), like)
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(layer)
	_height.value = HeightLayers.suggested(root)
	_set_status("Added %s, drawn %d px higher. Paint it; the next layer is suggested at %d px." % [layer.name, height, int(_height.value)])

func _add_lock(kind: String) -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null or plugin == null:
		_set_status("Open a map scene to add a %s." % kind)
		return
	var selected_nodes := EditorInterface.get_selection().get_selected_nodes()
	var selected: Node = selected_nodes[0] if selected_nodes.size() == 1 else null
	var plan := Placement.plan_lock(root, _view_centre(), _map_tile(root), kind, selected)
	var node := Placement.add_lock(plan, root, plugin.get_undo_redo())
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(node)
	var gate: Node = plan["gate"]
	if gate != null:
		_set_status("Added %s; it opens %s." % [plan["entity_id"], gate.name])
	else:
		_set_status("Added %s." % plan["entity_id"])

func _add_zone() -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null or plugin == null:
		_set_status("Open a map scene to add an encounter zone.")
		return
	if not DirAccess.dir_exists_absolute("res://addons/rpg_runtime/archetypes/turn_based"):
		_set_status("Random encounters are for turn-based games; in an action RPG, enemies are placed on the map.")
		return
	var selected: Array = EditorInterface.get_selection().get_selected_nodes()
	var plan := Placement.plan_zone(root, selected, _view_centre(), _map_tile(root))
	var area := Placement.add_zone(plan, root, plugin.get_undo_redo())
	EditorInterface.get_resource_filesystem().scan()
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(area)
	var enemies: Array = plan["enemies"]
	_set_status("Added %s with %d enemy group(s) in %s." % [plan["name"], enemies.size(), plan["table_path"]])

func _view_centre() -> Vector2:
	var viewport := EditorInterface.get_editor_viewport_2d()
	return viewport.get_canvas_transform().affine_inverse() * (Vector2(viewport.size) / 2.0)

func _add_trigger(on_interact: bool) -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null or plugin == null:
		_set_status("Open a map scene to add a trigger area.")
		return
	var tile := _map_tile(root)
	var plan := Placement.plan_trigger(root, _view_centre(), tile, tile, on_interact)
	var area := Placement.add_trigger(plan, root, plugin.get_undo_redo())
	EditorInterface.get_resource_filesystem().scan()
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(area)
	_set_status("Added %s; write its commands in %s." % [plan["entity_id"], plan["sequence_path"]])

func _set_status(text: String) -> void:
	if _status != null:
		_status.text = text

# ---------------------------------------------------------------- library

func rescan() -> void:
	_catalog = CatalogEdit.load_catalog()
	_entries = Index.build(_catalog)
	_fingerprint = Index.fingerprint()
	_refresh_list()
	if _entries.is_empty():
		_set_status("No library scenes yet: generate the project first (rpggen/object_index.json is missing).")

func _refresh_list() -> void:
	if _list == null:
		return
	_list.clear()
	_shown = Index.filter(_entries, _search.text, _category.get_item_text(_category.selected))
	for e in _shown:
		var scene_path := JsonIo.to_str(e["scene_path"])
		if not _icons.has(scene_path):
			_icons[scene_path] = Index.icon_of(scene_path)
		var icon: Texture2D = _icons[scene_path]
		var i := _list.add_item(JsonIo.to_str(e["name"]), icon)
		_list.set_item_metadata(i, scene_path)
		_list.set_item_tooltip(i, "%s\n%s" % [e["id"], scene_path])
	_set_status("%d of %d assets." % [_shown.size(), _entries.size()])

func _on_filesystem_changed() -> void:
	if Index.fingerprint() != _fingerprint:
		_icons.clear()
		rescan()

func _selected_entry() -> Dictionary:
	var picked := _list.get_selected_items()
	return _shown[picked[0]] if not picked.is_empty() else {}

func _on_item_selected(index: int) -> void:
	_inspector.show_entry(_shown[index], _catalog)

func _apply_settings() -> void:
	var choice: String = _snap.get_item_text(_snap.selected)
	match choice:
		"Off":
			placement.snap = 0
		"Tile":
			placement.snap = _tile_size()
		"Custom":
			placement.snap = int(_snap_custom.value)
		_:
			placement.snap = int(choice)
	placement.ysort_mode = "selected" if _ysort.selected == 1 else "auto"
	placement.flip_h = _flip.button_pressed
	placement.auto_id = _auto_id.button_pressed

## The map tile size (the overworld tile set's), 16 when unknown.
func _tile_size() -> int:
	var tilesets: Array = _catalog.get("tilesets", [])
	for def: Dictionary in tilesets:
		if def.get("name", "") == "overworld":
			return JsonIo.to_int(def["tile_size"][0])
	return 16

## What the world tools mean by a tile in the map being edited: the tile size above, and on an
## isometric map (T17.27) one step from a diamond to the next, as the builder counts it.
func _map_tile(root: Node) -> int:
	var diamond := Placement.diamond_of(root)
	return RpgIso.unit(diamond) if diamond != Vector2i.ZERO else _tile_size()

## " on the diamond (x, y)" for what was placed in an isometric map, "" in any other.
static func _cell_text(root: Node, placed: Node) -> String:
	if not (placed is Node2D) or Placement.diamond_of(root) == Vector2i.ZERO:
		return ""
	var cell := RpgIso.cell_at(root, (placed as Node2D).global_position)
	return " on the diamond (%d, %d)" % [cell.x, cell.y]

# ---------------------------------------------------------------- placement

func _on_drag_started(scene_path: String) -> void:
	_apply_settings()
	_armed_scene = scene_path
	_armed_until = Time.get_ticks_msec() / 1000.0 + 60.0  # until the drop; shortened when it ends

func _notification(what: int) -> void:
	if what == NOTIFICATION_DRAG_END and _armed_scene != "":
		_armed_until = Time.get_ticks_msec() / 1000.0 + DROP_WINDOW
		# The editor adds the scene when the drag ends; look at the selection right after.
		_process_selection.call_deferred()

func _on_selection_changed() -> void:
	_process_selection()

func _process_selection() -> void:
	var nodes := EditorInterface.get_selection().get_selected_nodes()
	var root := EditorInterface.get_edited_scene_root()
	var now := Time.get_ticks_msec() / 1000.0
	if _armed_scene != "" and now > _armed_until:
		_armed_scene = ""
	if root != null and _armed_scene != "" and plugin != null:
		for node in nodes:
			var dropped := node as Node2D
			if dropped != null and node != root and node.scene_file_path == _armed_scene and not _handled.has(node.get_instance_id()) and root.is_ancestor_of(node):
				_handled[node.get_instance_id()] = true
				_fix_dropped(dropped, root)
	if not nodes.is_empty() and nodes[0].scene_file_path != _armed_scene:
		_previous_selection = nodes[0]

func _entry_for_scene(scene_path: String) -> Dictionary:
	for e in _entries:
		if e["scene_path"] == scene_path:
			return e
	return {"name": scene_path.get_file().get_basename(), "role": "", "tags": []}

func _fix_dropped(node: Node2D, root: Node) -> void:
	_apply_settings()
	var entry := _entry_for_scene(node.scene_file_path)
	var selected: Node = _previous_selection if is_instance_valid(_previous_selection) else null
	var p := placement.plan(node, root, entry, selected)
	placement.apply(p, node, root, plugin.get_undo_redo(), JsonIo.to_str(entry["name"]))
	_set_status("Placed %s%s%s." % [entry["name"], " as " + JsonIo.to_str(p["entity_id"]) if JsonIo.to_str(p["entity_id"]) != "" else "", _cell_text(root, node)])

func _on_item_activated(index: int) -> void:
	var root := EditorInterface.get_edited_scene_root()
	if root == null or plugin == null:
		_set_status("Open a map scene to place assets.")
		return
	_apply_settings()
	var viewport := EditorInterface.get_editor_viewport_2d()
	var center := viewport.get_canvas_transform().affine_inverse() * (Vector2(viewport.size) / 2.0)
	var entry: Dictionary = _shown[index]
	var selected: Node = _previous_selection if is_instance_valid(_previous_selection) else null
	var node := placement.place_new(entry, root, plugin.get_undo_redo(), center, selected)
	if node == null:
		_set_status("Could not place %s." % entry["name"])
		return
	_handled[node.get_instance_id()] = true
	_set_status("Placed %s%s." % [entry["name"], _cell_text(root, node)])

# ---------------------------------------------------------------- project tab

func regenerate_now() -> void:
	_set_status("Regenerating: running the builder…")
	var result := Rebuild.regenerate()
	var issue_list: Array = result["issues"]
	var errors := 0
	var warnings := 0
	for issue: Dictionary in issue_list:
		match JsonIo.to_str(issue.get("severity", "")):
			"error":
				errors += 1
			"warning":
				warnings += 1
	if result["ok"]:
		_set_status("Regenerated. %d warning(s)." % warnings)
	else:
		var first := ""
		for issue: Dictionary in issue_list:
			if issue.get("severity", "") == "error":
				first = JsonIo.to_str(issue.get("message", ""))
				break
		_set_status("The build failed (%d error(s)): %s" % [errors, first if first != "" else "exit code %d, see rpggen/results/build_results.json" % JsonIo.to_int(result["exit_code"])])
	rescan()

func _open_generator() -> void:
	if Rebuild.open_generator() < 0:
		_set_status("Set the editor setting rpg_tools/rpggen_executable to the rpggen program (Editor Settings), or run: rpggen gui --target <this project folder>.")
	else:
		_set_status("The generator wizard was started.")

func _remove_demo() -> void:
	if plugin == null:
		return
	var result := DemoTools.new().remove(plugin)
	var messages: Array = result["messages"]
	if messages.is_empty():
		_set_status("There was no demo content to remove.")
	else:
		_set_status(" ".join(PackedStringArray(messages)))
	rescan()
