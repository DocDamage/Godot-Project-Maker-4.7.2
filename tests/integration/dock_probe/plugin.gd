@tool
extends EditorPlugin
## Test only (T17.27): runs the asset dock's placement in a running editor, which is the one
## place where the editor's undo manager exists. tests/integration/test_m17_isometric.py copies
## this folder into a generated project as addons/zz_dock_probe, enables it, writes what to
## place into res://rpggen/dock_probe_in.json and starts `godot --headless --editor`:
##
##   {"map": "res://game/maps/starter_map.tscn", "snap": 16, "save": true,
##    "places": [{"scene": "res://...tscn", "at": [x, y], "how": "double_click" | "drop"}]}
##
## `at` is where the mouse is, in the world. "double_click" is the dock's own double click
## (`Placement.place_new`); "drop" is what the dock does after the editor dropped a scene: the
## instance is under the scene's root at the mouse, and the dock itself fixes it up
## (`_fix_dropped` of the project's own Assets dock, which plans and applies). Every placement
## is undone and redone through the editor's history, the scene is saved, and
## res://rpggen/results/dock_probe.json says what was seen. After the save the dock's world
## tools add a trigger area, a gate and a floor switch in the middle of the view; they are
## looked at and not saved. Nobody moves a mouse: the 2D view's own drag and drop is not run.
## The report also has `undo_order`: the order in which the scene's history ran the operations of
## an action of its own (Placement.apply relies on it). It runs on a map of squares too.
##
## "mouse" (T18.18, a windowed editor only) is a real drag and drop: the mouse is pressed on the
## dock's item, moved to the 2D view and let go there, as `Input.parse_input_event` events. It
## has no `at` but an `offset` [columns, rows] from the cell in the middle of the view (the view
## cannot be moved from here), and with `raise` (px) a height layer with a tile on that cell is
## added first, which is not saved. The place then also says what was drawn over the view while
## the item was over it (`drawn`: the cell, the cells and the height) and where the mouse let go.

const IN := "res://rpggen/dock_probe_in.json"
const OUT := "res://rpggen/results/dock_probe.json"
const PLACEMENT := "res://addons/rpg_project_tools/dock/placement.gd"
const INDEX := "res://addons/rpg_project_tools/dock/index.gd"
const CATALOG_EDIT := "res://addons/rpg_project_tools/tools/catalog_edit.gd"
const DOCK := "res://addons/rpg_project_tools/dock/asset_dock.gd"

func _enter_tree() -> void:
	if FileAccess.file_exists(IN):
		_run.call_deferred()

func _frames(count: int) -> void:
	for i in count:
		await get_tree().process_frame

## The project's Assets dock, in the editor's own tree.
func _dock() -> Node:
	for node in EditorInterface.get_base_control().find_children("*", "EditorDock", true, false):
		var script: Script = node.get_script()
		if script != null and script.resource_path == DOCK:
			return node
	return null

func _status(dock: Node) -> String:
	var label: Label = dock.get("_status")
	return label.text if label != null else ""

## What a world tool added (it is selected afterwards): where it is and what shape it has.
func _tool(root: Node, dock: Node, kind: String) -> Dictionary:
	if kind == "trigger":
		dock.call("_add_trigger", false)
	else:
		dock.call("_add_lock", kind)
	await _frames(2)
	var nodes := EditorInterface.get_selection().get_selected_nodes()
	if nodes.size() != 1 or not (nodes[0] is Node2D):
		return {"kind": kind, "error": "nothing was added"}
	var node: Node2D = nodes[0]
	var seen := _where(root, node)
	seen["kind"] = kind
	seen["status"] = _status(dock)
	seen["shape"] = ""
	seen["points"] = []
	var holder := node.get_node_or_null("Shape") as CollisionShape2D
	if holder != null and holder.shape != null:
		seen["shape"] = holder.shape.get_class()
		seen["shape_owner"] = holder.owner == root
		if holder.shape is ConvexPolygonShape2D:
			var points: Array = []
			for point in (holder.shape as ConvexPolygonShape2D).points:
				points.append([point.x, point.y])
			seen["points"] = points
	var size: Variant = node.get("size")
	if size is Vector2:
		var extent: Vector2 = size
		seen["size"] = [extent.x, extent.y]
	return seen

