extends SceneTree
# Probe: editor, terrain and tile animation APIs used by M8 (T8.01, T8.03, T8.05, T8.06, T8.07).
# Run: godot --headless --path godot_templates --script res://tests/probes/probe_m8_api.gd

func _has(cls: String, method: String) -> void:
	print("PROBE %s.%s: %s" % [cls, method, str(ClassDB.class_has_method(cls, method))])

func _has_signal(cls: String, sig: String) -> void:
	print("PROBE signal %s.%s: %s" % [cls, sig, str(ClassDB.class_has_signal(cls, sig))])

func _initialize() -> void:
	for m in ["add_control_to_dock", "remove_control_from_docks", "add_dock", "remove_dock", "get_undo_redo"]:
		_has("EditorPlugin", m)
	print("PROBE class EditorDock exists: ", ClassDB.class_exists("EditorDock"))
	if ClassDB.class_exists("EditorDock"):
		for p in ClassDB.class_get_property_list("EditorDock", true):
			print("PROBE EditorDock prop: ", p["name"])
		for m in ClassDB.class_get_method_list("EditorDock", true):
			print("PROBE EditorDock method: ", m["name"])
		for c in ClassDB.class_get_enum_constants("EditorDock", "DockSlot"):
			print("PROBE EditorDock slot: ", c, " = ", ClassDB.class_get_integer_constant("EditorDock", c))
	for m in ["get_editor_viewport_2d", "save_all_scenes", "get_resource_filesystem", "get_selection", "get_edited_scene_root", "open_scene_from_path", "get_editor_settings", "get_open_scenes", "mark_scene_as_unsaved", "get_base_control", "get_editor_undo_redo", "reload_scene_from_path"]:
		_has("EditorInterface", m)
	for m in ["scan", "scan_sources", "update_file", "get_file_type", "is_scanning", "get_filesystem_path"]:
		_has("EditorFileSystem", m)
	for s in ["filesystem_changed", "resources_reload"]:
		_has_signal("EditorFileSystem", s)
	for m in ["create_action", "add_do_method", "add_undo_method", "add_do_property", "add_undo_property", "add_do_reference", "add_undo_reference", "commit_action"]:
		_has("EditorUndoRedoManager", m)
	for m in ["get_selected_nodes", "add_node", "clear", "remove_node"]:
		_has("EditorSelection", m)
	_has_signal("EditorSelection", "selection_changed")
	for m in ["has_setting", "get_setting", "set_setting", "add_property_info"]:
		_has("EditorSettings", m)
	print("PROBE OS.execute args ok: ", ClassDB.class_has_method("OS", "execute"))
	print("PROBE OS.get_executable_path: ", OS.get_executable_path())
	# Terrain
	for c in ["CELL_NEIGHBOR_RIGHT_SIDE", "CELL_NEIGHBOR_RIGHT_CORNER", "CELL_NEIGHBOR_BOTTOM_RIGHT_SIDE", "CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER", "CELL_NEIGHBOR_BOTTOM_SIDE", "CELL_NEIGHBOR_BOTTOM_CORNER", "CELL_NEIGHBOR_BOTTOM_LEFT_SIDE", "CELL_NEIGHBOR_BOTTOM_LEFT_CORNER", "CELL_NEIGHBOR_LEFT_SIDE", "CELL_NEIGHBOR_LEFT_CORNER", "CELL_NEIGHBOR_TOP_LEFT_SIDE", "CELL_NEIGHBOR_TOP_LEFT_CORNER", "CELL_NEIGHBOR_TOP_SIDE", "CELL_NEIGHBOR_TOP_CORNER", "CELL_NEIGHBOR_TOP_RIGHT_SIDE", "CELL_NEIGHBOR_TOP_RIGHT_CORNER"]:
		print("PROBE TileSet.%s: %s" % [c, str(ClassDB.class_get_integer_constant("TileSet", c))])
	for c in ["TERRAIN_MODE_MATCH_CORNERS_AND_SIDES", "TERRAIN_MODE_MATCH_CORNERS", "TERRAIN_MODE_MATCH_SIDES"]:
		print("PROBE TileSet.%s: %s" % [c, str(ClassDB.class_get_integer_constant("TileSet", c))])
	for m in ["add_terrain_set", "set_terrain_set_mode", "add_terrain", "set_terrain_name", "set_terrain_color", "get_terrain_sets_count", "get_terrains_count", "get_terrain_name"]:
		_has("TileSet", m)
	for m in ["set_terrain_peering_bit", "get_terrain_peering_bit", "set_terrain_set", "set_terrain", "is_valid_terrain_peering_bit"]:
		_has("TileData", m)
	for m in ["set_tile_animation_columns", "set_tile_animation_frames_count", "set_tile_animation_frame_duration", "set_tile_animation_separation", "set_tile_animation_speed", "set_tile_animation_mode", "get_tile_animation_frames_count"]:
		_has("TileSetAtlasSource", m)

	# Behaviour: terrain set with corners-and-sides, peering bits on a tile.
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_terrain_set()
	ts.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
	ts.add_terrain(0)
	ts.set_terrain_name(0, 0, "grass")
	ts.set_terrain_color(0, 0, Color("#4caf50"))
	var img := Image.create(64, 16, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 0, 0, 1))
	var src := TileSetAtlasSource.new()
	ts.add_source(src, 0)
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(16, 16)
	for x in 4:
		src.create_tile(Vector2i(x, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	td.terrain_set = 0
	td.terrain = 0
	print("PROBE bit valid right side: ", td.is_valid_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_SIDE))
	print("PROBE bit valid right corner: ", td.is_valid_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_CORNER))
	td.set_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_SIDE, 0)
	print("PROBE peering right: ", td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_SIDE))
	print("PROBE terrain_set / terrain: ", td.terrain_set, " ", td.terrain)
	# Animation: 4 columns in a horizontal run starting at (0, 0).
	src.set_tile_animation_columns(Vector2i(0, 0), 4)
	src.set_tile_animation_frames_count(Vector2i(0, 0), 4)
	for i in 4:
		src.set_tile_animation_frame_duration(Vector2i(0, 0), i, 0.1 * (i + 1))
	print("PROBE anim frames: ", src.get_tile_animation_frames_count(Vector2i(0, 0)), " duration[2]=", src.get_tile_animation_frame_duration(Vector2i(0, 0), 2))
	quit(0)
