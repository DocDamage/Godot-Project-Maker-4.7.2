extends RefCounted
## The isometric tile set (T17.13): the tile set recipe on the catalog of the synthetic pack
## `iso_tiles` as rpggen describes it (tests/fixtures/iso_tiles, written by
## tools/make_iso_fixture.py: 96 tiles in two atlas pictures, a diamond of 60 x 34), and the
## lookups of `IsoTileset` the map recipes use.

const Recipe := preload("res://builder/recipes/tileset_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const IsoTileset := preload("res://builder/lib/iso_tileset.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const TS_PATH := "res://generated/tilesets/iso.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"
const FOOT := Vector2i(60, 34)
const GRASS := "iso_tiles.png.isotile_001_0"
const WATER := "iso_tiles.png.isotile_002_0"
const FIELD := "iso_tiles.png.isotile_003_0"
const WALL := "iso_tiles.png.isotile_019_0"

func _catalog() -> Dictionary:
	return JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)

func _context(cat: Dictionary, projection: String = "isometric") -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": projection, "features": {}}
	ctx.catalog = CatalogReader.new(cat, projection)
	return ctx

func _build(cat: Dictionary) -> Array:
	return Recipe.new().build(_context(cat))

func _load() -> TileSet:
	return ResourceLoader.load(TS_PATH, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet

func _cleanup() -> void:
	for p: String in [TS_PATH, STATE_PATH]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

func _codes(issues: Array) -> Array:
	var out: Array = []
	for i: Dictionary in issues:
		out.append(i["code"])
	out.sort()
	return out

func _data(ts: TileSet, iso: IsoTileset, asset_id: String, turn: int = 0) -> TileData:
	var tile := iso.tile_for(asset_id, turn)
	var source: int = tile["source"]
	var coords: Vector2i = tile["coords"]
	return (ts.get_source(source) as TileSetAtlasSource).get_tile_data(coords, 0)

func test_the_tile_set_of_the_iso_pack_has_the_shape_the_size_and_the_origins(t) -> void:
	_cleanup()
	var cat := _catalog()
	t.eq(_build(cat), [], "the recipe has nothing to say")
	var ts := _load()
	t.ok(ts != null, "generated/tilesets/iso.tres is written")
	t.eq(ts.tile_shape, TileSet.TILE_SHAPE_ISOMETRIC)
	t.eq(ts.tile_layout, TileSet.TILE_LAYOUT_DIAMOND_DOWN)
	t.eq(ts.tile_size, FOOT, "the diamond of the pack, which is not twice as wide as high")
	t.eq(ts.get_source_count(), 2, "96 tiles of 60 x 64 are two pictures of 64")
	var iso := IsoTileset.new(CatalogReader.new(cat, "isometric"))
	t.eq(iso.footprint(), FOOT)
	t.eq(iso.tile_ids().size(), 96)
	var tiles := 0
	for i in ts.get_source_count():
		var src := ts.get_source(ts.get_source_id(i)) as TileSetAtlasSource
		t.eq(src.texture_region_size, Vector2i(60, 64), "an atlas cell is the pack's canvas")
		tiles += src.get_tiles_count()
	t.eq(tiles, 96, "every tile and every turn of it is a tile")
	# the middle of the diamond is at (30, 39) of the 60 x 64 picture: 7 px under the middle
	# of the cell, for a flat tile and for a block that rises 12 px alike
	for asset_id: String in [GRASS, WALL, "iso_tiles.png.isotile_024_3"]:
		t.eq(iso.facets(asset_id).get("origin"), [30.0, 39.0], "%s: the catalog's origin" % asset_id)
		t.eq(_data(ts, iso, asset_id).texture_origin, Vector2i(0, 7), asset_id)
	t.eq(IsoTileset.texture_origin(Vector2i(30, 39), Vector2i(0, 0), Vector2i(60, 64)), Vector2i(0, 7))
	# a picture of 60 x 64 on the bottom of a cell of 60 x 120 lies 56 px down
	t.eq(IsoTileset.texture_origin(Vector2i(30, 39), Vector2i(0, 56), Vector2i(60, 120)), Vector2i(0, 35))
	_cleanup()

func test_a_painted_cell_lies_where_the_map_says(t) -> void:
	_cleanup()
	var cat := _catalog()
	t.eq(_build(cat), [])
	var ts := _load()
	var iso := IsoTileset.new(CatalogReader.new(cat, "isometric"))
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	for y in 4:
		for x in 5:
			t.ok(iso.paint(layer, Vector2i(x, y), GRASS, (x + y) % 4), "painted (%d, %d)" % [x, y])
	t.eq(layer.get_used_cells().size(), 20)
	# x is east and y south: east is down and to the right, south down and to the left
	t.eq(layer.map_to_local(Vector2i(0, 0)), Vector2(30, 17), "the first cell hangs under the layer's origin")
	t.eq(layer.map_to_local(Vector2i(1, 0)), Vector2(60, 34), "one east")
	t.eq(layer.map_to_local(Vector2i(0, 1)), Vector2(0, 34), "one south")
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(4, 0), Vector2i(0, 3), Vector2i(4, 3), Vector2i(2, 1), Vector2i(-3, 7)]:
		var middle := IsoTileset.cell_to_local(cell, FOOT)
		t.eq(layer.map_to_local(cell), middle, "cell_to_local is map_to_local for %s" % cell)
		t.eq(layer.local_to_map(middle), cell)
		for corner in IsoTileset.diamond(FOOT):
			t.eq(layer.local_to_map(middle + corner * 0.9), cell, "a point just inside a corner of %s" % cell)
	# what is painted is the tile that was asked for, turned as it was asked
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(3, 2), Vector2i(4, 3)]:
		var turn := (cell.x + cell.y) % 4
		var tile := iso.tile_for(GRASS, turn)
		t.eq(layer.get_cell_source_id(cell), tile["source"])
		t.eq(layer.get_cell_atlas_coords(cell), tile["coords"])
		t.eq(layer.get_cell_tile_data(cell).get_custom_data("asset_id"), "iso_tiles.png.isotile_001_%d" % turn)
	t.ok(not iso.paint(layer, Vector2i(9, 9), "no.such.tile"), "a tile that is not in the set is not painted")
	t.eq(layer.get_cell_source_id(Vector2i(9, 9)), -1)
	layer.free()
	_cleanup()

