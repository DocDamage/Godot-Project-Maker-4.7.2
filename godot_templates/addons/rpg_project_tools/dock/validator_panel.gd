@tool
extends VBoxContainer
## "Validate content" (T8.04): runs the content checks of tools/content_checks.gd, lists the
## findings in a tree and opens the scene of a finding on double-click. "Fix entity IDs" assigns
## ids to the edited scene's persistent entities that have none and renames later duplicates.
## "Fix" and "Fix all" (T13.24) mend the doors that lead nowhere and the maps that cannot be
## reached (tools/world_repair.gd): each in the scene it belongs to, through the editor's undo
## history, so Ctrl+Z takes it back; the scene is left modified, not saved. Nothing is fixed
## unless you press the button.

const ContentChecks := preload("../tools/content_checks.gd")
const EntityIds := preload("../tools/entity_ids.gd")
const Placement := preload("placement.gd")
const JsonIo := preload("../tools/json_io.gd")
const Repair := preload("../tools/world_repair.gd")

const ERROR_CODES_PATHS: Array[String] = ["res://generated/builder/lib/error_codes.gd", "res://builder/lib/error_codes.gd"]

var plugin: EditorPlugin = null
var _tree: Tree
var _summary: Label
var _findings: Array = []

func _init() -> void:
	name = "ValidatorPanel"
	var buttons := HBoxContainer.new()
	var validate := Button.new()
	validate.text = "Validate content"
	validate.pressed.connect(validate_now)
	buttons.add_child(validate)
	var fix := Button.new()
	fix.text = "Fix entity IDs"
	fix.tooltip_text = "Assigns ids to entities without one and renames duplicates in the scene being edited (undoable)."
	fix.pressed.connect(fix_entity_ids)
	buttons.add_child(fix)
	var fix_row := Button.new()
	fix_row.text = "Fix"
	fix_row.tooltip_text = "Mends the selected door or unreachable map: adds the missing spawn point or door (undoable; the scene is left modified, not saved)."
	fix_row.pressed.connect(fix_selected)
	buttons.add_child(fix_row)
	var fix_everything := Button.new()
	fix_everything.text = "Fix all"
	fix_everything.tooltip_text = "Mends every door that leads nowhere and every map that cannot be reached (undoable, scene by scene)."
	fix_everything.pressed.connect(fix_all)
	buttons.add_child(fix_everything)
	add_child(buttons)
	_summary = Label.new()
	_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_summary)
	_tree = Tree.new()
	_tree.columns = 2
	_tree.set_column_expand(0, true)
	_tree.set_column_expand(1, false)
	_tree.set_column_custom_minimum_width(1, 140)
	_tree.hide_root = true
	_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tree.custom_minimum_size = Vector2(0, 160)
	_tree.item_activated.connect(_on_item_activated)
	add_child(_tree)

static func _error_codes() -> Dictionary:
	for path in ERROR_CODES_PATHS:
		if ResourceLoader.exists(path):
			var script := load(path) as GDScript
			if script != null:
				return script.get("CODES")
	return {}

## The message of a finding (its code's template filled with its detail), and the severity.
static func describe(finding: Dictionary, codes: Dictionary) -> Dictionary:
	var info: Dictionary = codes.get(finding["code"], {})
	var text := JsonIo.to_str(info.get("message", finding["code"]))
	var detail: Dictionary = finding["detail"]
	for key: Variant in detail.keys():
		text = text.replace("{%s}" % str(key), str(detail[key]))
	return {"severity": JsonIo.to_str(info.get("severity", "warning")), "message": "%s: %s" % [finding["code"], text]}

func validate_now() -> void:
	_findings = ContentChecks.run()
	_tree.clear()
	var codes := _error_codes()
	var root := _tree.create_item()
	var errors := 0
	var warnings := 0
	for f: Dictionary in _findings:
		var d := describe(f, codes)
		var item := _tree.create_item(root)
		var message: String = d["message"]
		item.set_text(0, message)
		item.set_text(1, JsonIo.to_str(f["file"]).trim_prefix("res://"))
		item.set_metadata(0, f)
		match d["severity"]:
			"error":
				errors += 1
				item.set_custom_color(0, Color(1.0, 0.45, 0.45))
				item.set_icon(0, _icon("StatusError"))
			"warning":
				warnings += 1
				item.set_custom_color(0, Color(1.0, 0.85, 0.4))
				item.set_icon(0, _icon("StatusWarning"))
			_:
				item.set_icon(0, _icon("NodeInfo"))
	_summary.text = "No problems found." if _findings.is_empty() else "%d error(s), %d warning(s)." % [errors, warnings]

