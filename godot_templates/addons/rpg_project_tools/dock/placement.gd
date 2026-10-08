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

# ---------------------------------------------------------------- trigger areas (T12.54)

const TRIGGERS_PATH := "Triggers"
const SEQUENCES_DIR := "res://game/data/sequences"
const TRIGGER_SCRIPT := "res://addons/rpg_runtime/world/trigger_area.gd"
const SEQUENCE_SCRIPT := "res://addons/rpg_runtime/events/sequence.gd"

## Where a new trigger area goes: {parent (the map's Triggers node, else the root), position (local
## to the parent), entity_id (<map>_trigger_<n>), sequence_path (game/data/sequences/<entity_id>.tres),
## size (one tile), on_interact}. Nothing is changed.
static func plan_trigger(root: Node, world_position: Vector2, tile: int, step: int, on_interact: bool, sequences_dir: String = SEQUENCES_DIR) -> Dictionary:
	var parent: Node = root.get_node_or_null(TRIGGERS_PATH)
	if parent == null:
		parent = root
	var map_id := EntityIds.map_id_of(root)
	var number := EntityIds.next_number(existing_ids(root), map_id, "trigger")
	var entity_id := EntityIds.make_id(map_id, "trigger", number)
	var world := snap_position(world_position, step)
	var local := world
	if parent is Node2D and (parent as Node2D).is_inside_tree():
		local = (parent as Node2D).to_local(world)
	return {
		"parent": parent, "position": local, "entity_id": entity_id, "on_interact": on_interact,
		"sequence_path": "%s/%s.tres" % [sequences_dir, entity_id], "size": Vector2(tile, tile),
	}

## The trigger area of a plan, not yet in the map: an RpgTriggerArea with a one-tile rectangle.
static func build_trigger(plan: Dictionary) -> Area2D:
	var area := Area2D.new()
	area.set_script(load(TRIGGER_SCRIPT))
	var entity_id := JsonIo.to_str(plan["entity_id"])
	area.name = "Trigger_" + entity_id.get_slice("_", entity_id.get_slice_count("_") - 1)
	area.set("entity_id", entity_id)
	area.set("sequence_id", StringName(entity_id))
	area.set("on_interact", JsonIo.to_bool(plan["on_interact"]))
	var at: Vector2 = plan["position"]
	area.position = at
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var rect := RectangleShape2D.new()
	var size: Vector2 = plan["size"]
	rect.size = size
	shape.shape = rect
	area.add_child(shape)
	return area

## Writes an empty sequence (id = the trigger's entity id) unless the file exists. Returns the error.
static func make_sequence_file(path: String, sequence_id: String) -> int:
	if ResourceLoader.exists(path):
		return OK
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var sequence := Resource.new()
	sequence.set_script(load(SEQUENCE_SCRIPT))
	sequence.set("id", StringName(sequence_id))
	var commands: Array[Dictionary] = [{"cmd": "show_dialogue", "lines": ["..."]}]
	sequence.set("commands", commands)
	return ResourceSaver.save(sequence, path)

## Adds the planned trigger area with undo ("Add trigger area") and creates its sequence file.
static func add_trigger(plan: Dictionary, root: Node, undo: EditorUndoRedoManager) -> Area2D:
	var area := build_trigger(plan)
	var parent: Node = plan["parent"]
	undo.create_action("Add trigger area", UndoRedo.MERGE_DISABLE, root)
	undo.add_do_method(parent, "add_child", area, true)
	undo.add_do_method(area, "set_owner", root)
	undo.add_do_method(area.get_node("Shape"), "set_owner", root)
	undo.add_do_reference(area)
	undo.add_undo_method(parent, "remove_child", area)
	undo.commit_action()
	if make_sequence_file(JsonIo.to_str(plan["sequence_path"]), JsonIo.to_str(plan["entity_id"])) != OK:
		push_error("[RPG-TOOLS] could not write %s" % plan["sequence_path"])
	return area

# ---------------------------------------------------------------- encounter zones (T12.53)

const ZONE_SCRIPT := "res://addons/rpg_runtime/world/encounter_zone.gd"
const TABLE_SCRIPT := "res://addons/rpg_runtime/data/encounter_table.gd"
const ENCOUNTERS_DIR := "res://game/data/encounters"
const ENEMIES_DIR := "res://game/data/enemies"
const ZONE_MIN_TILES := 3
const ZONE_DEFAULT_TILES := 6