func test_the_collision_of_a_wall_cell_is_its_diamond(t) -> void:
	_cleanup()
	var cat := _catalog()
	t.eq(_build(cat), [])
	var ts := _load()
	var iso := IsoTileset.new(CatalogReader.new(cat, "isometric"))
	t.eq(ts.get_physics_layers_count(), 1)
	var wall := _data(ts, iso, WALL)
	t.eq(wall.get_collision_polygons_count(0), 1, "a wall blocks")
	t.eq(wall.get_collision_polygon_points(0, 0), PackedVector2Array([Vector2(0, -17), Vector2(30, 0), Vector2(0, 17), Vector2(-30, 0)]), "its diamond: the top, the right, the bottom, the left corner")
	t.eq(wall.get_collision_polygon_points(0, 0), IsoTileset.diamond(FOOT))
	t.eq(_data(ts, iso, GRASS).get_collision_polygons_count(0), 0, "ground blocks nothing")
	# the profiles of square tiles on the diamond: the half towards the south is the lower left
	t.eq(IsoTileset.collision_polygons({"profile": "FULL"}, FOOT, Vector2i(30, 39)), [IsoTileset.diamond(FOOT)])
	var half: Array = IsoTileset.collision_polygons({"profile": "BOTTOM_HALF"}, FOOT, Vector2i(30, 39))
	t.eq(half, [PackedVector2Array([Vector2(-15, -8.5), Vector2(15, 8.5), Vector2(0, 17), Vector2(-30, 0)])], "BOTTOM_HALF")
	t.eq(IsoTileset.collision_polygons({"profile": "NONE"}, FOOT, Vector2i(30, 39)), [])
	t.eq(IsoTileset.collision_polygons({"profile": "ALPHA_POLYGON"}, FOOT, Vector2i(30, 39)), [IsoTileset.diamond(FOOT)], "the outline of a picture drawn at an angle is not what stands on the ground")
	var custom: Array = IsoTileset.collision_polygons({"profile": "CUSTOM", "polygon": [[20, 39], [30, 34], [40, 39]]}, FOOT, Vector2i(30, 39))
	t.eq(custom, [PackedVector2Array([Vector2(-10, 0), Vector2(0, -5), Vector2(10, 0)])], "CUSTOM is in the px of the picture, from its origin")
	_cleanup()

