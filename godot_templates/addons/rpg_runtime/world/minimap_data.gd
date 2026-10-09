class_name RpgMinimapData
extends RefCounted
## The minimap of a map (T12.64): one pixel per cell, the average colour of the cell's tile, made
## by the builder's minimap recipe from the map's TileMapLayers and saved as an ImageTexture in
## res://generated/minimaps/<key>.tres. The texture's metadata says where it sits:
## "origin_cell" (Vector2i, the map cell of pixel 0,0) and "tile_size" (Vector2i).

const DIR := "res://generated/minimaps/"

## The key of a map scene: its project path without "res://" and ".tscn", "/" made "__"
## (".../maps/imported/pack/cave.tscn" -> "game__maps__imported__pack__cave").
static func key_for(scene_path: String) -> String:
	return scene_path.trim_prefix("res://").trim_suffix(".tscn").replace("/", "__")

static func path_for(map_key: String) -> String:
	return DIR + map_key + ".tres"

## The minimap texture of a map key, or null.
static func load_texture(map_key: String) -> Texture2D:
	var path := path_for(map_key)
	return load(path) as Texture2D if ResourceLoader.exists(path) else null

static func origin_of(texture: Texture2D) -> Vector2i:
	if texture == null:
		return Vector2i.ZERO
	var origin: Vector2i = texture.get_meta("origin_cell", Vector2i.ZERO)
	return origin

static func tile_of(texture: Texture2D) -> Vector2i:
	if texture == null:
		return Vector2i(16, 16)
	var tile: Vector2i = texture.get_meta("tile_size", Vector2i(16, 16))
	return tile

## The minimap pixel (cell from the origin) of a map-local position.
static func cell_at(texture: Texture2D, local_position: Vector2) -> Vector2i:
	var tile := tile_of(texture)
	var cell := Vector2i(floori(local_position.x / maxf(tile.x, 1.0)), floori(local_position.y / maxf(tile.y, 1.0)))
	return cell - origin_of(texture)

## What the minimap marks in `map`: doors, unopened chests and the entities quest stages point
## at. [{kind: "door" | "chest" | "quest", position: map-local Vector2}].
static func markers(map: Node, quest_targets: Array[String]) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	_collect(map, map, quest_targets, out)
	return out

static func _collect(map: Node, node: Node, targets: Array[String], out: Array[Dictionary]) -> void:
	for child in node.get_children():
		if child is Node2D:
			var spot: Node2D = child
			var at := (map as Node2D).to_local(spot.global_position) if map is Node2D else spot.position
			var entity := str(child.get("entity_id")) if "entity_id" in child else ""
			if entity != "" and targets.has(entity):
				out.append({"kind": "quest", "position": at})
			elif child is RpgDoor:
				out.append({"kind": "door", "position": at})
			elif child is RpgChest and not (child as RpgChest).opened:
				out.append({"kind": "chest", "position": at})
		_collect(map, child, targets, out)