## A zone over the selection: {parent, name, polygon (local to the parent), cells_layer (from the
## zone to a selected TileMapLayer, or an empty path), table_path, table_id, enemies}. A selected
## TileMapLayer makes the zone its painted cells; other selected 2D nodes give the rectangle around
## them (half a tile of margin, at least 3x3 tiles); with nothing selected it is 6x6 tiles around
## `centre`. The table lists every enemy definition of the project as a group of one. Nothing is
## changed.
static func plan_zone(root: Node, selected: Array, centre: Vector2, tile: int, enemies_dir: String = ENEMIES_DIR, encounters_dir: String = ENCOUNTERS_DIR) -> Dictionary:
	var parent: Node = root.get_node_or_null(TRIGGERS_PATH)
	if parent == null:
		parent = root
	var layer: TileMapLayer = null
	var points: Array[Vector2] = []
	for node: Variant in selected:
		if node is TileMapLayer and layer == null:
			layer = node
		elif node is Node2D and node != root:
			var picked: Node2D = node
			points.append(RpgUtil.world_position(picked))
	var t := float(tile)
	var rect := Rect2(centre - Vector2(t, t) * ZONE_DEFAULT_TILES / 2.0, Vector2(t, t) * ZONE_DEFAULT_TILES)
	if not points.is_empty():
		rect = Rect2(points[0], Vector2.ZERO)
		for p in points:
			rect = rect.expand(p)
		rect = rect.grow(t / 2.0)
		var least := t * ZONE_MIN_TILES
		rect = rect.grow_individual(maxf(0.0, (least - rect.size.x) / 2.0), maxf(0.0, (least - rect.size.y) / 2.0), maxf(0.0, (least - rect.size.x) / 2.0), maxf(0.0, (least - rect.size.y) / 2.0))
	var origin := RpgUtil.world_position(parent as Node2D) if parent is Node2D else Vector2.ZERO
	var polygon := PackedVector2Array()
	if layer == null:
		for corner: Vector2 in [rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)]:
			polygon.append((corner - origin).snapped(Vector2(1, 1)))
	var map_id := EntityIds.map_id_of(root)
	var number := 1
	for existing in root.find_children("*", "Area2D", true, false):
		var script: Script = existing.get_script()
		if script != null and script.resource_path == ZONE_SCRIPT:
			number += 1
	var table_id := "%s_zone_%d" % [map_id, number]
	while ResourceLoader.exists("%s/%s.tres" % [encounters_dir, table_id]):
		number += 1
		table_id = "%s_zone_%d" % [map_id, number]
	var enemies: Array[String] = []
	var dir := DirAccess.open(enemies_dir)
	if dir != null:
		var files := dir.get_files()
		files.sort()
		for file_name in files:
			if file_name.trim_suffix(".remap").ends_with(".tres"):
				enemies.append(file_name.trim_suffix(".remap").get_basename())
	return {
		"parent": parent, "name": "EncounterZone%d" % number, "polygon": polygon,
		"cells_layer": NodePath("../" + String(parent.get_path_to(layer))) if layer != null else NodePath(),
		"table_id": table_id, "table_path": "%s/%s.tres" % [encounters_dir, table_id], "enemies": enemies,
	}

## Writes the plan's encounter table (one group of one per enemy id) and returns it, or null.
static func make_table_file(plan: Dictionary) -> Resource:
	var path := JsonIo.to_str(plan["table_path"])
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var table := Resource.new()
	table.set_script(load(TABLE_SCRIPT))
	table.set("id", StringName(JsonIo.to_str(plan["table_id"])))
	var groups: Array[Dictionary] = []
	for enemy_id: Variant in JsonIo.to_array(plan["enemies"]):
		groups.append({"enemies": [JsonIo.to_str(enemy_id)], "weight": 1})
	table.set("groups", groups)
	if ResourceSaver.save(table, path) != OK:
		return null
	return load(path)

## The zone of a plan, not yet in the map.
static func build_zone(plan: Dictionary, table: Resource) -> Area2D:
	var zone := Area2D.new()
	zone.set_script(load(ZONE_SCRIPT))
	zone.name = JsonIo.to_str(plan["name"])
	zone.set("table", table)
	var cells: NodePath = plan["cells_layer"]
	if not cells.is_empty():
		zone.set("cells_layer", cells)
	else:
		var shape := CollisionPolygon2D.new()
		shape.name = "Shape"
		var polygon: PackedVector2Array = plan["polygon"]
		shape.polygon = polygon
		zone.add_child(shape)
	return zone

