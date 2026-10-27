@tool
extends RefCounted
## Placing library scenes in a map (T8.03). `plan` works out the fix-ups an instance needs (Y-sort
## parent, snapping, flip, entity id) without changing anything; `apply` performs them through
## the editor's undo manager as one action called "Place <name>".
##
## A map of diamonds (T17.27, `projection: isometric`) is asked through RpgIso, the runtime's
## arithmetic: what is placed stands on the middle of the diamond under it, as the builder
## stands it. A map of squares is placed in as it always was.
##
## On a cell of an isometric map with something stacked on it (a block, a storey, a roof on the
## level's height layers: tools/height_layers.gd, 2026-10-26) what is placed stands on the top of
## the stack: it goes into a node `Raised` on the cell's middle, by which it sorts as everything
## on that cell does, and lies `raise` px higher in it.

const EntityIds := preload("../tools/entity_ids.gd")
const CatalogEdit := preload("../tools/catalog_edit.gd")
const JsonIo := preload("../tools/json_io.gd")
const HeightLayers := preload("../tools/height_layers.gd")

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

## A side-view room (T14.04): its root says so (RpgRoom has `side_view`).
static func is_side_view(root: Node) -> bool:
	return root != null and JsonIo.to_bool(root.get("side_view"))

## How many cells below the drop point the floor is looked for.
const FLOOR_SEARCH_CELLS := 64

## In a side-view room an object stands on the floor: the top of the nearest tile with a collision
## shape at or below `world`. Without one the point is returned as it is.
static func floor_below(root: Node, world: Vector2) -> Vector2:
	var best := INF
	for node in root.find_children("*", "TileMapLayer", true, false):
		var layer := node as TileMapLayer
		if layer.tile_set == null:
			continue
		var tile := Vector2(layer.tile_set.tile_size)
		var origin := layer.global_position if layer.is_inside_tree() else layer.position
		var local := world - origin
		var cell := Vector2i(floori(local.x / tile.x), floori(local.y / tile.y))
		for step in FLOOR_SEARCH_CELLS:
			var at := Vector2i(cell.x, cell.y + step)
			var data := layer.get_cell_tile_data(at)
			if data == null:
				continue
			var solid := false
			for physics in layer.tile_set.get_physics_layers_count():
				if data.get_collision_polygons_count(physics) > 0:
					solid = true
			if solid:
				best = minf(best, origin.y + at.y * tile.y)
				break
	return Vector2(world.x, best) if best != INF else world

# ---------------------------------------------------------------- diamonds (T17.27)

## The diamond of an isometric map's cells (the size of its tile set); Vector2i.ZERO for a map
## of squares or without tiles, where nothing below is asked.
static func diamond_of(root: Node) -> Vector2i:
	return RpgIso.footprint_of(root)

## The middle of the diamond under `world`: where the builder puts an actor, a marker and the
## origin of an object's picture (builder/lib/map_geo.gd `center`). With snapping off (`step` 0)
## the point is returned as it is.
static func snap_to_diamond(root: Node, world: Vector2, step: int) -> Vector2:
	if step <= 0:
		return world
	return RpgIso.cell_position(root, RpgIso.cell_at(root, world))

## How many cells a library scene stands on, [columns, rows]: the `stands_on` the builder wrote
## on an isometric object scene (object_scenes_recipe.gd), one cell for everything else.
static func stands_on(instance: Node) -> Vector2i:
	if instance == null or not instance.has_meta("stands_on"):
		return Vector2i.ONE
	var pair := JsonIo.to_array(instance.get_meta("stands_on"))
	if pair.size() != 2:
		return Vector2i.ONE
	return Vector2i(maxi(1, JsonIo.to_int(pair[0])), maxi(1, JsonIo.to_int(pair[1])))

