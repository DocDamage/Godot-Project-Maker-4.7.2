extends RefCounted
## Painting maps with terrains (T17.31): RpgTerrain (Godot's painting and the seeded choice of
## variants), TerrainPaint (which terrain paints what) and the peering bits of a diamond.

const Recipe := preload("res://builder/recipes/tileset_recipe.gd")
const TerrainPaint := preload("res://builder/lib/terrain_paint.gd")

# the 13 tiles of a block of 3 x 3 with its inner corners, and two more middles (variants)
const MASKS := {
	Vector2i(0, 0): 28, Vector2i(1, 0): 124, Vector2i(2, 0): 112,
	Vector2i(0, 1): 31, Vector2i(1, 1): 255, Vector2i(2, 1): 241,
	Vector2i(0, 2): 7, Vector2i(1, 2): 199, Vector2i(2, 2): 193,
	Vector2i(3, 0): 253, Vector2i(4, 0): 247, Vector2i(3, 1): 223, Vector2i(4, 1): 127,
	Vector2i(5, 0): 255, Vector2i(6, 0): 255,
}
const GRASS := Vector2i(7, 3)
const KEYS := {
	1: "top_side", 2: "top_right_corner", 4: "right_side", 8: "bottom_right_corner",
	16: "bottom_side", 32: "bottom_left_corner", 64: "left_side", 128: "top_left_corner",
}

func _sets() -> Array:
	return [{"name": "dirt_block", "mode": "corners_and_sides", "terrains": [{"name": "dirt", "color": "#8d6e63"}],
		"surface": "dirt", "over": "ground", "shape": "area", "sheet": "pack.ground"}]

