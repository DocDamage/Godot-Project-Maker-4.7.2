extends SceneTree
# Probe: TileSet / TileSetAtlasSource / TileData / Image / BitMap APIs used by tileset_recipe.

func _initialize() -> void:
	var img := Image.create(32, 16, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	img.fill_rect(Rect2i(0, 0, 16, 16), Color(1, 0, 0, 1))
	var tex := ImageTexture.create_from_image(img)

	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	print("PROBE physics_layers_count: ", ts.get_physics_layers_count())
	while ts.get_physics_layers_count() < 1:
		ts.add_physics_layer()
	ts.set_physics_layer_collision_layer(0, 1)
	ts.set_physics_layer_collision_mask(0, 0)
	print("PROBE physics_layer_values: ", ts.get_physics_layer_collision_layer(0), " ", ts.get_physics_layer_collision_mask(0))

	print("PROBE custom_data_by_name_missing: ", ts.get_custom_data_layer_by_name("asset_id"))
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(0, "asset_id")
	ts.set_custom_data_layer_type(0, TYPE_STRING)
	print("PROBE custom_data_by_name_found: ", ts.get_custom_data_layer_by_name("asset_id"))

	var src := TileSetAtlasSource.new()
	var sid := ts.add_source(src, 3)
	print("PROBE add_source_explicit_id: ", sid, " has_source(3)=", ts.has_source(3))
	src.texture = tex
	src.texture_region_size = Vector2i(16, 16)
	src.margins = Vector2i(0, 0)
	src.separation = Vector2i(0, 0)
	print("PROBE grid_size: ", src.get_atlas_grid_size())

	var cell0 := img.get_region(Rect2i(0, 0, 16, 16))
	var cell1 := img.get_region(Rect2i(16, 0, 16, 16))
	print("PROBE is_invisible: opaque=", cell0.is_invisible(), " transparent=", cell1.is_invisible())

	src.create_tile(Vector2i(0, 0))
	print("PROBE has_tile: ", src.has_tile(Vector2i(0, 0)), " ", src.has_tile(Vector2i(1, 0)))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	td.add_collision_polygon(0)
	td.set_collision_polygon_points(0, 0, PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, 8), Vector2(-8, 8)]))
	print("PROBE collision_polygons_count: ", td.get_collision_polygons_count(0))
	td.remove_collision_polygon(0, 0)
	print("PROBE collision_polygons_after_remove: ", td.get_collision_polygons_count(0))
	td.set_custom_data("asset_id", "pack.sheet")
	print("PROBE custom_data_value: ", td.get_custom_data("asset_id"))

	var bm := BitMap.new()
	bm.create_from_image_alpha(cell0, 0.5)
	var polys := bm.opaque_to_polygons(Rect2i(0, 0, 16, 16), 1.0)
	print("PROBE bitmap_polygons: ", polys.size(), " first_points=", polys[0].size() if polys.size() > 0 else -1)

	var err := ResourceSaver.save(ts, "user://probe_ts.tres")
	print("PROBE resource_saver_save: ", err)
	var loaded := load("user://probe_ts.tres") as TileSet
	print("PROBE reload: sources=", loaded.get_source_count(), " has_source3=", loaded.has_source(3),
		" tile_size=", loaded.tile_size)
	DirAccess.remove_absolute("user://probe_ts.tres")
	quit(0)
