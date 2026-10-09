extends SceneTree
# Probe: APIs of the metroidvania archetype (T14.03 the one-way physics layer and the bool custom
# data of a TileSet; T14.06 Parallax2D; CharacterBody2D helpers of the platform actor).

func _initialize() -> void:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_physics_layer()
	ts.add_physics_layer()
	ts.set_physics_layer_collision_layer(1, 1 << 10)
	ts.set_physics_layer_collision_mask(1, 0)
	print("PROBE physics_layers: ", ts.get_physics_layers_count(), " layer1_bits=", ts.get_physics_layer_collision_layer(1))
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(0, "ladder")
	ts.set_custom_data_layer_type(0, TYPE_BOOL)
	print("PROBE custom_layer_by_name: ", ts.get_custom_data_layer_by_name("ladder"), " missing=", ts.get_custom_data_layer_by_name("nope"))
	var img := Image.create(16, 16, false, Image.FORMAT_RGBA8)
	img.fill(Color.RED)
	var src := TileSetAtlasSource.new()
	ts.add_source(src, 0)
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(16, 16)
	src.create_tile(Vector2i(0, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	td.add_collision_polygon(1)
	td.set_collision_polygon_points(1, 0, PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, -3), Vector2(-8, -3)]))
	print("PROBE one_way_default: ", td.is_collision_polygon_one_way(1, 0))
	td.set_collision_polygon_one_way(1, 0, true)
	print("PROBE one_way_set: ", td.is_collision_polygon_one_way(1, 0), " margin=", td.get_collision_polygon_one_way_margin(1, 0))
	print("PROBE polygons_layer0: ", td.get_collision_polygons_count(0), " layer1: ", td.get_collision_polygons_count(1))
	td.set_custom_data("ladder", true)
	print("PROBE custom_bool: ", td.get_custom_data("ladder"), " has=", td.has_custom_data("ladder"))
	# the one-way flag and the custom data survive a save
	var path := "user://probe_m14_tileset.tres"
	print("PROBE save: ", ResourceSaver.save(ts, path))
	var again := ResourceLoader.load(path, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet
	var td2 := (again.get_source(0) as TileSetAtlasSource).get_tile_data(Vector2i(0, 0), 0)
	print("PROBE reloaded_one_way: ", td2.is_collision_polygon_one_way(1, 0), " ladder=", td2.get_custom_data("ladder"))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	# a layer: tile data of a painted cell, erase
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	layer.set_cell(Vector2i(2, 3), 0, Vector2i(0, 0))
	print("PROBE cell_tile_data: ", layer.get_cell_tile_data(Vector2i(2, 3)) != null, " empty=", layer.get_cell_tile_data(Vector2i(0, 0)))
	layer.erase_cell(Vector2i(2, 3))
	print("PROBE erased: ", layer.get_cell_source_id(Vector2i(2, 3)))
	layer.free()
	# Parallax2D (4.3+)
	print("PROBE parallax2d_exists: ", ClassDB.class_exists("Parallax2D"))
	var parallax := Parallax2D.new()
	parallax.scroll_scale = Vector2(0.5, 1.0)
	parallax.repeat_size = Vector2(320, 0)
	parallax.repeat_times = 3
	print("PROBE parallax2d: scale=", parallax.scroll_scale, " repeat=", parallax.repeat_size, " times=", parallax.repeat_times, " follow=", parallax.follow_viewport)
	parallax.free()
	# CharacterBody2D
	var body := CharacterBody2D.new()
	body.motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
	body.floor_snap_length = 3.0
	print("PROBE body: on_wall_only=", body.is_on_wall_only(), " wall_normal=", body.get_wall_normal(), " snap=", body.floor_snap_length)
	body.set_collision_mask_value(11, true)
	print("PROBE mask_bit_11: ", body.collision_mask)
	body.free()
	var cam := Camera2D.new()
	cam.position_smoothing_enabled = true
	cam.limit_left = -10
	print("PROBE camera: smoothing=", cam.position_smoothing_enabled, " limit_left=", cam.limit_left)
	cam.free()
	quit(0)
