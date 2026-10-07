extends RefCounted
## Builds small map scenes for the editor-tool tests (M8): a map root, entities with and without
## ids, doors and spawn points, saved under user://.

const SceneUtil := preload("res://builder/lib/scene_util.gd")

const MAP_ROOT := "res://addons/rpg_runtime/world/map_root.gd"
const WORLD_OBJECT := "res://addons/rpg_runtime/world/world_object.gd"
const PERSISTENT := "res://addons/rpg_runtime/world/persistent.gd"
const DOOR := "res://addons/rpg_runtime/world/door.gd"
const SPAWN := "res://addons/rpg_runtime/world/spawn_point.gd"

## A map root with YSorted/Entities, not yet saved.
static func map(map_id: String, root_name: String = "Map") -> Node2D:
	var root := Node2D.new()
	root.name = root_name
	root.set_script(load(MAP_ROOT))
	root.set("map_id", StringName(map_id))
	var ysorted := Node2D.new()
	ysorted.name = "YSorted"
	ysorted.y_sort_enabled = true
	root.add_child(ysorted)
	var entities := Node2D.new()
	entities.name = "Entities"
	entities.y_sort_enabled = true
	ysorted.add_child(entities)
	return root

static func entities_of(root: Node) -> Node:
	return root.get_node("YSorted/Entities")

## An entity under `parent`: a world object with the given id; `persistent` adds an RpgPersistent child.
static func entity(parent: Node, node_name: String, id: String, persistent: bool = true, position: Vector2 = Vector2.ZERO) -> Node2D:
	var node := Node2D.new()
	node.name = node_name
	node.set_script(load(WORLD_OBJECT))
	node.set("entity_id", id)
	node.position = position
	parent.add_child(node)
	if persistent:
		var p := Node.new()
		p.name = "Persistent"
		p.set_script(load(PERSISTENT))
		node.add_child(p)
	return node

static func door(parent: Node, node_name: String, target_map: String, target_spawn: String = "default") -> Area2D:
	var node := Area2D.new()
	node.name = node_name
	node.set_script(load(DOOR))
	node.set("target_map", target_map)
	node.set("target_spawn", StringName(target_spawn))
	parent.add_child(node)
	return node

static func spawn(parent: Node, node_name: String, spawn_id: String) -> Marker2D:
	var node := Marker2D.new()
	node.name = node_name
	node.set_script(load(SPAWN))
	node.set("spawn_id", StringName(spawn_id))
	parent.add_child(node)
	return node

## Saves the tree (the root is freed) and returns the Error code.
static func save(root: Node, path: String) -> int:
	return SceneUtil.save_scene(root, path)

static func remove_tree(dir_path: String) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		remove_tree(dir_path + "/" + sub)
	for f in dir.get_files():
		DirAccess.remove_absolute(dir_path + "/" + f)
	DirAccess.remove_absolute(dir_path)
