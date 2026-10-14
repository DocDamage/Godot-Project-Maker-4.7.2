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
		var at := Vector2(float(place["at"][0]), float(place["at"][1]))
		var placement: RefCounted = placement_script.new()
		placement.set("snap", int(wanted.get("snap", 16)))
		var seen := {"scene": scene, "how": str(place["how"]), "at": [at.x, at.y], "role": str(entry["role"])}
		var before := history.get_version()
		var node: Node2D = null
		if str(place["how"]) == "drop":
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

func _finish(report: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(OUT.get_base_dir())
	var file := FileAccess.open(OUT, FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  ", true) + "\n")
	file.close()
	get_tree().quit(0)