func _where(root: Node, node: Node2D) -> Dictionary:
	var cell := RpgIso.cell_at(root, node.global_position)
	var middle := RpgIso.cell_position(root, cell)
	return {
		"parent": String(root.get_path_to(node.get_parent())), "name": String(node.name),
		"x": node.global_position.x, "y": node.global_position.y, "cell": [cell.x, cell.y],
		"middle": [middle.x, middle.y], "entity_id": str(node.get("entity_id")) if node.get("entity_id") != null else "",
		"owner": node.owner == root, "in_tree": node.is_inside_tree(),
	}

func _run() -> void:
	var report := {"ok": false, "error": "", "places": []}
	var wanted: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(IN))
	# the editor is still starting: it scans and imports first, and opens a scene only after
	await _frames(20)
	var waited := 0
	while EditorInterface.get_resource_filesystem().is_scanning() and waited < 3000:
		await _frames(1)
		waited += 1
	var root: Node = null
	for attempt in 20:
		EditorInterface.open_scene_from_path(str(wanted["map"]))
		await _frames(15)
		root = EditorInterface.get_edited_scene_root()
		if root != null and root.scene_file_path == str(wanted["map"]):
			break
	if root == null or root.scene_file_path != str(wanted["map"]):
		report["error"] = "the map did not open"
		_finish(report)
		return
	var footprint := RpgIso.footprint_of(root)
	report["footprint"] = [footprint.x, footprint.y]
	var placement_script: GDScript = load(PLACEMENT)
	var index_script: GDScript = load(INDEX)
	var catalog_script: GDScript = load(CATALOG_EDIT)
	var entries: Array = index_script.call("build", catalog_script.call("load_catalog"))
	report["entries"] = entries.size()
	var dock := _dock()
	report["dock"] = dock != null
	if dock == null:
		report["error"] = "the Assets dock is not in the editor"
		_finish(report)
		return
	var manager := get_undo_redo()
	var history := manager.get_history_undo_redo(manager.get_object_history_id(root))
	var places: Array = wanted["places"]
	for raw: Variant in places:
		var place: Dictionary = raw
		var scene := str(place["scene"])
		var entry := {"name": scene.get_file().get_basename(), "role": "", "tags": [], "scene_path": scene}
		for found: Dictionary in entries:
			if str(found["scene_path"]) == scene:
				entry = found
		var spot: Array = place.get("at", [0, 0])  # a drop of the mouse has none: it says where
		var at := Vector2(float(spot[0]), float(spot[1]))
		var placement: RefCounted = placement_script.new()
		placement.set("snap", int(wanted.get("snap", 16)))
		var seen := {"scene": scene, "how": str(place["how"]), "at": [at.x, at.y], "role": str(entry["role"])}
		var before := history.get_version()
		var node: Node2D = null
		if str(place["how"]) == "mouse":
			node = await _mouse_drop(root, dock, entry, place, seen)
			at = Vector2(float(seen["at"][0]), float(seen["at"][1]))
			seen["status"] = _status(dock)
		elif str(place["how"]) == "drop":
			# what the editor's 2D view leaves behind: the instance under the root, at the mouse
			node = (load(scene) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE) as Node2D
			root.add_child(node, true)
			node.owner = root
			node.global_position = at
			var plan: Dictionary = placement.call("plan", node, root, entry)  # only to say its cells
			var cells: Array = []
			for cell: Vector2i in plan.get("cells", []):
				cells.append([cell.x, cell.y])
			seen["cells"] = cells
			dock.call("_fix_dropped", node, root)
			seen["status"] = _status(dock)
		else:
			node = placement.call("place_new", entry, root, manager, at)
		if node == null:
			seen["error"] = "nothing was placed"
			(report["places"] as Array).append(seen)
			continue
		seen["action"] = history.get_current_action_name()
		seen["one_step"] = history.get_version() == before + 1
		seen["placed"] = _where(root, node)
		seen["stands_on"] = node.get_meta("stands_on") if node.has_meta("stands_on") else [1, 1]
		# Ctrl+Z, then Ctrl+Shift+Z
		seen["undo_ok"] = history.undo()
		seen["undone_in_tree"] = node.is_inside_tree()
		if node.is_inside_tree():
			seen["undone"] = _where(root, node)
		seen["redo_ok"] = history.redo()
		seen["redone"] = _where(root, node)
		(report["places"] as Array).append(seen)
	report["undo_order"] = _undo_order(root, manager, history)
	if bool(wanted.get("save", true)):
		report["saved"] = EditorInterface.save_scene()
		await _frames(5)
	var tools: Array = []
	for kind: String in ["trigger", "gate", "plate"]:
		var before := history.get_version()
		var seen: Dictionary = await _tool(root, dock, kind)
		seen["one_step"] = history.get_version() == before + 1
		seen["undo_ok"] = history.undo()
		seen["redo_ok"] = history.redo()
		tools.append(seen)
	report["tools"] = tools
	report["unit"] = RpgIso.map_unit(root)
	report["ok"] = true
	_finish(report)