func test_the_custom_data_the_maps_ask(t) -> void:
	_cleanup()
	var cat := _catalog()
	t.eq(_build(cat), [])
	var ts := _load()
	var iso := IsoTileset.new(CatalogReader.new(cat, "isometric"))
	for layer_name: String in ["asset_id", "footstep", "move_cost", "tillable", "water"]:
		t.ok(ts.get_custom_data_layer_by_name(layer_name) >= 0, "the layer %s" % layer_name)
	t.eq(_data(ts, iso, WATER).get_custom_data("water"), true)
	t.eq(_data(ts, iso, WATER).get_custom_data("tillable"), false)
	t.eq(_data(ts, iso, FIELD).get_custom_data("tillable"), true)
	t.eq(_data(ts, iso, FIELD).get_custom_data("footstep"), "grass")
	t.eq(_data(ts, iso, GRASS).get_custom_data("water"), false)
	t.eq(_data(ts, iso, GRASS).get_custom_data("footstep"), "")
	t.eq(_data(ts, iso, GRASS, 2).get_custom_data("asset_id"), "iso_tiles.png.isotile_001_2", "a turn is a tile of its own")
	_cleanup()

func test_tile_for_finds_a_tile_and_its_turns(t) -> void:
	var iso := IsoTileset.new(CatalogReader.new(_catalog(), "isometric"))
	t.ok(iso.has_tiles())
	t.eq(iso.tileset_name(), "iso")
	t.eq(iso.tileset_path(), TS_PATH)
	t.eq(iso.turns_of(GRASS), [0, 1, 2, 3])
	var seen := {}
	for turn in 4:
		var tile := iso.tile_for(GRASS, turn)
		t.eq(tile["asset_id"], "iso_tiles.png.isotile_001_%d" % turn)
		t.eq(tile["turn"], turn)
		seen[[tile["source"], tile["coords"]]] = true
		# any turn of the tile names the tile
		t.eq(iso.tile_for("iso_tiles.png.isotile_001_3", turn), tile)
	t.eq(seen.size(), 4, "four turns are four tiles of the atlas")
	t.eq(iso.tile_for(GRASS), iso.tile_for(GRASS, 0), "no turn is the first")
	t.eq(iso.tile_for(GRASS, 7)["asset_id"], GRASS, "a turn the pack did not draw is the first")
	t.eq(iso.tile_for("iso_tiles.png.tree_01_0"), {}, "an object is no tile of the set")
	t.eq(iso.tile_for("nobody"), {})
	# the cells are the ones the catalog wrote down: the first eight tiles in id order are the
	# first row of the first picture
	t.eq(iso.tile_for(GRASS, 0)["coords"], Vector2i(0, 0))
	t.eq(iso.tile_for(GRASS, 3)["coords"], Vector2i(3, 0))
	t.eq(iso.tile_for("iso_tiles.png.isotile_003_0")["coords"], Vector2i(0, 1))
	t.eq(iso.tile_for("iso_tiles.png.isotile_017_0")["source"], 1, "the 65th tile begins the second picture")
	t.eq(iso.tile_for("iso_tiles.png.isotile_017_0")["coords"], Vector2i(0, 0))

func _piece(id: String, pack: String, facets: Dictionary) -> Dictionary:
	var detected := {"usage": "iso_tile", "role": "GROUND", "projection": "isometric", "footprint": [100, 50], "origin": [50, 40], "size": [100, 65], "tags": []}
	detected.merge(facets, true)
	return {"id": id, "pack_id": pack, "path": "x.png", "status": "CONFIRMED", "detected": detected, "overrides": {}}

