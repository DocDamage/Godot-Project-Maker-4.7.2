extends SceneTree

const JsonUtil := preload("../lib/json_util.gd")
# Dumps every painted tile of every map under res://game/maps as sorted tuples, so a test can
# compare the cells before and after a regeneration (the tile invariant, M5).
# Run: godot --headless --path <proj> --script res://generated/builder/tools/dump_map_cells.gd -- --out=<file>
# Output: {map_path: {layer_path: [[x, y, source_id, atlas_x, atlas_y, alternative], ...]}}

const MAPS_DIR := "res://game/maps"

func _initialize() -> void:
	var out_path := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out_path = arg.trim_prefix("--out=")
	var result := {}
	for map_path in _list_scenes(MAPS_DIR):
		var packed := ResourceLoader.load(map_path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
		if packed == null:
			push_error("cannot load %s" % map_path)
			quit(1)
			return
		var root := packed.instantiate()
		var layers := {}
		_collect(root, root, layers)
		result[map_path] = layers
		root.free()
	var text := JSON.stringify(result, "  ", true) + "\n"
	if out_path == "":
		print(text)
	else:
		var f := FileAccess.open(out_path, FileAccess.WRITE)
		if f == null:
			push_error("cannot write %s" % out_path)
			quit(1)
			return
		f.store_string(text)
		f.close()
	quit(0)

func _collect(root: Node, node: Node, layers: Dictionary) -> void:
	if node is TileMapLayer:
		var layer := node as TileMapLayer
		var cells: Array = []
		for c in layer.get_used_cells():
			var atlas := layer.get_cell_atlas_coords(c)
			cells.append([c.x, c.y, layer.get_cell_source_id(c), atlas.x, atlas.y, layer.get_cell_alternative_tile(c)])
		cells.sort_custom(func(a: Array, b: Array) -> bool:
			for i in a.size():
				if a[i] != b[i]:
					return a[i] < b[i]
			return false)
		layers[str(root.get_path_to(layer))] = cells
	for child in node.get_children():
		_collect(root, child, layers)

func _list_scenes(dir_path: String) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	var names: Array[Array] = []
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		names.append([name, dir.current_is_dir()])
		name = dir.get_next()
	dir.list_dir_end()
	names.sort()
	for e: Array in names:
		var entry_name: String = e[0]
		var is_dir: bool = e[1]
		var full: String = dir_path + "/" + entry_name
		if is_dir:
			found.append_array(_list_scenes(full))
		elif entry_name.ends_with(".tscn"):
			found.append(full)
	return found
