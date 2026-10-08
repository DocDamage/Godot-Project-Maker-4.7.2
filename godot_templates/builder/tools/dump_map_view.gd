extends SceneTree
# Dumps what a picture of one map needs: its painted cells, the tile sources they come from and the
# pictures of the entities placed in it (T11.27). Headless Godot has no renderer, so rpggen draws
# the picture itself from this file.
# Run: godot --headless --path <proj> --script res://generated/builder/tools/dump_map_view.gd -- --map=res://game/maps/starter_map.tscn --out=<file>
# Output: {map, tile_size, sources: {id: {path, region_size, margins, separation}},
#          layers: [{name, z, cells: [[x, y, source_id, atlas_x, atlas_y], ...]}],
#          entities: [{name, scene, entity_id, x, y, sprite: {path, region, offset}}]}

func _initialize() -> void:
	var map_path := "res://game/maps/starter_map.tscn"
	var out_path := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
		elif arg.begins_with("--map="):
			map_path = arg.trim_prefix("--map=")
	var packed := ResourceLoader.load(map_path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	if packed == null:
		push_error("cannot load %s" % map_path)
		quit(1)
		return
	var root := packed.instantiate()
	var view := {"map": map_path, "tile_size": [16, 16], "sources": {}, "layers": [], "entities": []}
	_collect(root, root, view)
	root.free()
	var text := JSON.stringify(view, "  ", true) + "\n"
	if out_path == "":
		print(text)
	else:
		DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
		var f := FileAccess.open(out_path, FileAccess.WRITE)
		if f == null:
			push_error("cannot write %s" % out_path)
			quit(1)
			return
		f.store_string(text)
		f.close()
	quit(0)

func _collect(root: Node, node: Node, view: Dictionary) -> void:
	if node is TileMapLayer:
		_add_layer(node as TileMapLayer, view)
	elif node is Node2D and node != root and node.scene_file_path != "":
		var entities: Array = view["entities"]
		entities.append(_entity(root, node as Node2D))
		return  # what is inside an instanced scene belongs to it
	for child in node.get_children():
		_collect(root, child, view)

func _add_layer(layer: TileMapLayer, view: Dictionary) -> void:
	var cells: Array = []
	for c in layer.get_used_cells():
		var atlas := layer.get_cell_atlas_coords(c)
		cells.append([c.x, c.y, layer.get_cell_source_id(c), atlas.x, atlas.y])
	cells.sort_custom(func(a: Array, b: Array) -> bool:
		for i in a.size():
			if a[i] != b[i]:
				return a[i] < b[i]
		return false)
	var layers: Array = view["layers"]
	layers.append({"name": String(layer.name), "z": layer.z_index, "cells": cells})
	var tile_set := layer.tile_set
	if tile_set == null:
		return
	view["tile_size"] = [tile_set.tile_size.x, tile_set.tile_size.y]
	for i in tile_set.get_source_count():
		var id := tile_set.get_source_id(i)
		var key := str(id)
		var known_sources: Dictionary = view["sources"]
		if known_sources.has(key):
			continue
		var source := tile_set.get_source(id) as TileSetAtlasSource
		if source == null or source.texture == null:
			continue
		view["sources"][key] = {
			"path": source.texture.resource_path,
			"region_size": [source.texture_region_size.x, source.texture_region_size.y],
			"margins": [source.margins.x, source.margins.y],
			"separation": [source.separation.x, source.separation.y],
		}

## The sum of the positions up to the map root (no rotation or scale is assumed).
func _position_in(root: Node, node: Node2D) -> Vector2:
	var pos := Vector2.ZERO
	var current: Node = node
	while current != null and current != root:
		if current is Node2D:
			pos += (current as Node2D).position
		current = current.get_parent()
	return pos

func _entity(root: Node, node: Node2D) -> Dictionary:
	var pos := _position_in(root, node)
	var id: Variant = node.get("entity_id")
	return {
		"name": String(node.name),
		"scene": node.scene_file_path,
		"entity_id": str(id) if id != null else "",
		"x": pos.x,
		"y": pos.y,
		"sprite": _sprite_of(node),
	}

## The first picture an entity shows: {path, region, offset} or {}.
func _sprite_of(node: Node) -> Dictionary:
	for child in node.get_children():
		var tex: Texture2D = null
		var offset := Vector2.ZERO
		if child is Sprite2D and (child as Sprite2D).texture != null:
			var sprite := child as Sprite2D
			tex = sprite.texture
			offset = sprite.position + sprite.offset
			if sprite.centered and tex != null:
				offset -= tex.get_size() / 2.0
		elif child is AnimatedSprite2D and (child as AnimatedSprite2D).sprite_frames != null:
			var animated := child as AnimatedSprite2D
			var names := animated.sprite_frames.get_animation_names()
			var wanted := "idle_down" if animated.sprite_frames.has_animation("idle_down") else (String(names[0]) if names.size() > 0 else "")
			if wanted != "" and animated.sprite_frames.get_frame_count(wanted) > 0:
				tex = animated.sprite_frames.get_frame_texture(wanted, 0)
				offset = animated.position + animated.offset
				if animated.centered and tex != null:
					offset -= tex.get_size() / 2.0
		if tex == null:
			continue
		if tex is AtlasTexture and (tex as AtlasTexture).atlas != null:
			var at := tex as AtlasTexture
			return {"path": at.atlas.resource_path, "region": [at.region.position.x, at.region.position.y, at.region.size.x, at.region.size.y], "offset": [offset.x, offset.y]}
		if tex.resource_path != "":
			return {"path": tex.resource_path, "region": [0, 0, tex.get_width(), tex.get_height()], "offset": [offset.x, offset.y]}
	return {}
