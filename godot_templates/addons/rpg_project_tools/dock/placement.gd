@tool
extends RefCounted
## Placing library scenes in a map (T8.03). `plan` works out the fix-ups an instance needs (Y-sort
## parent, snapping, flip, entity id) without changing anything; `apply` performs them through
## the editor's undo manager as one action called "Place <name>".

const EntityIds := preload("../tools/entity_ids.gd")
const CatalogEdit := preload("../tools/catalog_edit.gd")
const JsonIo := preload("../tools/json_io.gd")

const YSORT_PATH := "YSorted/Entities"

## Grid step in pixels; 0 = no snapping.
var snap: int = 0
## "auto": the map's YSorted/Entities; "selected": the node that was selected before the drop.
var ysort_mode: String = "auto"
var flip_h: bool = false
var auto_id: bool = true

static func snap_position(pos: Vector2, step: int) -> Vector2:
	if step <= 0:
		return pos
	return (pos / float(step)).round() * float(step)

## The map's Y-sorted entity container, or null.
static func ysort_parent(root: Node) -> Node:
	return root.get_node_or_null(YSORT_PATH)

## The sprite a flip applies to: the first Sprite2D / AnimatedSprite2D below the node.
static func visual_of(node: Node) -> Node:
	for child in node.get_children():
		if child is Sprite2D or child is AnimatedSprite2D:
			return child
	for child in node.get_children():
		var found := visual_of(child)
		if found != null:
			return found
	return null

## The parent an instance goes under. `selected` is the node selected before the drop.
func target_parent(root: Node, current_parent: Node, selected: Node = null) -> Node:
	if ysort_mode == "selected" and selected != null and (selected == root or root.is_ancestor_of(selected)):
		if selected is CanvasItem and (selected as CanvasItem).y_sort_enabled:
			return selected
		var up := selected.get_parent()
		if up is CanvasItem and (up as CanvasItem).y_sort_enabled and (up == root or root.is_ancestor_of(up)):
			return up
	var auto := ysort_parent(root)
	return auto if auto != null else current_parent

## Ids of every entity in the map except `skip`.
static func existing_ids(root: Node, skip: Node = null) -> Array:
	var ids: Array = []
	for node in EntityIds.entity_nodes(root):
		if node == skip:
			continue
		var id := str(node.get("entity_id"))
		if id != "":
			ids.append(id)
	return ids

## The fix-ups of an instance (already in the map, or detached with `world_position` given).
## Returns {parent, old_parent, position, old_position, flip_node, old_flip, flip, entity_id,
## old_entity_id, kind, map_id, number}.
func plan(instance: Node2D, root: Node, entry: Dictionary, selected: Node = null, world_position: Variant = null) -> Dictionary:
	var current_parent: Node = instance.get_parent()
	var parent := target_parent(root, current_parent if current_parent != null else root, selected)
	var world: Vector2 = world_position if world_position is Vector2 else instance.global_position
	world = snap_position(world, snap)
	var local := world
	if parent is Node2D:
		local = (parent as Node2D).to_local(world)
	var out := {
		"parent": parent, "old_parent": current_parent, "position": local, "old_position": instance.position,
		"flip_node": null, "old_flip": false, "flip": false, "entity_id": "", "old_entity_id": "",
		"kind": "", "map_id": "", "number": 0,
	}
	if flip_h:
		var visual := visual_of(instance)
		if visual != null:
			out["flip_node"] = visual
			out["old_flip"] = JsonIo.to_bool(visual.get("flip_h"))
			out["flip"] = true
	if auto_id and EntityIds.has_entity_id(instance) and EntityIds.is_persistent(instance) and str(instance.get("entity_id")) == "":
		var map_id := EntityIds.map_id_of(root)
		var entry_tags: Array = entry.get("tags", [])
		var kind := EntityIds.kind_of(JsonIo.to_str(entry.get("role", "")), entry_tags)
		var number := EntityIds.next_number(existing_ids(root, instance), map_id, kind)
		out["entity_id"] = EntityIds.make_id(map_id, kind, number)
		out["kind"] = kind
		out["map_id"] = map_id
		out["number"] = number
	return out

## Performs a plan with undo. A detached instance is added to the plan's parent.
func apply(plan: Dictionary, instance: Node2D, root: Node, undo: EditorUndoRedoManager, display_name: String) -> void:
	var parent: Node = plan["parent"]
	undo.create_action("Place %s" % display_name, UndoRedo.MERGE_DISABLE, root)
	if not instance.is_inside_tree():
		undo.add_do_method(parent, "add_child", instance, true)
		undo.add_do_method(instance, "set_owner", root)
		undo.add_do_reference(instance)
		undo.add_undo_method(parent, "remove_child", instance)
	elif plan["old_parent"] != parent:
		undo.add_do_method(instance, "reparent", parent, false)
		undo.add_undo_method(instance, "reparent", plan["old_parent"], false)
	undo.add_do_property(instance, "position", plan["position"])
	undo.add_undo_property(instance, "position", plan["old_position"])
	var flip_node: Node = plan["flip_node"]
	if flip_node != null:
		undo.add_do_property(flip_node, "flip_h", plan["flip"])
		undo.add_undo_property(flip_node, "flip_h", plan["old_flip"])
	if JsonIo.to_str(plan["entity_id"]) != "":
		undo.add_do_property(instance, "entity_id", plan["entity_id"])
		undo.add_undo_property(instance, "entity_id", plan["old_entity_id"])
	undo.commit_action()
	if JsonIo.to_str(plan["entity_id"]) != "":
		record_allocation(JsonIo.to_str(plan["map_id"]), JsonIo.to_str(plan["kind"]), JsonIo.to_int(plan["number"]))

## Writes the number used for an id into the catalog's id_allocations.entities.
static func record_allocation(map_id: String, kind: String, number: int) -> void:
	var catalog := CatalogEdit.load_catalog()
	if catalog.is_empty():
		return
	var allocations := CatalogEdit.entity_allocations(catalog, map_id)
	if JsonIo.to_int(allocations.get(kind, 0)) == number:
		return
	allocations[kind] = number
	if CatalogEdit.save_catalog(catalog) != OK:
		push_error("[RPG-TOOLS] could not save the entity id allocation to the catalog")

## Instances a library scene at `world_position` (the double-click path) and applies the same
## fix-ups. Returns the new node, or null when the scene cannot be loaded.
func place_new(entry: Dictionary, root: Node, undo: EditorUndoRedoManager, world_position: Vector2, selected: Node = null) -> Node:
	var packed := load(JsonIo.to_str(entry["scene_path"])) as PackedScene
	if packed == null:
		return null
	var instance := packed.instantiate() as Node2D
	if instance == null:
		return null
	var p := plan(instance, root, entry, selected, world_position)
	apply(p, instance, root, undo, JsonIo.to_str(entry["name"]))
	return instance
