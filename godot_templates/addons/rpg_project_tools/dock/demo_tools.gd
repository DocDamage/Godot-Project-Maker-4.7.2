@tool
extends RefCounted
## "Remove demo content" (T8.08): deletes game/demo/ (when present), removes the demo NPC, chest
## and enemy from the starter map (undoable), removes interior_1.tscn when it is untouched,
## empties the starting items of new_game.tres and records `demo_removed` in the ownership ledger
## so regeneration does not bring the demo back.

const JsonIo := preload("../tools/json_io.gd")
const FileHash := preload("../tools/file_hash.gd")
const EntityIds := preload("../tools/entity_ids.gd")

const DEMO_DIR := "res://game/demo"
const MAP_PATH := "res://game/maps/starter_map.tscn"
const INTERIOR_PATH := "res://game/maps/interior_1.tscn"
const NEW_GAME_PATH := "res://game/data/new_game.tres"
const DEMO_ENTITIES_PATH := "res://rpggen/demo_entities.json"
const LEDGER_PATH := "res://rpggen/ownership_ledger.json"
const DOOR_SUFFIX := "/world/door.gd"
## The ids the recipes give the demo entities; used when rpggen/demo_entities.json is missing
## (a project generated before M8).
const DEFAULT_IDS := ["starter_map_npc_001", "starter_map_chest_001", "starter_map_enemy_001"]

## The ids of the demo entities: rpggen/demo_entities.json, else the defaults.
static func demo_ids(entities_json: Variant = null) -> Array:
	var data: Variant = entities_json if entities_json != null else JsonIo.read(DEMO_ENTITIES_PATH)
	if data is Dictionary and data.get("entities") is Array:
		return data["entities"].duplicate()
	return DEFAULT_IDS.duplicate()

## The nodes below `root` whose entity_id is one of `ids`.
static func demo_nodes(root: Node, ids: Array) -> Array:
	var out: Array = []
	for node in EntityIds.entity_nodes(root):
		if ids.has(str(node.get("entity_id"))):
			out.append(node)
	return out

## Door nodes below `root` whose target_map is `target`.
static func doors_targeting(root: Node, target: String) -> Array:
	var out: Array = []
	var stack: Array = [root]
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var script := node.get_script() as Script
		if script != null and script.resource_path.ends_with(DOOR_SUFFIX) and str(node.get("target_map")) == target:
			out.append(node)
		stack.append_array(node.get_children())
	return out

## True when the ledger knows the file and it still has the content the generator wrote.
static func untouched(ledger: Dictionary, res_path: String) -> bool:
	var files: Variant = ledger.get("files")
	if not (files is Dictionary):
		return false
	var entry: Variant = files.get(res_path.trim_prefix("res://"))
	return entry is Dictionary and FileHash.file_hash(res_path) == String(entry.get("sha256", ""))

## The ledger after the removal: demo_removed set, the removed files recorded as user deletions.
static func updated_ledger(ledger: Dictionary, removed: Array) -> Dictionary:
	var out := ledger.duplicate(true)
	out["demo_removed"] = true
	var deleted: Array = out.get("deleted_by_user", [])
	for rel in removed:
		if not deleted.has(rel):
			deleted.append(rel)
	deleted.sort()
	out["deleted_by_user"] = deleted
	return out

## Every file below a directory (res:// paths), recursive.
static func files_below(dir_path: String) -> Array:
	var out: Array = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return out
	for sub in dir.get_directories():
		out.append_array(files_below(dir_path + "/" + sub))
	for f in dir.get_files():
		out.append(dir_path + "/" + f)
	return out

static func _remove_dir(dir_path: String) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		_remove_dir(dir_path + "/" + sub)
	for f in dir.get_files():
		DirAccess.remove_absolute(dir_path + "/" + f)
	DirAccess.remove_absolute(dir_path)

## Removes the demo. Returns {nodes, files, messages}: how many map nodes were removed, the
## res:// files deleted and a line per step for the status label.
func remove(plugin: EditorPlugin) -> Dictionary:
	var result := {"nodes": 0, "files": [], "messages": []}
	var ledger_data: Variant = JsonIo.read(LEDGER_PATH)
	var ledger: Dictionary = ledger_data if ledger_data is Dictionary else {}
	var removed_rels: Array = []
	for f in files_below(DEMO_DIR):
		result["files"].append(f)
		removed_rels.append(String(f).trim_prefix("res://"))
	_remove_dir(DEMO_DIR)
	if not result["files"].is_empty():
		result["messages"].append("Deleted game/demo/ (%d files)." % result["files"].size())
	var interior_removed := false
	if FileAccess.file_exists(INTERIOR_PATH):
		if untouched(ledger, INTERIOR_PATH):
			DirAccess.remove_absolute(INTERIOR_PATH)
			interior_removed = true
			result["files"].append(INTERIOR_PATH)
			removed_rels.append(INTERIOR_PATH.trim_prefix("res://"))
			result["messages"].append("Removed interior_1.tscn.")
		else:
			result["messages"].append("Kept interior_1.tscn: it was changed.")
	result["nodes"] = _remove_map_nodes(plugin, interior_removed)
	if result["nodes"] > 0:
		result["messages"].append("Removed %d demo entities from the starter map." % result["nodes"])
	_empty_start_items(result)
	JsonIo.write(LEDGER_PATH, updated_ledger(ledger, removed_rels))
	EditorInterface.get_resource_filesystem().scan()
	return result

## Takes the demo entities out of the starter map with undo and saves the map. When the interior
## was removed, the doors that led to it are cleared (an unset door is not an error).
func _remove_map_nodes(plugin: EditorPlugin, clear_doors: bool) -> int:
	if not FileAccess.file_exists(MAP_PATH):
		return 0
	var root := EditorInterface.get_edited_scene_root()
	if root == null or root.scene_file_path != MAP_PATH:
		EditorInterface.open_scene_from_path(MAP_PATH)
		root = EditorInterface.get_edited_scene_root()
	if root == null:
		return 0
	var nodes := demo_nodes(root, demo_ids())
	var doors := doors_targeting(root, INTERIOR_PATH) if clear_doors else []
	if nodes.is_empty() and doors.is_empty():
		return 0
	var undo := plugin.get_undo_redo()
	undo.create_action("Remove demo content", UndoRedo.MERGE_DISABLE, root)
	for node in nodes:
		var parent: Node = node.get_parent()
		undo.add_do_method(parent, "remove_child", node)
		undo.add_undo_method(parent, "add_child", node, true)
		undo.add_undo_method(node, "set_owner", root)
		undo.add_undo_reference(node)
	for door in doors:
		undo.add_do_property(door, "target_map", "")
		undo.add_undo_property(door, "target_map", INTERIOR_PATH)
	undo.commit_action()
	EditorInterface.save_scene()
	return nodes.size()

## new_game.tres starts without items.
func _empty_start_items(result: Dictionary) -> void:
	if not FileAccess.file_exists(NEW_GAME_PATH):
		return
	var ng := ResourceLoader.load(NEW_GAME_PATH, "", ResourceLoader.CACHE_MODE_IGNORE)
	if ng == null or ng.get("items") == null or ng.get("items").is_empty():
		return
	ng.get("items").clear()
	if ResourceSaver.save(ng, NEW_GAME_PATH) == OK:
		result["messages"].append("The new game starts without items.")
