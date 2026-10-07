@tool
extends VBoxContainer
## "Validate content" (T8.04): runs the content checks of tools/content_checks.gd, lists the
## findings in a tree and opens the scene of a finding on double-click. "Fix entity IDs" assigns
## ids to the edited scene's persistent entities that have none and renames later duplicates.

const ContentChecks := preload("../tools/content_checks.gd")
const EntityIds := preload("../tools/entity_ids.gd")
const Placement := preload("placement.gd")

const ERROR_CODES_PATHS := ["res://generated/builder/lib/error_codes.gd", "res://builder/lib/error_codes.gd"]

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
	var text := String(info.get("message", finding["code"]))
	for key in finding["detail"].keys():
		text = text.replace("{%s}" % str(key), str(finding["detail"][key]))
	return {"severity": String(info.get("severity", "warning")), "message": "%s: %s" % [finding["code"], text]}

func validate_now() -> void:
	_findings = ContentChecks.run()
	_tree.clear()
	var codes := _error_codes()
	var root := _tree.create_item()
	var errors := 0
	var warnings := 0
	for f in _findings:
		var d := describe(f, codes)
		var item := _tree.create_item(root)
		item.set_text(0, d["message"])
		item.set_text(1, String(f["file"]).trim_prefix("res://"))
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
	var path := String(f["file"])
	if path.get_extension() != "tscn":
		return
	var edited := EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != path:
		EditorInterface.open_scene_from_path(path)
		edited = EditorInterface.get_edited_scene_root()
	var node_path := String(f["node"])
	if edited != null and node_path != "":
		var node := edited.get_node_or_null(node_path)
		if node != null:
			var selection := EditorInterface.get_selection()
			selection.clear()
			selection.add_node(node)

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
	for c in changes:
		undo.add_do_property(c["node"], "entity_id", c["new"])
		undo.add_undo_property(c["node"], "entity_id", c["old"])
	undo.commit_action()
	var map_id := EntityIds.map_id_of(root)
	for kind in fixes["allocations"].keys():
		Placement.record_allocation(map_id, String(kind), int(fixes["allocations"][kind]))
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