var _order: Array[String] = []
## Where the last mouse event of the probe was (window coordinates).
var _mouse_at := Vector2.ZERO

const HEIGHT_LAYERS := "res://addons/rpg_project_tools/tools/height_layers.gd"

## A mouse event at `where` (the editor window's px), sent as the window would.
func _send(event: InputEventMouse, where: Vector2) -> void:
	event.position = where
	event.global_position = where
	Input.warp_mouse(where)  # the editor finds what is under a drag by the real mouse
	Input.parse_input_event(event)
	await _frames(2)

func _motion(where: Vector2, held: bool) -> void:
	var event := InputEventMouseMotion.new()
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if held else 0
	event.relative = where - _mouse_at  # a drag starts once these add up past the threshold
	_mouse_at = where
	await _send(event, where)

func _button(where: Vector2, down: bool) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = down
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if down else 0
	await _send(event, where)

## Drags the dock's item of `entry` to a cell of the 2D view and lets go there. Returns what the
## dock placed (selected after the drop), or null.
func _mouse_drop(root: Node, dock: Node, entry: Dictionary, place: Dictionary, seen: Dictionary) -> Node2D:
	var list := dock.get("_list") as ItemList
	var search := dock.get("_search") as LineEdit
	if search != null and search.text != "":
		search.text = ""
		dock.call("_refresh_list")
	var item := -1
	for i in list.item_count:
		if str(list.get_item_metadata(i)) == str(entry["scene_path"]):
			item = i
	if item < 0:
		seen["error"] = "the dock does not list the scene"
		return null
	# the library tab in front, the item in sight
	var tabs := list.get_parent()
	while tabs != null and not (tabs is TabContainer):
		tabs = tabs.get_parent()
	if tabs != null:
		(tabs as TabContainer).current_tab = 0
	dock.call("make_visible") if dock.has_method("make_visible") else null
	list.select(item)
	list.ensure_current_is_visible()
	EditorInterface.set_main_screen_editor("2D")  # the 2D view is what is dropped on
	await _frames(10)
	var from := list.get_global_transform_with_canvas() * list.get_item_rect(item).get_center()
	# the cell in the middle of the view, and the one `offset` from it
	var view := EditorInterface.get_editor_viewport_2d()
	var container := view.get_parent() as Control
	var shown := view.global_canvas_transform * view.canvas_transform
	var middle := shown.affine_inverse() * (Vector2(view.size) * 0.5)
	var off := Vector2i(int(place.get("offset", [0, 0])[0]), int(place.get("offset", [0, 0])[1]))
	var cell := RpgIso.cell_at(root, middle) + off
	var world := RpgIso.cell_position(root, cell) + Vector2(3, 1)  # a little off its middle
	var raise := int(place.get("raise", 0))
	if raise > 0:
		var ground := RpgIso.ground_layer(root)
		var heights: GDScript = load(HEIGHT_LAYERS)
		var layer: TileMapLayer = heights.call("make_layer", root, raise)
		ground.get_parent().add_child(layer)
		var used := ground.get_used_cells()
		var like := cell if ground.get_cell_source_id(cell) != -1 else used[0]
		layer.set_cell(cell, ground.get_cell_source_id(like), ground.get_cell_atlas_coords(like), ground.get_cell_alternative_tile(like))
	var to := container.get_global_transform_with_canvas() * (shown * world)
	seen["target"] = [cell.x, cell.y]
	seen["at"] = [world.x, world.y]
	seen["mouse"] = [to.x, to.y]
	seen["view"] = [view.size.x, view.size.y, container.is_visible_in_tree()]
	seen["from"] = [from.x, from.y]
	# press on the item, pull it out of the list, over the view, and let go
	await _motion(from, false)
	await _button(from, true)
	for step in 12:
		await _motion(from.lerp(to, float(step + 1) / 12.0), true)
	for wiggle in 6:
		await _motion(to + Vector2(0.0 if wiggle % 2 == 0 else 1.0, 0.0), true)
	seen["dragging"] = get_viewport().gui_is_dragging()
	var drawn: Dictionary = dock.get("drag_shown")
	if not drawn.is_empty():
		var cells: Rect2i = drawn["cells"]
		var drawn_cell: Vector2i = drawn["cell"]
		seen["drawn"] = {"cell": [drawn_cell.x, drawn_cell.y], "cells": [cells.position.x, cells.position.y, cells.size.x, cells.size.y], "raise": int(drawn["raise"])}
	var manager := get_undo_redo()
	var history := manager.get_history_undo_redo(manager.get_object_history_id(root))
	var version := history.get_version()
	var count := root.get_child_count()
	await _motion(to, true)
	await _button(to, false)
	await _frames(20)
	var nodes := EditorInterface.get_selection().get_selected_nodes()
	var names: Array[String] = []
	for picked in nodes:
		names.append(str(picked.name))
	seen["after"] = {"history": history.get_version() - version, "children": root.get_child_count() - count, "selected": names, "dragging": get_viewport().gui_is_dragging(), "armed": dock.get("_armed_scene")}
	if nodes.is_empty() or not (nodes[0] is Node2D) or nodes[0] == root:
		seen["error"] = "nothing was dropped"
		return null
	var node := nodes[0] as Node2D
	seen["raised"] = String(node.get_parent().name).begins_with("Raised")
	var cells_under: Array = []
	var placement_script: GDScript = load(PLACEMENT)
	var stands: Vector2i = placement_script.call("stands_on", node)
	for under: Vector2i in placement_script.call("cells_under", cell, stands):
		cells_under.append([under.x, under.y])
	seen["cells"] = cells_under
	return node

func _note(what: String) -> void:
	_order.append(what)

## The order in which the scene's history runs an action's operations: two of each, noted as
## they run; then the action is undone and redone. Placement.apply relies on it.
func _undo_order(root: Node, manager: EditorUndoRedoManager, history: UndoRedo) -> Array[String]:
	_order.clear()
	manager.create_action("Probe the order", UndoRedo.MERGE_DISABLE, root)
	manager.add_do_method(self, "_note", "do 1")
	manager.add_do_method(self, "_note", "do 2")
	manager.add_undo_method(self, "_note", "undo 1")
	manager.add_undo_method(self, "_note", "undo 2")
	manager.commit_action()
	history.undo()
	history.redo()
	history.undo()  # the probe's action is not left in the scene's history
	return _order.duplicate()

func _finish(report: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(OUT.get_base_dir())
	var file := FileAccess.open(OUT, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  ", true) + "\n")
	file.close()
	get_tree().quit(0)