## The cells an object of `size` cells stands on when its origin is on `cell`: `cell` is the one
## nearest the camera (the highest x and y), as the builder's IsoTileset.cells_under counts.
static func cells_under(cell: Vector2i, size: Vector2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for dy in maxi(1, size.y):
		for dx in maxi(1, size.x):
			out.append(cell - Vector2i(dx, dy))
	return out

## The outline of a rectangle of cells of an isometric map, in the world: the top, the right,
## the bottom and the left corner.
static func cells_outline(root: Node, cells: Rect2i) -> PackedVector2Array:
	var diamond := diamond_of(root)
	var last := cells.end - Vector2i.ONE
	# where the layer's own px are in the world (RpgIso.diamond counts in the layer)
	var shift := RpgIso.cell_position(root, cells.position) - RpgIso.cell_to_screen(cells.position, diamond)
	return PackedVector2Array([
		RpgIso.diamond(cells.position, diamond)[0] + shift,
		RpgIso.diamond(Vector2i(last.x, cells.position.y), diamond)[1] + shift,
		RpgIso.diamond(last, diamond)[2] + shift,
		RpgIso.diamond(Vector2i(cells.position.x, last.y), diamond)[3] + shift,
	])

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

## A readable name no other child of `parent` has (`skip` aside), made from `wanted` the way the
## editor names a second copy of a scene: "treeoak" is taken, so "treeoak2"; "treeoak2" is
## taken, so "treeoak3" (Node's own serial names with the editor's default, no separator).
## `Node.reparent` would give a taken name a name like "@StaticBody2D@20523" instead.
static func free_name(parent: Node, wanted: String, skip: Node = null) -> String:
	var taken := {}
	if parent != null:
		for child in parent.get_children(true):
			if child != skip:
				taken[String(child.name)] = true
	if not taken.has(wanted):
		return wanted
	var stem := wanted
	while stem != "" and stem[stem.length() - 1].is_valid_int():
		stem = stem.left(stem.length() - 1)
	var number := 2 if stem == wanted else wanted.substr(stem.length()).to_int() + 1
	while taken.has(stem + str(number)):
		number += 1
	return stem + str(number)

## A library scene's instance as the editor makes one, so that the map saves it as an instance of
## its scene (`instance=ExtResource(...)` and only what was changed), not as a copy of its root.
static func instance_for_edit(packed: PackedScene) -> Node:
	return packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)