## Adds the planned zone with undo ("Add encounter zone") after writing its table.
static func add_zone(plan: Dictionary, root: Node, undo: EditorUndoRedoManager) -> Area2D:
	var table := make_table_file(plan)
	if table == null:
		push_error("[RPG-TOOLS] could not write %s" % plan["table_path"])
	var zone := build_zone(plan, table)
	var parent: Node = plan["parent"]
	undo.create_action("Add encounter zone", UndoRedo.MERGE_DISABLE, root)
	undo.add_do_method(parent, "add_child", zone, true)
	undo.add_do_method(zone, "set_owner", root)
	for child in zone.get_children():
		undo.add_do_method(child, "set_owner", root)
	undo.add_do_reference(zone)
	undo.add_undo_method(parent, "remove_child", zone)
	undo.commit_action()
	return zone

# ---------------------------------------------------------------- gates and switches (T12.70)

const GATE_SCRIPT := "res://addons/rpg_runtime/world/gate.gd"
const SWITCH_SCRIPT := "res://addons/rpg_runtime/world/switch.gd"
## The kinds the dock adds: a gate, a floor plate, a lever.
const LOCK_KINDS: Array[String] = ["gate", "plate", "lever"]

## A new gate or switch: {parent (the map's YSorted/Entities, else the root), position (snapped,
## local to the parent), entity_id (<map>_gate_<n> or <map>_switch_<n>), kind, size, gate (the
## selected gate a new switch opens, or null)}. Nothing is changed.
static func plan_lock(root: Node, world_position: Vector2, tile: int, kind: String, selected: Node = null) -> Dictionary:
	var parent: Node = ysort_parent(root)
	if parent == null:
		parent = root
	var id_kind := "gate" if kind == "gate" else "switch"
	var map_id := EntityIds.map_id_of(root)
	var number := EntityIds.next_number(existing_ids(root), map_id, id_kind)
	var world := snap_position(world_position, tile)
	var local := world
	if parent is Node2D and (parent as Node2D).is_inside_tree():
		local = (parent as Node2D).to_local(world)
	var gate: Node = null
	if kind != "gate" and selected != null:
		var script: Script = selected.get_script()
		if script != null and script.resource_path == GATE_SCRIPT:
			gate = selected
	var t := float(tile)
	return {
		"parent": parent, "position": local, "entity_id": EntityIds.make_id(map_id, id_kind, number),
		"kind": kind, "size": Vector2(t, t) if kind == "gate" else Vector2(t, t) * 0.75, "gate": gate,
	}

## The gate or switch of a plan, not yet in the map.
static func build_lock(plan: Dictionary) -> Node2D:
	var kind := JsonIo.to_str(plan["kind"])
	var node: Node2D
	if kind == "gate":
		node = StaticBody2D.new()
		node.set_script(load(GATE_SCRIPT))
	else:
		node = Area2D.new()
		node.set_script(load(SWITCH_SCRIPT))
	var entity_id := JsonIo.to_str(plan["entity_id"])
	node.name = ("Gate_" if kind == "gate" else "Switch_") + entity_id.get_slice("_", entity_id.get_slice_count("_") - 1)
	node.set("entity_id", entity_id)
	var size: Vector2 = plan["size"]
	node.set("size", size)
	if kind != "gate":
		node.set("kind", 1 if kind == "lever" else 0)  # RpgSwitch.Kind.LEVER / PLATE
	var at: Vector2 = plan["position"]
	node.position = at
	return node

## The condition a gate opened by this switch gets.
static func switch_condition(switch_id: String) -> String:
	return "flag:%s.on" % switch_id

## Adds the planned gate or switch with undo; a switch planned for a selected gate also sets the
## gate's `open_when` in the same action.
static func add_lock(plan: Dictionary, root: Node, undo: EditorUndoRedoManager) -> Node2D:
	var node := build_lock(plan)
	var parent: Node = plan["parent"]
	var gate: Node = plan["gate"]
	undo.create_action("Add %s" % JsonIo.to_str(plan["kind"]), UndoRedo.MERGE_DISABLE, root)
	undo.add_do_method(parent, "add_child", node, true)
	undo.add_do_method(node, "set_owner", root)
	undo.add_do_reference(node)
	undo.add_undo_method(parent, "remove_child", node)
	if gate != null:
		undo.add_do_property(gate, "open_when", switch_condition(JsonIo.to_str(plan["entity_id"])))
		undo.add_undo_property(gate, "open_when", gate.get("open_when"))
	undo.commit_action()
	return node
