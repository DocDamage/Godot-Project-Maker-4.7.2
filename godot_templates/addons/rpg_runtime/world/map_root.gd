class_name RpgMapRoot
extends Node2D
## Script of every map's root node.

@export var map_id: StringName = &""
@export var music_asset_id: String = ""
## The name shown on a save slot: a translation key. Empty means "MAP_<ID>" from `map_id`.
@export var display_name: String = ""

## The translation key of this map's name ("MAP_STARTER_MAP" for the map `starter_map`).
func name_key() -> String:
	if display_name != "":
		return display_name
	var id := str(map_id) if str(map_id) != "" else scene_file_path.get_file().get_basename()
	return "MAP_" + id.to_upper()

## The spawn with this id; else "default"; else the first spawn in the map; else null.
func get_spawn(spawn_id: StringName) -> RpgSpawnPoint:
	var spawns: Array[RpgSpawnPoint] = []
	_collect_spawns(self, spawns)
	for spawn in spawns:
		if spawn.spawn_id == spawn_id:
			return spawn
	for spawn in spawns:
		if spawn.spawn_id == &"default":
			return spawn
	return spawns[0] if spawns.size() > 0 else null

func _collect_spawns(node: Node, out: Array[RpgSpawnPoint]) -> void:
	for child in node.get_children():
		if child is RpgSpawnPoint:
			out.append(child)
		_collect_spawns(child, out)

## The first node of group "player" inside this map, or null.
func get_player() -> Node2D:
	for node in get_tree().get_nodes_in_group("player"):
		if node is Node2D and is_ancestor_of(node):
			return node
	return null

## Union of every TileMapLayer's used rectangle, in pixels (map-local), or an empty Rect2.
func used_rect_px() -> Rect2:
	var result := Rect2()
	var first := true
	for layer in _collect_layers(self):
		if layer.tile_set == null:
			continue
		var cells := layer.get_used_rect()
		if cells.size == Vector2i.ZERO:
			continue
		var tile := Vector2(layer.tile_set.tile_size)
		var rect := Rect2(Vector2(cells.position) * tile, Vector2(cells.size) * tile)
		rect.position += layer.position
		result = rect if first else result.merge(rect)
		first = false
	return result

func _collect_layers(node: Node) -> Array[TileMapLayer]:
	var layers: Array[TileMapLayer] = []
	for child in node.get_children():
		if child is TileMapLayer:
			layers.append(child)
		layers.append_array(_collect_layers(child))
	return layers
