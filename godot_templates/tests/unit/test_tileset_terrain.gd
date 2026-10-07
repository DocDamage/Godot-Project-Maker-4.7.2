extends RefCounted
## Terrain assignments and animated tiles of tileset_recipe (T8.06, T8.07).

const Recipe := preload("res://builder/recipes/tileset_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

func _sets() -> Array:
	return [
		{"name": "ground", "mode": "corners_and_sides", "terrains": [{"name": "grass", "color": "#4caf50"}, {"name": "dirt", "color": "#8d6e63"}]},
		{"name": "shore", "mode": "corners", "terrains": [{"name": "sand", "color": "#f4e04d"}]},
	]

func _tileset(size: int = 16, cols: int = 6) -> Array:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(size, size)
	var img := Image.create(size * cols, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 0, 0, 1))
	var src := TileSetAtlasSource.new()
	ts.add_source(src, 0)
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(size, size)
	return [ts, src]

func test_terrain_sets_are_added_with_modes_names_and_colors(t) -> void:
	var ts := TileSet.new()
	Recipe.ensure_terrain_sets(ts, _sets())
	t.eq(ts.get_terrain_sets_count(), 2)
	t.eq(ts.get_terrain_set_mode(0), TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
	t.eq(ts.get_terrain_set_mode(1), TileSet.TERRAIN_MODE_MATCH_CORNERS)
	t.eq(ts.get_terrains_count(0), 2)
	t.eq(ts.get_terrain_name(0, 1), "dirt")
	t.eq(ts.get_terrain_color(0, 0), Color("#4caf50"))

func test_existing_terrain_sets_are_never_changed(t) -> void:
	var ts := TileSet.new()
	ts.add_terrain_set()
	ts.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_SIDES)
	ts.add_terrain(0)
	ts.set_terrain_name(0, 0, "mine")
	Recipe.ensure_terrain_sets(ts, _sets())
	t.eq(ts.get_terrain_set_mode(0), TileSet.TERRAIN_MODE_MATCH_SIDES, "the user's mode stays")
	t.eq(ts.get_terrain_name(0, 0), "mine")
	t.eq(ts.get_terrains_count(0), 2, "missing terrains are appended")
	t.eq(ts.get_terrain_sets_count(), 2)
	Recipe.ensure_terrain_sets(ts, _sets())
	t.eq(ts.get_terrains_count(0), 2, "a second run adds nothing")

func test_peering_bits_follow_the_catalog_keys(t) -> void:
	var made := _tileset()
	var ts: TileSet = made[0]
	var src: TileSetAtlasSource = made[1]
	Recipe.ensure_terrain_sets(ts, _sets())
	src.create_tile(Vector2i(0, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	var peering := {"right_side": 0, "bottom_right_corner": 0, "bottom_side": 1, "bottom_left_corner": -1, "left_side": -1, "top_left_corner": -1, "top_side": -1, "top_right_corner": 1}
	t.ok(Recipe.apply_terrain(td, ts, _sets(), {"set": "ground", "terrain": 0, "peering": peering}))
	t.eq(td.terrain_set, 0)
	t.eq(td.terrain, 0)
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_SIDE), 0)
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER), 0)
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_BOTTOM_SIDE), 1)
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER), 1)
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_LEFT_SIDE), -1)

func test_a_corners_set_ignores_side_bits(t) -> void:
	var made := _tileset()
	var ts: TileSet = made[0]
	var src: TileSetAtlasSource = made[1]
	Recipe.ensure_terrain_sets(ts, _sets())
	src.create_tile(Vector2i(1, 0))
	var td := src.get_tile_data(Vector2i(1, 0), 0)
	Recipe.apply_terrain(td, ts, _sets(), {"set": "shore", "terrain": 0, "peering": {"right_side": 0, "top_left_corner": 0}})
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER), 0)
	t.ok(not td.is_valid_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_SIDE), "a side bit is not valid in a corners set")