static func _icon(icon_name: String) -> Texture2D:
	var base := EditorInterface.get_base_control()
	return base.get_theme_icon(icon_name, "EditorIcons") if base != null else null

func _on_item_activated() -> void:
	var item := _tree.get_selected()
	if item == null:
		return
	var f: Dictionary = item.get_metadata(0)
	open_finding(f)

## Opens the scene of a finding (a scene file) and selects the node it is about.
static func open_finding(f: Dictionary) -> void:
	var path := JsonIo.to_str(f["file"])
	if path.get_extension() != "tscn":
		return
	var edited := EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != path:
		EditorInterface.open_scene_from_path(path)
		edited = EditorInterface.get_edited_scene_root()
	var node_path := JsonIo.to_str(f["node"])
	if edited != null and node_path != "":
		var node := edited.get_node_or_null(node_path)
		if node != null:
			var selection := EditorInterface.get_selection()
			selection.clear()
			selection.add_node(node)

# ---------------------------------------------------------------- world repair (T13.24)

## The codes Fix can do something about.
static func fixable_codes() -> Array[String]:
	return ["VAL-016", "VAL-017", "VAL-027", "VAL-028"]

## What a repair would do to the project's maps now (nothing is changed).
static func plan_world_fixes() -> Array[Dictionary]:
	var roots := {}
	var instance_of := func(path: String) -> Node:
		if not roots.has(path):
			var packed := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
			roots[path] = packed.instantiate() if packed != null else null
		return roots[path]
	var actions := Repair.plan_repairs(ContentChecks.list_files(ContentChecks.MAPS_DIR, ["tscn"]), Repair.read_plan(), instance_of)
	for path: String in roots.keys():
		var root: Node = roots[path]
		if root != null:
			root.free()
	return actions

## One action in `root` (the scene of action.map) as one undo step: through `undo_redo` (the
## editor's history, or a plain UndoRedo in tests), or directly without one.
static func do_fix(action: Dictionary, root: Node, undo_redo: Object) -> void:
	var kind := str(action["kind"])
	var title := "Repair: %s" % str(action["what"])
	if kind == "retarget":
		var door := root.get_node_or_null(str(action["node"]))
		if door == null:
			return
		var old_map: Variant = door.get("target_map")
		var old_spawn: Variant = door.get("target_spawn")
		var new_spawn := StringName(str(action["target_spawn"]))
		if undo_redo is UndoRedo:
			var plain := undo_redo as UndoRedo
			plain.create_action(title)
			plain.add_do_property(door, "target_map", str(action["target_map"]))
			plain.add_do_property(door, "target_spawn", new_spawn)
			plain.add_undo_property(door, "target_map", old_map)
			plain.add_undo_property(door, "target_spawn", old_spawn)
			plain.commit_action()
		elif undo_redo != null:
			undo_redo.call("create_action", title, UndoRedo.MERGE_DISABLE, root)
			undo_redo.call("add_do_property", door, "target_map", str(action["target_map"]))
			undo_redo.call("add_do_property", door, "target_spawn", new_spawn)
			undo_redo.call("add_undo_property", door, "target_map", old_map)
			undo_redo.call("add_undo_property", door, "target_spawn", old_spawn)
			undo_redo.call("commit_action")
		else:
			Repair.apply(action, root)
		return
	if kind != "spawn" and kind != "door":
		return  # an unfixable finding: nothing safe to do
	if undo_redo == null:
		Repair.apply(action, root)
		return
	var holder := Repair._holder(root, "SpawnPoints" if kind == "spawn" else "Triggers")
	var node := Repair.build(action)
	var owned: Array[Node] = [node]
	owned.append_array(node.get_children())
	if undo_redo is UndoRedo:
		var plain := undo_redo as UndoRedo
		plain.create_action(title)
		plain.add_do_method(holder.add_child.bind(node))
		for part in owned:
			plain.add_do_method(part.set_owner.bind(root))
		plain.add_undo_method(holder.remove_child.bind(node))
		plain.add_do_reference(node)
		plain.commit_action()
	else:
		undo_redo.call("create_action", title, UndoRedo.MERGE_DISABLE, root)
		undo_redo.call("add_do_method", holder, "add_child", node)
		for part in owned:
			undo_redo.call("add_do_method", part, "set_owner", root)
		undo_redo.call("add_undo_method", holder, "remove_child", node)
		undo_redo.call("add_do_reference", node)
		undo_redo.call("commit_action")