func _roads() -> IsoTileset:
	# a pack whose names say the sides (roads.*), and one whose tiles are turned four ways and of
	# which the audit said for one turn which sides it joins (turned.*)
	var assets := [
		_piece("roads.roadns", "roads", {"joins": ["n", "s"], "tags": ["road"]}),
		_piece("roads.roadew", "roads", {"joins": ["e", "w"], "tags": ["road"]}),
		_piece("roads.roadcorneres", "roads", {"joins": ["e", "s"], "tags": ["road"]}),
		_piece("roads.beache", "roads", {"joins": ["e"], "tags": ["beach"], "role": "WATER"}),
		_piece("roads.grass", "roads", {}),
		_piece("turned.bend_0", "turned", {"turn": 0, "joins": ["n", "e"], "tags": ["road", "turn:0"]}),
		_piece("turned.bend_1", "turned", {"turn": 1, "tags": ["road", "turn:1"]}),
		_piece("turned.bend_2", "turned", {"turn": 2, "tags": ["road", "turn:2"]}),
		_piece("turned.bend_3", "turned", {"turn": 3, "tags": ["road", "turn:3"]}),
	]
	var tiles := {}
	for i in assets.size():
		var entry := {"source": 0, "coords": [i, 0], "at": [0, 0]}
		var id: String = assets[i]["id"]
		if id.begins_with("turned."):
			entry["of"] = "turned.bend_0"
		tiles[id] = entry
	return IsoTileset.new(CatalogReader.new({"assets": assets, "objects": [], "tilesets": [{"name": "iso", "projection": "isometric", "tile_size": [100, 50], "sources": [], "tiles": tiles}]}, "isometric"))

func test_piece_for_chooses_the_piece_whose_joins_are_exactly_the_sides(t) -> void:
	var iso := _roads()
	t.eq(iso.piece_for("roads", ["n", "s"]), {"asset_id": "roads.roadns", "turn": 0})
	t.eq(iso.piece_for("roads", ["s", "n"]), {"asset_id": "roads.roadns", "turn": 0}, "the order of the sides says nothing")
	t.eq(iso.piece_for("roads", ["s", "e"]), {"asset_id": "roads.roadcorneres", "turn": 0})
	t.eq(iso.piece_for("roads", ["e"]), {"asset_id": "roads.beache", "turn": 0})
	t.eq(iso.piece_for("road", ["e"]), {}, "by tag: no road ends towards the east alone")
	t.eq(iso.piece_for("beach", ["e"]), {"asset_id": "roads.beache", "turn": 0}, "by tag")
	t.eq(iso.piece_for("WATER", ["e"]), {"asset_id": "roads.beache", "turn": 0}, "by role")
	t.eq(iso.piece_for("roads", ["n", "e", "s"]), {}, "exactly the sides: no piece for a junction")
	t.eq(iso.piece_for("roads", []), {}, "a piece that joins nothing is a plain tile")
	t.eq(iso.piece_for("nobody", ["n", "s"]), {})
	# a tile turned four ways: a quarter turn clockwise moves n to e, e to s, s to w, w to n
	t.eq(iso.piece_for("turned", ["n", "e"]), {"asset_id": "turned.bend_0", "turn": 0})
	t.eq(iso.piece_for("turned", ["e", "s"]), {"asset_id": "turned.bend_1", "turn": 1})
	t.eq(iso.piece_for("turned", ["s", "w"]), {"asset_id": "turned.bend_2", "turn": 2})
	t.eq(iso.piece_for("turned", ["n", "w"]), {"asset_id": "turned.bend_3", "turn": 3})
	t.eq(iso.piece_for("turned", ["n", "s"]), {}, "a bend is no straight, however it is turned")
	# what piece_for answers is what tile_for takes
	var piece := iso.piece_for("turned", ["s", "w"])
	var asset_id: String = piece["asset_id"]
	var turn: int = piece["turn"]
	t.eq(iso.tile_for(asset_id, turn)["coords"], Vector2i(7, 0))
	t.eq(iso.tile_for("turned.bend_0", 2)["coords"], Vector2i(7, 0))
	# by tag over both packs the piece whose own name says the sides comes first
	t.eq(iso.piece_for("road", ["e", "s"]), {"asset_id": "roads.roadcorneres", "turn": 0})
	t.eq(IsoTileset.turned_joins(["n", "e"], 1), ["e", "s"])
	t.eq(IsoTileset.turned_joins(["n", "e"], -1), ["n", "w"])
	t.eq(IsoTileset.normalized_joins(["w", "x", "n", "n"]), ["n", "w"])