func test_an_unknown_set_leaves_the_tile_alone(t) -> void:
	var made := _tileset()
	var ts: TileSet = made[0]
	var src: TileSetAtlasSource = made[1]
	src.create_tile(Vector2i(0, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	t.ok(not Recipe.apply_terrain(td, ts, _sets(), {"set": "nope", "terrain": 0, "peering": {}}))
	t.eq(td.terrain_set, -1)

func test_a_tile_without_any_terrain_color_keeps_terrain_minus_one(t) -> void:
	var made := _tileset()
	var ts: TileSet = made[0]
	var src: TileSetAtlasSource = made[1]
	Recipe.ensure_terrain_sets(ts, _sets())
	src.create_tile(Vector2i(0, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	Recipe.apply_terrain(td, ts, _sets(), {"set": "ground", "terrain": -1, "peering": {}})
	t.eq(td.terrain, -1)

func test_terrain_set_index(t) -> void:
	t.eq(Recipe.terrain_set_index(_sets(), "shore"), 1)
	t.eq(Recipe.terrain_set_index(_sets(), "missing"), -1)

func test_animation_runs_must_be_horizontal_and_start_at_the_tile(t) -> void:
	var good := {"frames": [[2, 1], [3, 1], [4, 1]]}
	t.eq(Recipe.animation_run(Vector2i(2, 1), good).size(), 3)
	t.eq(Recipe.animation_run(Vector2i(1, 1), good), [], "the first frame is not the tile")
	t.eq(Recipe.animation_run(Vector2i(2, 1), {"frames": [[2, 1], [4, 1]]}), [], "a gap")
	t.eq(Recipe.animation_run(Vector2i(2, 1), {"frames": [[2, 1], [3, 2]]}), [], "another row")
	t.eq(Recipe.animation_run(Vector2i(2, 1), {"frames": [[2, 1]]}), [], "one frame is no animation")
	t.eq(Recipe.animation_run(Vector2i(2, 1), {"frames": [[3, 1], [2, 1]]}), [], "reversed")

func test_an_animated_tile_gets_frames_and_durations(t) -> void:
	var made := _tileset()
	var src: TileSetAtlasSource = made[1]
	src.create_tile(Vector2i(0, 0))
	var recipe := Recipe.new()
	var ctx := BuildContext.new("res://builder", "build")
	var issues: Array = []
	recipe._apply_animation(ctx, src, Vector2i(0, 0), {"count": 3, "durations_ms": [100, 200]}, {"id": "p.a", "path": "x.png"}, issues)
	t.eq(issues, [])
	t.eq(src.get_tile_animation_frames_count(Vector2i(0, 0)), 3)
	t.near(src.get_tile_animation_frame_duration(Vector2i(0, 0), 0), 0.1)
	t.near(src.get_tile_animation_frame_duration(Vector2i(0, 0), 1), 0.2)
	t.near(src.get_tile_animation_frame_duration(Vector2i(0, 0), 2), 0.1, 0.001)
	# A second build changes nothing and reports nothing.
	recipe._apply_animation(ctx, src, Vector2i(0, 0), {"count": 3, "durations_ms": [100, 200]}, {"id": "p.a", "path": "x.png"}, issues)
	t.eq(issues, [])

func test_an_animation_over_existing_tiles_is_skipped_with_tile_008(t) -> void:
	var made := _tileset()
	var src: TileSetAtlasSource = made[1]
	src.create_tile(Vector2i(0, 0))
	src.create_tile(Vector2i(1, 0))
	var ctx := BuildContext.new("res://builder", "build")
	var issues: Array = []
	Recipe.new()._apply_animation(ctx, src, Vector2i(0, 0), {"count": 2, "durations_ms": []}, {"id": "p.a", "path": "x.png"}, issues)
	t.eq(issues.size(), 1)
	t.eq(issues[0]["code"], "TILE-008")
	t.eq(src.get_tile_animation_frames_count(Vector2i(0, 0)), 1)