## The fix-ups of an instance (already in the map, or detached with `world_position` given).
## Returns {parent, old_parent, position, old_position, flip_node, old_flip, flip, entity_id,
## old_entity_id, kind, map_id, number, name, old_name}; `name` is the instance's own name, or a
## readable one free under the new parent (`free_name`). On an isometric map (T17.27) the position is the middle
## of the diamond under the point (with any snapping on: a grid of px means nothing there), and
## the plan also has `cell` (that diamond) and `cells` (every cell the object stands on, `cell`
## being the one nearest the camera). Nothing is dropped to a floor there: a room seen from the
## side is never isometric.
func plan(instance: Node2D, root: Node, entry: Dictionary, selected: Node = null, world_position: Variant = null) -> Dictionary:
	var current_parent: Node = instance.get_parent()
	var parent := target_parent(root, current_parent if current_parent != null else root, selected)
	var world: Vector2 = world_position if world_position is Vector2 else instance.global_position
	var diamond := diamond_of(root)
	world = snap_position(world, snap) if diamond == Vector2i.ZERO else snap_to_diamond(root, world, snap)
	if is_side_view(root):
		world = floor_below(root, world)  # no Y-sort in a room: things stand on the floor
	var local := world
	if parent is Node2D:
		local = (parent as Node2D).to_local(world)
	var out := {
		"parent": parent, "old_parent": current_parent, "position": local, "old_position": instance.position,
		"flip_node": null, "old_flip": false, "flip": false, "entity_id": "", "old_entity_id": "",
		"kind": "", "map_id": "", "number": 0,
		"name": String(instance.name) if parent == current_parent else free_name(parent, String(instance.name), instance),
		"old_name": String(instance.name),
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
	if diamond != Vector2i.ZERO:
		var cell := RpgIso.cell_at(root, world)
		out["cell"] = cell
		out["cells"] = cells_under(cell, stands_on(instance))
		out["raise"] = HeightLayers.top_at(root, cell)
	return out

## Performs a plan with undo. A detached instance is added to the plan's parent under the plan's
## name; one that moves to another parent is given the plan's name there.
##
## The undo of an action runs its operations in the order they were added, not backwards (Godot
## 4.7, docs/godot_api_verified.md): what takes the instance out of the map or back to where it
## was is added last, after the properties it sets back, so that each is set while the node is
## still in the tree.
func apply(plan: Dictionary, instance: Node2D, root: Node, undo: EditorUndoRedoManager, display_name: String) -> void:
	if JsonIo.to_int(plan.get("raise", 0)) > 0:
		_apply_raised(plan, instance, root, undo, display_name)
		return
	var parent: Node = plan["parent"]
	var fresh := not instance.is_inside_tree()
	var old_parent: Node = plan["old_parent"]
	var moved: bool = not fresh and old_parent != parent
	var new_name := JsonIo.to_str(plan.get("name", String(instance.name)))
	var old_name := JsonIo.to_str(plan.get("old_name", String(instance.name)))
	var flip_node: Node = plan["flip_node"]
	var has_id := JsonIo.to_str(plan["entity_id"]) != ""
	undo.create_action("Place %s" % display_name, UndoRedo.MERGE_DISABLE, root)
	if fresh:
		instance.name = new_name  # free under the parent: add_child keeps it
		undo.add_do_method(parent, "add_child", instance, true)
		undo.add_do_method(instance, "set_owner", root)
		undo.add_do_reference(instance)
	elif moved:
		undo.add_do_method(instance, "reparent", parent, false)
		if new_name != old_name:
			undo.add_do_method(instance, "set_name", new_name)
	undo.add_do_property(instance, "position", plan["position"])
	if flip_node != null:
		undo.add_do_property(flip_node, "flip_h", plan["flip"])
	if has_id:
		undo.add_do_property(instance, "entity_id", plan["entity_id"])
	# the undo: first the properties, then the tree
	if has_id:
		undo.add_undo_property(instance, "entity_id", plan["old_entity_id"])
	if flip_node != null:
		undo.add_undo_property(flip_node, "flip_h", plan["old_flip"])
	undo.add_undo_property(instance, "position", plan["old_position"])
	if fresh:
		undo.add_undo_method(parent, "remove_child", instance)
	elif moved:
		undo.add_undo_method(instance, "reparent", old_parent, false)
		if new_name != old_name:
			undo.add_undo_method(instance, "set_name", old_name)
	undo.commit_action()
	if JsonIo.to_str(plan["entity_id"]) != "":
		record_allocation(JsonIo.to_str(plan["map_id"]), JsonIo.to_str(plan["kind"]), JsonIo.to_int(plan["number"]))

const RAISED_NAME := "Raised"

## `apply` for a plan whose cell has a stack (`raise` > 0): a node `Raised` on the cell's middle,
## in the plan's parent, holds the instance `raise` px higher. The undo takes the instance out
## of it (back where it was, for one that was dropped) and the node away, after the properties.
func _apply_raised(plan: Dictionary, instance: Node2D, root: Node, undo: EditorUndoRedoManager, display_name: String) -> void:
	var parent: Node = plan["parent"]
	var fresh := not instance.is_inside_tree()
	var old_parent: Node = plan["old_parent"]
	var raise := JsonIo.to_int(plan["raise"])
	var holder := Node2D.new()
	holder.name = free_name(parent, RAISED_NAME)
	holder.position = plan["position"]
	holder.set_meta(HeightLayers.HEIGHT_META, raise)
	var new_name := JsonIo.to_str(plan.get("name", String(instance.name)))
	var old_name := JsonIo.to_str(plan.get("old_name", String(instance.name)))
	var flip_node: Node = plan["flip_node"]
	var has_id := JsonIo.to_str(plan["entity_id"]) != ""
	undo.create_action("Place %s" % display_name, UndoRedo.MERGE_DISABLE, root)
	undo.add_do_method(parent, "add_child", holder, true)
	undo.add_do_method(holder, "set_owner", root)
	undo.add_do_reference(holder)
	if fresh:
		instance.name = new_name
		undo.add_do_method(holder, "add_child", instance, true)
		undo.add_do_method(instance, "set_owner", root)
		undo.add_do_reference(instance)
	else:
		undo.add_do_method(instance, "reparent", holder, false)
		if new_name != old_name:
			undo.add_do_method(instance, "set_name", new_name)
	undo.add_do_property(instance, "position", Vector2(0, -raise))
	if flip_node != null:
		undo.add_do_property(flip_node, "flip_h", plan["flip"])
	if has_id:
		undo.add_do_property(instance, "entity_id", plan["entity_id"])
	# the undo: first the properties, then the tree
	if has_id:
		undo.add_undo_property(instance, "entity_id", plan["old_entity_id"])
	if flip_node != null:
		undo.add_undo_property(flip_node, "flip_h", plan["old_flip"])
	undo.add_undo_property(instance, "position", plan["old_position"])
	if fresh:
		undo.add_undo_method(holder, "remove_child", instance)
	else:
		undo.add_undo_method(instance, "reparent", old_parent, false)
		if new_name != old_name:
			undo.add_undo_method(instance, "set_name", old_name)
	undo.add_undo_method(parent, "remove_child", holder)
	undo.commit_action()
	if has_id:
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
## fix-ups. Returns the new node, or null when the scene cannot be loaded. The instance is made as
## the editor makes a dropped one (`instance_for_edit`), so the map saves it the same way.
func place_new(entry: Dictionary, root: Node, undo: EditorUndoRedoManager, world_position: Vector2, selected: Node = null) -> Node:
	var packed := load(JsonIo.to_str(entry["scene_path"])) as PackedScene
	if packed == null:
		return null
	var instance := instance_for_edit(packed) as Node2D
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
## size (one tile), on_interact}. Nothing is changed. On an isometric map the position is the
## middle of the diamond under the point and the plan has `diamond`, the size of a cell: the
## area is that diamond.
static func plan_trigger(root: Node, world_position: Vector2, tile: int, step: int, on_interact: bool, sequences_dir: String = SEQUENCES_DIR) -> Dictionary:
	var parent: Node = root.get_node_or_null(TRIGGERS_PATH)
	if parent == null:
		parent = root
	var map_id := EntityIds.map_id_of(root)
	var number := EntityIds.next_number(existing_ids(root), map_id, "trigger")
	var entity_id := EntityIds.make_id(map_id, "trigger", number)
	var diamond := diamond_of(root)
	var world := snap_position(world_position, step) if diamond == Vector2i.ZERO else snap_to_diamond(root, world_position, step)
	var local := world
	if parent is Node2D and (parent as Node2D).is_inside_tree():
		local = (parent as Node2D).to_local(world)
	var out := {
		"parent": parent, "position": local, "entity_id": entity_id, "on_interact": on_interact,
		"sequence_path": "%s/%s.tres" % [sequences_dir, entity_id], "size": Vector2(tile, tile),
	}
	if diamond != Vector2i.ZERO:
		out["diamond"] = diamond
	return out

## The trigger area of a plan, not yet in the map: an RpgTriggerArea with a one-tile rectangle,
## or with the diamond of its cell (RpgIso.cell_shape, the shape the builder gives a cell).
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
	if plan.has("diamond"):
		var diamond: Vector2i = plan["diamond"]
		shape.shape = RpgIso.cell_shape(diamond)
		area.add_child(shape)
		return area
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
## changed. On an isometric map the zone with nothing selected is the outline of 6x6 diamonds
## around the cell under `centre`; the rectangle around selected nodes is a rectangle of the
## screen there too (`tile` is then one step on the diamonds).
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
	if layer == null and points.is_empty() and diamond_of(root) != Vector2i.ZERO:
		@warning_ignore("integer_division")
		var first := RpgIso.cell_at(root, centre) - Vector2i(ZONE_DEFAULT_TILES / 2, ZONE_DEFAULT_TILES / 2)
		for corner in cells_outline(root, Rect2i(first, Vector2i(ZONE_DEFAULT_TILES, ZONE_DEFAULT_TILES))):
			polygon.append((corner - origin).snapped(Vector2(1, 1)))
	elif layer == null:
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
## selected gate a new switch opens, or null)}. Nothing is changed. On an isometric map the
## position is the middle of the diamond under the point and the plan has `diamond`: a gate
## closes its diamond, as the builder's does (builder/lib/world_plan.gd `add_gate`); a switch
## keeps the square it makes for itself.
static func plan_lock(root: Node, world_position: Vector2, tile: int, kind: String, selected: Node = null) -> Dictionary:
	var parent: Node = ysort_parent(root)
	if parent == null:
		parent = root
	var id_kind := "gate" if kind == "gate" else "switch"
	var map_id := EntityIds.map_id_of(root)
	var number := EntityIds.next_number(existing_ids(root), map_id, id_kind)
	var diamond := diamond_of(root)
	var world := snap_position(world_position, tile) if diamond == Vector2i.ZERO else snap_to_diamond(root, world_position, tile)
	var local := world
	if parent is Node2D and (parent as Node2D).is_inside_tree():
		local = (parent as Node2D).to_local(world)
	var gate: Node = null
	if kind != "gate" and selected != null:
		var script: Script = selected.get_script()
		if script != null and script.resource_path == GATE_SCRIPT:
			gate = selected
	var t := float(tile)
	var out := {
		"parent": parent, "position": local, "entity_id": EntityIds.make_id(map_id, id_kind, number),
		"kind": kind, "size": Vector2(t, t) if kind == "gate" else Vector2(t, t) * 0.75, "gate": gate,
	}
	if diamond != Vector2i.ZERO:
		out["diamond"] = diamond
	return out

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
	if kind == "gate" and plan.has("diamond"):
		# a gate makes a rectangle of `size` only when it has no shape of its own
		var diamond: Vector2i = plan["diamond"]
		var shape := CollisionShape2D.new()
		shape.name = "Shape"
		shape.shape = RpgIso.cell_shape(diamond)
		node.add_child(shape)
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
	for child in node.get_children():  # the diamond of a gate on an isometric map; else none
		undo.add_do_method(child, "set_owner", root)
	undo.add_do_reference(node)
	undo.add_undo_method(parent, "remove_child", node)
	if gate != null:
		undo.add_do_property(gate, "open_when", switch_condition(JsonIo.to_str(plan["entity_id"])))
		undo.add_undo_property(gate, "open_when", gate.get("open_when"))
	undo.commit_action()
	return node