## A tile set with the block above: its tiles' terrain set from the catalog's keys, the two
## extra middles at probability 0.5, and a plain tile of grass without a terrain.
func _tileset() -> TileSet:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	Recipe.ensure_terrain_sets(ts, _sets())
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(128, 64, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(16, 16)
	ts.add_source(src, 0)
	for coords: Vector2i in MASKS:
		src.create_tile(coords)
		var peering := {}
		for bit: int in KEYS:
			peering[KEYS[bit]] = 0 if MASKS[coords] & bit else -1
		Recipe.apply_terrain(src.get_tile_data(coords, 0), ts, _sets(), {"set": "dirt_block", "terrain": 0, "peering": peering})
		if coords.x >= 5:
			src.get_tile_data(coords, 0).probability = 0.5
	src.create_tile(GRASS)
	return ts

func _layer(ts: TileSet, grass: bool) -> TileMapLayer:
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	if grass:
		for y in 10:
			for x in 10:
				layer.set_cell(Vector2i(x, y), 0, GRASS)
	return layer

func test_an_area_is_painted_with_its_edges_over_plain_tiles_and_over_nothing(t) -> void:
	for grass: bool in [true, false]:
		var layer := _layer(_tileset(), grass)
		RpgTerrain.paint_area(layer, RpgTerrain.rect_cells(Rect2i(2, 2, 4, 3)), 0, 0, 7)
		t.eq(layer.get_cell_atlas_coords(Vector2i(2, 2)), Vector2i(0, 0), "the top left corner")
		t.eq(layer.get_cell_atlas_coords(Vector2i(3, 2)), Vector2i(1, 0), "the top edge")
		t.eq(layer.get_cell_atlas_coords(Vector2i(5, 4)), Vector2i(2, 2), "the bottom right corner")
		t.eq(layer.get_cell_atlas_coords(Vector2i(1, 1)), GRASS if grass else Vector2i(-1, -1), "a cell outside is not changed")
		var middle := layer.get_cell_atlas_coords(Vector2i(3, 3))
		t.ok(middle == Vector2i(1, 1) or middle.x >= 5, "the middle is a middle or one of its variants")
		layer.free()

func test_the_variants_are_chosen_by_the_seed_whatever_godot_drew(t) -> void:
	var cells := RpgTerrain.rect_cells(Rect2i(0, 0, 12, 12))
	var first := PackedStringArray()
	var second := PackedStringArray()
	for out: PackedStringArray in [first, second]:
		seed(randi())  # Godot's own choice draws from the global generator: another each time
		var layer := _layer(_tileset(), false)
		RpgTerrain.paint_area(layer, cells, 0, 0, 1234)
		for cell in cells:
			out.append(str(layer.get_cell_atlas_coords(cell)))
		layer.free()
	t.eq(first, second, "the same seed paints the same map")
	var used := {}
	for coords: String in first:
		used[coords] = true
	t.ok(used.has(str(Vector2i(5, 0))) and used.has(str(Vector2i(1, 1))), "the variants are used")

func test_a_ground_is_filled_with_the_variants_of_its_tile(t) -> void:
	var ts := _tileset()
	var layer := _layer(ts, false)
	var tile := {"source_id": 0, "coords": Vector2i(1, 1)}
	t.eq(RpgTerrain.variants_of(ts, 0, Vector2i(1, 1)).size(), 3)
	t.eq(RpgTerrain.variants_of(ts, 0, GRASS).size(), 0, "a tile of no terrain has none")
	RpgTerrain.fill_varied(layer, RpgTerrain.rect_cells(Rect2i(0, 0, 8, 8)), tile, 99)
	var counts := {}
	for cell in layer.get_used_cells():
		var coords := layer.get_cell_atlas_coords(cell)
		counts[coords] = int(counts.get(coords, 0)) + 1
	t.eq(counts.size(), 3, "every variant is laid")
	t.ok(int(counts.get(Vector2i(1, 1), 0)) > int(counts.get(Vector2i(5, 0), 0)), "the middle more often than a variant of probability 0.5")
	layer.free()

func test_a_path_joins_only_the_cells_before_and_after(t) -> void:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	var sets := [{"name": "path", "mode": "sides", "terrains": [{"name": "path", "color": "#ffffff"}], "surface": "path", "shape": "path"}]
	Recipe.ensure_terrain_sets(ts, sets)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(64, 64, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(16, 16)
	ts.add_source(src, 0)
	var names := ["top_side", "right_side", "bottom_side", "left_side"]
	for sides in 16:
		var coords := Vector2i(sides % 4, sides / 4)
		src.create_tile(coords)
		var peering := {}
		for i in 4:
			peering[names[i]] = 0 if sides & (1 << i) else -1
		Recipe.apply_terrain(src.get_tile_data(coords, 0), ts, sets, {"set": "path", "terrain": 0, "peering": peering})
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	var path: Array[Vector2i] = [Vector2i(1, 1), Vector2i(2, 1), Vector2i(2, 2)]
	RpgTerrain.paint_path(layer, path, 0, 0, 1)
	var beside: Array[Vector2i] = [Vector2i(1, 2), Vector2i(1, 3)]
	RpgTerrain.paint_path(layer, beside, 0, 0, 1)
	# sides bits: n 1, e 2, s 4, w 8 (the tile's x + 4 y)
	var code := func(cell: Vector2i) -> int: return layer.get_cell_atlas_coords(cell).x + 4 * layer.get_cell_atlas_coords(cell).y
	t.eq(code.call(Vector2i(1, 1)), 2, "the first joins east")
	t.eq(code.call(Vector2i(2, 1)), 4 | 8, "the corner joins west and south")
	t.eq(code.call(Vector2i(1, 2)), 4, "a path beside the first is not joined to it")
	layer.free()

func test_the_peering_of_a_diamond_follows_the_grid(t) -> void:
	var ts := TileSet.new()
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	ts.tile_size = Vector2i(64, 32)
	var sets := [{"name": "road", "mode": "sides", "terrains": [{"name": "road", "color": "#555555"}]}]
	Recipe.ensure_terrain_sets(ts, sets)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(64, 32, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(64, 32)
	ts.add_source(src, 0)
	src.create_tile(Vector2i.ZERO)
	var td := src.get_tile_data(Vector2i.ZERO, 0)
	t.ok(Recipe.apply_iso_terrain(td, ts, sets, {"set": "road", "peering": {"top_side": 0, "right_side": 0, "bottom_side": -1, "left_side": -1}}))
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_TOP_RIGHT_SIDE), 0, "n is the upper right side")
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_SIDE), 0, "e is the lower right side")
	t.eq(td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_SIDE), -1)
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	t.eq(layer.get_neighbor_cell(Vector2i(2, 2), TileSet.CELL_NEIGHBOR_TOP_RIGHT_SIDE), Vector2i(2, 1), "the neighbour on n is north by the grid")
	t.eq(layer.get_neighbor_cell(Vector2i(2, 2), TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_SIDE), Vector2i(3, 2), "the neighbour on e is east")
	t.eq(layer.get_neighbor_cell(Vector2i(2, 2), TileSet.CELL_NEIGHBOR_RIGHT_CORNER), Vector2i(3, 1), "the right corner is north-east")
	layer.free()

func test_terrains_are_found_by_surface_and_shape(t) -> void:
	var def := {"terrain_sets": [
		{"name": "lot", "mode": "corners_and_sides", "terrains": [{"name": "road", "color": "#fff"}], "surface": "road", "shape": "any", "sheet": "a"},
		{"name": "road", "mode": "sides", "terrains": [{"name": "road", "color": "#fff"}], "surface": "road", "shape": "path", "sheet": "b"},
		{"name": "Tiled", "mode": "corners", "terrains": [{"name": "Deep Water", "color": "#00f"}]},
		{"name": "plain", "mode": "corners_and_sides", "terrains": [{"name": "grass", "color": "#0f0"}], "surface": "grass", "shape": "plain"},
	]}
	t.eq(int(TerrainPaint.find(null, def, null, ["road"], ["path"]).get("set", -1)), 1, "a path's terrain by its shape")
	t.eq(int(TerrainPaint.find(null, def, null, ["road"], ["path", "any"]).get("set", -1)), 0, "of two shapes the first in the definition")
	t.eq(int(TerrainPaint.find(null, def, null, ["water"], ["any"]).get("set", -1)), 2, "a wang terrain whose name has the word")
	t.ok(TerrainPaint.find(null, def, null, ["grass"], ["any", "area"]).is_empty(), "plain variants paint no area")
	t.eq(TerrainPaint.find(null, def, null, ["dirt", "road"], ["any"], [], "road"), {}, "the surface to avoid is not taken")