func test_an_added_tile_gets_a_new_cell_and_no_painted_cell_moves(t) -> void:
	_cleanup()
	var cat := _catalog()
	t.eq(_build(cat), [])
	var iso := IsoTileset.new(CatalogReader.new(cat, "isometric"))
	var before := {}
	for asset_id in iso.tile_ids():
		before[asset_id] = iso.tile_for(asset_id)
	# a regeneration: one tile left the pack (the definition no longer places it), and the
	# origin of another was corrected in the audit
	var changed := _catalog()
	var def: Dictionary = changed["tilesets"][0]
	var tiles: Dictionary = def["tiles"]
	var gone: Dictionary = tiles["iso_tiles.png.isotile_005_2"]
	tiles.erase("iso_tiles.png.isotile_005_2")
	for asset: Dictionary in changed["assets"]:
		if asset["id"] == GRASS:
			asset["overrides"] = {"origin": [30, 41]}
	var issues := _build(changed)
	t.eq(_codes(issues), ["TILE-005"], "the tile that left is kept and reported")
	var ts := _load()
	var again := IsoTileset.new(CatalogReader.new(changed, "isometric"))
	for asset_id in again.tile_ids():
		t.eq(again.tile_for(asset_id), before[asset_id], asset_id)
	var kept := ts.get_source(JsonUtil.to_int(gone["source"])) as TileSetAtlasSource
	t.ok(kept.has_tile(Vector2i(JsonUtil.to_int(gone["coords"][0]), JsonUtil.to_int(gone["coords"][1]))), "its tile is still there for the maps that painted it")
	t.eq(_data(ts, again, GRASS).texture_origin, Vector2i(0, 9), "the corrected origin is the tile's")
	_cleanup()

func test_a_cell_that_grew_keeps_the_coords_of_its_tiles(t) -> void:
	_cleanup()
	# a pack of 32 tiles in the upper four rows of the first picture (the fixture's picture is
	# 512 px high: four rows of a cell that is twice as high still fit it)
	var small := _catalog()
	var small_tiles: Dictionary = small["tilesets"][0]["tiles"]
	for id: String in small_tiles.keys():
		var entry: Dictionary = small_tiles[id]
		if JsonUtil.to_int(entry["source"]) == 0 and JsonUtil.to_int(entry["coords"][1]) >= 4:
			small_tiles.erase(id)
	t.eq(_build(small), [])
	# the pack got a taller picture: the atlas cell is 60 x 128 now, and every tile stands on
	# the bottom of it, at the atlas coords it had
	var grown := small.duplicate(true)
	for asset: Dictionary in grown["assets"]:
		if asset["id"] == "rpggen_iso.iso_tiles_0":
			var detected: Dictionary = asset["detected"]
			var grid: Dictionary = detected["grid"]
			grid["cell"] = [60, 128]
	var tiles: Dictionary = grown["tilesets"][0]["tiles"]
	for id: String in tiles.keys():
		var entry: Dictionary = tiles[id]
		if JsonUtil.to_int(entry["source"]) == 0:
			entry["at"] = [0, 64]
	t.eq(_build(grown), [], "nothing to say: every tile still fits its picture")
	# a tile whose cell is outside the picture is reported and not made
	var outside := grown.duplicate(true)
	var beyond: Dictionary = outside["tilesets"][0]["tiles"]
	beyond["iso_tiles.png.isotile_008_3"]["coords"] = [7, 4]
	t.eq(_codes(_build(outside)), ["TILE-002", "TILE-005"], "the cell outside the picture, and the tile it left")
	t.eq(_build(grown), [])
	var ts := _load()
	var iso := IsoTileset.new(CatalogReader.new(grown, "isometric"))
	var src := ts.get_source(0) as TileSetAtlasSource
	t.eq(src.texture_region_size, Vector2i(60, 128))
	t.eq(iso.tile_for(GRASS)["coords"], Vector2i(0, 0), "the coords are the catalog's, whatever the cell")
	t.ok(src.has_tile(Vector2i(0, 0)) and src.has_tile(Vector2i(7, 3)))
	t.eq(_data(ts, iso, GRASS).texture_origin, Vector2i(0, 39), "(30, 39) + (0, 64) - (30, 64)")
	t.eq((ts.get_source(1) as TileSetAtlasSource).texture_region_size, Vector2i(60, 64), "the other picture is as it was")
	_cleanup()

