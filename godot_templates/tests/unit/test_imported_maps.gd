extends RefCounted
## T12.49: painting of imported Tiled and LDtk maps (MapBuild) and the selection rules of the
## imported maps recipe. The full build is covered by the generation tests on the synthetic packs
## tiled_map and ldtk_level.

const MapBuild := preload("../../builder/lib/map_build.gd")
const ImportedMaps := preload("../../builder/recipes/imported_maps_recipe.gd")
const BuildContext := preload("../../builder/lib/build_context.gd")
const CatalogReader := preload("../../builder/lib/catalog_reader.gd")

## A tile set with one 16 px atlas source (id 3) that has the tiles (0,0), (1,0) and (0,1).
func _tile_set() -> TileSet:
	var tile_set := TileSet.new()
	tile_set.tile_size = Vector2i(16, 16)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create(32, 32, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(16, 16)
	source.create_tile(Vector2i(0, 0))
	source.create_tile(Vector2i(1, 0))
	source.create_tile(Vector2i(0, 1))
	tile_set.add_source(source, 3)
	return tile_set

func _context(config: Dictionary, maps: Array) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = config
	ctx.catalog = CatalogReader.new({"maps": maps})
	return ctx

func _map(map_id: String, pack: String) -> Dictionary:
	return {"id": map_id, "pack_id": pack, "source": "", "format": "tiled", "tile_size": [16, 16], "size": [2, 2], "layers": []}

func test_flips_become_the_bits_of_the_alternative_tile(t) -> void:
	t.eq(MapBuild.transform_alt(0), 0)
	t.eq(MapBuild.transform_alt(MapBuild.BIT_FLIP_H), TileSetAtlasSource.TRANSFORM_FLIP_H)
	t.eq(MapBuild.transform_alt(MapBuild.BIT_FLIP_V), TileSetAtlasSource.TRANSFORM_FLIP_V)
	t.eq(MapBuild.transform_alt(MapBuild.BIT_TRANSPOSE | MapBuild.BIT_FLIP_H), TileSetAtlasSource.TRANSFORM_TRANSPOSE | TileSetAtlasSource.TRANSFORM_FLIP_H)

func test_runs_are_painted_row_by_row_with_their_flips(t) -> void:
	var tile_set := _tile_set()
	var layer := TileMapLayer.new()
	layer.tile_set = tile_set
	# 3 x 2 map: [empty, tile (0,0), tile (1,0) flipped in x] / [3 x tile (0,1) flipped in y]
	var runs: Array = [[1, -1, 0, 0, 0], [1, 3, 0, 0, 0], [1, 3, 1, 0, MapBuild.BIT_FLIP_H], [3, 3, 0, 1, MapBuild.BIT_FLIP_V]]
	var missing := MapBuild.paint_runs(layer, tile_set, 3, runs)
	t.eq(missing, 0)
	t.eq(layer.get_used_cells().size(), 5)
	t.eq(layer.get_cell_source_id(Vector2i(0, 0)), -1)
	t.eq(layer.get_cell_atlas_coords(Vector2i(1, 0)), Vector2i(0, 0))
	t.eq(layer.get_cell_atlas_coords(Vector2i(2, 0)), Vector2i(1, 0))
	t.eq(layer.get_cell_alternative_tile(Vector2i(2, 0)), TileSetAtlasSource.TRANSFORM_FLIP_H)
	t.eq(layer.get_cell_alternative_tile(Vector2i(1, 0)), 0)
	for x in 3:
		t.eq(layer.get_cell_atlas_coords(Vector2i(x, 1)), Vector2i(0, 1))
		t.eq(layer.get_cell_alternative_tile(Vector2i(x, 1)), TileSetAtlasSource.TRANSFORM_FLIP_V)
	layer.free()

func test_tiles_the_tile_set_does_not_have_stay_empty(t) -> void:
	var tile_set := _tile_set()
	var layer := TileMapLayer.new()
	layer.tile_set = tile_set
	# (1,1) is not a tile of the source and source 9 does not exist
	var runs: Array = [[2, 3, 1, 1, 0], [1, 9, 0, 0, 0], [1, 3, 0, 0, 0]]
	t.eq(MapBuild.paint_runs(layer, tile_set, 2, runs), 3)
	t.eq(layer.get_used_cells(), [Vector2i(1, 1)])
	layer.free()

func test_solid_values_are_read_from_the_value_list(t) -> void:
	var values: Array = [{"value": 1, "name": "wall", "solid": true}, {"value": 2, "name": "water", "solid": false}, {"value": 3, "name": "", "solid": true}]
	t.eq(MapBuild.solid_values(values), [1, 3])

func test_solid_cells_are_merged_into_rectangles(t) -> void:
	# 4 x 3 map:  1 1 0 1 / 1 1 0 0 / 0 0 2 1   (1 and 2 are solid: 7 cells)
	var runs: Array = [[2, 1], [1, 0], [1, 1], [2, 1], [2, 0], [2, 0], [1, 2], [1, 1]]
	var solid: Array[int] = [1, 2]
	var rects := MapBuild.solid_rects(4, runs, solid)
	var area := 0
	for r in rects:
		area += r.size.x * r.size.y
	t.eq(area, 7, "every solid cell is covered once")
	t.ok(rects.has(Rect2i(0, 0, 2, 2)), "equal runs on two rows join into one rectangle")
	t.ok(rects.has(Rect2i(3, 0, 1, 1)) and rects.has(Rect2i(2, 2, 2, 1)))
	t.eq(rects.size(), 3)
	var none: Array[int] = []
	t.eq(MapBuild.solid_rects(4, runs, none).size(), 0)

func test_the_free_cell_nearest_the_middle_is_not_solid(t) -> void:
	var solid := {Vector2i(2, 2): true}
	var cell := MapBuild.free_cell_near_centre(Vector2i(5, 5), solid)
	t.ok(cell != Vector2i(2, 2) and absi(cell.x - 2) + absi(cell.y - 2) == 1, "next to the solid middle")
	var all := {}
	for y in 2:
		for x in 2:
			all[Vector2i(x, y)] = true
	t.eq(MapBuild.free_cell_near_centre(Vector2i(2, 2), all), Vector2i(-1, -1))

func test_the_starter_is_not_built_as_an_extra_map(t) -> void:
	var maps: Array = [_map("pk.maps.town", "pk"), _map("pk.maps.cave", "pk"), _map("pk.maps.unused", "pk")]
	var ctx := _context({"imported_maps": {"include": ["pk.maps.town", "pk.maps.cave"], "starter": "pk.maps.town"}}, maps)
	var extra := ImportedMaps.extra_maps(ctx)
	t.eq(extra.size(), 1)
	t.eq(extra[0]["id"], "pk.maps.cave")
	t.eq(ImportedMaps.starter_map(ctx)["id"], "pk.maps.town")
	t.eq(ImportedMaps.map_path(extra[0]), "res://game/maps/imported/pk/maps_cave.tscn")
	var none := _context({}, maps)
	t.eq(ImportedMaps.extra_maps(none).size(), 0)
	t.ok(ImportedMaps.starter_map(none).is_empty())

func test_a_door_finds_the_maps_that_are_built(t) -> void:
	var maps: Array = [_map("pk.maps.town", "pk"), _map("pk.maps.cave", "pk"), _map("pk.maps.unused", "pk")]
	var ctx := _context({"imported_maps": {"include": ["pk.maps.town", "pk.maps.cave"], "starter": "pk.maps.town"}}, maps)
	t.eq(ImportedMaps.resolve_target(ctx, "cave"), "res://game/maps/imported/pk/maps_cave.tscn")
	t.eq(ImportedMaps.resolve_target(ctx, "pk.maps.cave"), "res://game/maps/imported/pk/maps_cave.tscn")
	t.eq(ImportedMaps.resolve_target(ctx, "town"), "res://game/maps/starter_map.tscn")
	t.eq(ImportedMaps.resolve_target(ctx, "starter_map"), "res://game/maps/starter_map.tscn")
	t.eq(ImportedMaps.resolve_target(ctx, "res://game/maps/other.tscn"), "res://game/maps/other.tscn")
	t.eq(ImportedMaps.resolve_target(ctx, "unused"), "", "a map that is not selected is not built")
	t.eq(ImportedMaps.resolve_target(ctx, ""), "")