## Applies `actions` in the editor: each map is opened, changed through the undo history and left
## modified. Returns how many were applied.
func apply_fixes(actions: Array[Dictionary]) -> int:
	if plugin == null:
		return 0
	var done := 0
	for action in actions:
		if str(action["kind"]) == "unfixable":
			continue
		var map := str(action["map"])
		var edited := EditorInterface.get_edited_scene_root()
		if edited == null or edited.scene_file_path != map:
			EditorInterface.open_scene_from_path(map)
			edited = EditorInterface.get_edited_scene_root()
		if edited == null or edited.scene_file_path != map:
			continue
		do_fix(action, edited, plugin.get_undo_redo())
		done += 1
	return done

## Fix: the selected finding (a door that leads nowhere, or a map that cannot be reached).
func fix_selected() -> int:
	var item := _tree.get_selected()
	if item == null:
		_summary.text = "Select a finding first."
		return 0
	var f: Dictionary = item.get_metadata(0)
	if not fixable_codes().has(str(f["code"])):
		_summary.text = "There is no automatic fix for %s." % str(f["code"])
		return 0
	var wanted := Repair.actions_for(plan_world_fixes(), JsonIo.to_str(f["file"]), JsonIo.to_str(f["node"]))
	return _report_fixes(wanted)

## Fix all: every repair the project needs.
func fix_all() -> int:
	return _report_fixes(plan_world_fixes())

func _report_fixes(actions: Array[Dictionary]) -> int:
	var done := apply_fixes(actions)
	var unfixable: PackedStringArray = []
	for action in actions:
		if str(action["kind"]) == "unfixable":
			unfixable.append(str(action["what"]))
	if done == 0 and unfixable.is_empty():
		_summary.text = "Nothing to fix."
	else:
		_summary.text = "%d fix(es) made; Ctrl+Z takes one back. Save the scenes to keep them." % done
		if not unfixable.is_empty():
			_summary.text += " Cannot be mended: " + "; ".join(unfixable)
	return done

## Assigns ids in the scene being edited, as one undo action. Returns the number of changes.
func fix_entity_ids() -> int:
	var root := EditorInterface.get_edited_scene_root()
	if root == null or plugin == null:
		_summary.text = "Open a map scene first."
		return 0
	var elsewhere := _ids_elsewhere(root.scene_file_path)
	var fixes := EntityIds.plan_fixes(root, elsewhere)
	var changes: Array = fixes["changes"]
	if changes.is_empty():
		_summary.text = "Entity ids are fine in this scene."
		return 0
	var undo := plugin.get_undo_redo()
	undo.create_action("Fix entity IDs", UndoRedo.MERGE_DISABLE, root)
	for c: Dictionary in changes:
		var changed: Node = c["node"]
		undo.add_do_property(changed, "entity_id", c["new"])
		undo.add_undo_property(changed, "entity_id", c["old"])
	undo.commit_action()
	var map_id := EntityIds.map_id_of(root)
	var allocations: Dictionary = fixes["allocations"]
	for kind: Variant in allocations.keys():
		Placement.record_allocation(map_id, JsonIo.to_str(kind), JsonIo.to_int(allocations[kind]))
	_summary.text = "%d entity id(s) assigned or renamed. Save the scene to keep them." % changes.size()
	return changes.size()

## Ids used by the other map scenes: id -> true.
static func _ids_elsewhere(own_path: String) -> Dictionary:
	var out := {}
	for path in ContentChecks.list_files(ContentChecks.MAPS_DIR, ["tscn"]):
		if path == own_path:
			continue
		var packed := load(path) as PackedScene
		if packed == null:
			continue
		var inst := packed.instantiate()
		for node in EntityIds.entity_nodes(inst):
			var id := str(node.get("entity_id"))
			if id != "":
				out[id] = true
		inst.free()
	return out