func test_a_top_down_project_is_offered_nothing_isometric(t) -> void:
	var cat := _catalog()
	var top := CatalogReader.new(cat, "top_down")
	t.eq(top.assets_by_role("GROUND"), [], "no isometric tile is a top-down project's ground")
	t.eq(top.assets_by_role("DECORATION"), [], "... and no isometric tree its scenery")
	t.eq(top.assets().size(), 0)
	t.ok(not top.asset(GRASS).is_empty(), "an asset is still found by its id")
	var iso := CatalogReader.new(cat, "isometric")
	t.eq(iso.assets_by_role("GROUND").size(), 92, "an isometric project is: 23 tiles in four turns")
	t.eq(iso.assets_by_role("WALL").size(), 4)
	t.eq(iso.assets_by_role("NONE"), [], "the atlas pictures are nobody's choice")
	var square := {"id": "p.sheet", "detected": {"usage": "tiles", "role": "GROUND"}, "overrides": {}}
	var hero := {"id": "p.hero", "detected": {"usage": "sprite", "role": "PLAYER"}, "overrides": {}}
	var car := {"id": "p.car", "detected": {"usage": "sprite", "role": "VEHICLE", "projection": "isometric"}, "overrides": {}}
	var mixed := {"assets": [square, hero, car]}
	t.eq(CatalogReader.new(mixed).assets().size(), 2, "top-down: the sheet and the hero")
	t.eq(CatalogReader.new(mixed).assets_by_role("VEHICLE"), [])
	t.eq(CatalogReader.new(mixed, "isometric").assets_by_role("GROUND"), [], "an isometric project paints with no sheet of squares")
	t.eq(CatalogReader.new(mixed, "isometric").assets_by_role("PLAYER").size(), 1, "a hero drawn for a top-down game walks both")
	t.eq(CatalogReader.new(mixed, "isometric").assets_by_role("VEHICLE").size(), 1)

func test_an_object_stands_on_the_middle_of_its_cell(t) -> void:
	var cat := _catalog()
	var tree := CatalogReader.effective(CatalogReader.new(cat, "isometric").asset("iso_tiles.png.tree_01_0"))
	var sprite := Sprite2D.new()
	IsoTileset.stand(sprite, tree, IsoTileset.cell_to_local(Vector2i(2, 1), FOOT))
	t.eq(sprite.position, Vector2(60, 68))
	t.eq(sprite.offset, Vector2(-30, -39), "the picture's origin lies on the middle of the cell")
	t.ok(not sprite.centered)
	sprite.free()
	t.eq(IsoTileset.cells_under(Vector2i(5, 5), {"stands_on": [1, 1]}), [Vector2i(5, 5)])
	t.eq(IsoTileset.cells_under(Vector2i(5, 5), {"stands_on": [2, 1]}), [Vector2i(5, 5), Vector2i(4, 5)])
	t.eq(IsoTileset.cells_under(Vector2i(5, 5), {}), [Vector2i(5, 5)])

func test_a_top_down_tile_set_is_not_touched_by_the_isometric_code(t) -> void:
	# the definition of a square tile set has no `projection`: the recipe's hash has no `iso` key
	var ctx := _context({"assets": [], "objects": [], "tilesets": []}, "top_down")
	t.eq(IsoTileset.inputs(ctx.catalog), [])
	t.ok(not IsoTileset.wanted({"name": "overworld", "tile_size": [16, 16]}))
	t.ok(IsoTileset.wanted({"name": "iso", "projection": "isometric"}))
	t.ok(not IsoTileset.project_wanted({}), "a config without the key is top-down")
	t.ok(IsoTileset.project_wanted({"projection": "isometric"}))
