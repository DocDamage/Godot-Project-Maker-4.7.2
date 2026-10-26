extends RefCounted
## tileset_recipe merge rules (T5.04): painted tiles keep their source ids and tiles, sources are
## never dropped silently, collision is replaced only where the catalog changed it.

const Recipe := preload("res://builder/recipes/tileset_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")

const TS_PATH := "res://generated/tilesets/merge_test.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"

func _asset(id: String, status: String = "CONFIRMED", extra: Dictionary = {}) -> Dictionary:
	var detected := {
		"usage": "tiles", "role": "GROUND",
		"grid": {"cell": [32, 32], "margin": [0, 0], "separation": [0, 0]},
		"collision": {"profile": "NONE"},
	}
	return {"id": id, "path": "icon.svg", "status": status, "detected": detected, "overrides": extra}

func _catalog(assets: Array, sources: Array, retired: Array = []) -> Dictionary:
	return {
		"assets": assets,
		"tilesets": [{
			"name": "merge_test", "tile_size": [32, 32], "sources": sources,
			"physics_layers": [{"layer_bits": 1, "mask_bits": 0}],
			"custom_data": [{"name": "asset_id", "type": "string"}],
			"patterns_from_objects": false,
		}],
		"id_allocations": {"tilesets": {"merge_test": {"next_source_id": 3, "retired": retired}}},
		"objects": [],
	}

func _build(cat: Dictionary) -> Array:
	var ctx := BuildContext.new("res://builder")
	ctx.catalog = CatalogReader.new(cat)
	return Recipe.new().build(ctx)

func _load() -> TileSet:
	return ResourceLoader.load(TS_PATH, "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet

func _codes(issues: Array) -> Array:
	var out: Array = []
	for i in issues:
		out.append(i["code"])
	out.sort()
	return out

func _cleanup() -> void:
	for p in [TS_PATH, STATE_PATH]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

func _polygon_count(ts: TileSet, source_id: int, coords: Vector2i) -> int:
	var src := ts.get_source(source_id) as TileSetAtlasSource
	return src.get_tile_data(coords, 0).get_collision_polygons_count(0)

func _tiles(ts: TileSet, source_id: int) -> Array:
	var src := ts.get_source(source_id) as TileSetAtlasSource
	var out: Array = []
	for i in src.get_tiles_count():
		out.append(src.get_tile_id(i))
	return out

func test_merge_keeps_painted_cells_and_adds_new_sources(t) -> void:
	_cleanup()
	var base_sources := [{"asset": "t.a", "source_id": 0}, {"asset": "t.c", "source_id": 1}]
	t.eq(_build(_catalog([_asset("t.a"), _asset("t.c")], base_sources)), [])
	var first := _load()
	t.eq(first.get_source_count(), 2)
	t.eq(_polygon_count(first, 0, Vector2i(0, 0)), 0)
	# Paint a few cells with the first TileSet.
	var layer := TileMapLayer.new()
	layer.tile_set = first
	var painted := [[Vector2i(0, 0), 0], [Vector2i(1, 0), 0], [Vector2i(2, 1), 1]]
	for p in painted:
		layer.set_cell(p[0], p[1], p[0])
	var before: Array = []
	for p in painted:
		before.append([layer.get_cell_source_id(p[0]), layer.get_cell_atlas_coords(p[0])])
	layer.free()

	# The catalog changes: one sheet is added, one tile's collision changes, one sheet is gone.
	var changed := _asset("t.a", "CONFIRMED", {"tile_overrides": {"0,0": {"collision": {"profile": "FULL"}}}})
	var gone := _asset("t.c", "MISSING")
	var sources := [{"asset": "t.a", "source_id": 0}, {"asset": "t.c", "source_id": 1}, {"asset": "t.b", "source_id": 2}]
	var issues := _build(_catalog([changed, gone, _asset("t.b")], sources))
	t.eq(_codes(issues), ["REGEN-003"], "the removed sheet is reported and kept")
	var merged := _load()
	t.eq(merged.get_source_count(), 3)
	t.ok(merged.has_source(0) and merged.has_source(1) and merged.has_source(2), "ids 0, 1, 2")
	t.eq(_polygon_count(merged, 0, Vector2i(0, 0)), 1, "collision of the changed tile was replaced")
	t.eq(_polygon_count(merged, 0, Vector2i(1, 0)), 0, "other tiles keep theirs")
	t.eq(_tiles(merged, 1), _tiles(first, 1), "the kept source still has all its tiles")
	var layer2 := TileMapLayer.new()
	layer2.tile_set = merged
	for i in painted.size():
		layer2.set_cell(painted[i][0], painted[i][1], painted[i][0])
		t.eq([layer2.get_cell_source_id(painted[i][0]), layer2.get_cell_atlas_coords(painted[i][0])], before[i], "painted cell %d" % i)
	layer2.free()
	_cleanup()

func test_collision_edited_in_godot_is_kept(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	t.eq(_build(_catalog([_asset("t.a")], sources)), [])
	# The user draws a custom polygon on tile (1, 0) in the editor.
	var ts := _load()
	var td := (ts.get_source(0) as TileSetAtlasSource).get_tile_data(Vector2i(1, 0), 0)
	td.add_collision_polygon(0)
	td.set_collision_polygon_points(0, 0, PackedVector2Array([Vector2(-4, -4), Vector2(4, -4), Vector2(0, 6)]))
	t.eq(ResourceSaver.save(ts, TS_PATH), OK)
	var edited := _asset("t.a", "CONFIRMED", {"tile_overrides": {"1,0": {"collision": {"profile": "FULL"}}}})
	var issues := _build(_catalog([edited], sources))
	t.eq(_codes(issues), ["TILE-007"], "the kept edit is reported")
	var after := _load()
	var points := (after.get_source(0) as TileSetAtlasSource).get_tile_data(Vector2i(1, 0), 0).get_collision_polygon_points(0, 0)
	t.eq(points.size(), 3, "the user's triangle is still there")
	_cleanup()

func test_a_conflict_asset_is_left_untouched(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	t.eq(_build(_catalog([_asset("t.a")], sources)), [])
	var ts := _load()
	var src := ts.get_source(0) as TileSetAtlasSource
	var tiles_before := _tiles(ts, 0)
	var resized := _asset("t.a", "CONFLICT", {"grid": {"cell": [16, 16]}})
	var issues := _build(_catalog([resized], sources))
	t.eq(_codes(issues), ["TILE-004"])
	var after := _load()
	t.eq((after.get_source(0) as TileSetAtlasSource).texture_region_size, src.texture_region_size, "geometry untouched")
	t.eq(_tiles(after, 0), tiles_before, "tiles untouched")
	_cleanup()

func test_a_source_goes_only_with_remove_source(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}, {"asset": "t.c", "source_id": 1}]
	t.eq(_build(_catalog([_asset("t.a"), _asset("t.c")], sources)), [])
	var confirmed := _asset("t.c", "UNUSED", {"remove_source": true})
	t.eq(_build(_catalog([_asset("t.a"), confirmed], sources)), [])
	var ts := _load()
	t.ok(ts.has_source(0) and not ts.has_source(1), "only the confirmed source was removed")
	_cleanup()

func test_a_changed_tile_size_is_reported_and_kept(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	t.eq(_build(_catalog([_asset("t.a")], sources)), [])
	var cat := _catalog([_asset("t.a")], sources)
	cat["tilesets"][0]["tile_size"] = [16, 16]
	var issues := _build(cat)
	t.ok(_codes(issues).has("TILE-004"))
	t.eq(_load().tile_size, Vector2i(32, 32))
	_cleanup()

func test_cells_that_became_empty_are_reported_and_kept(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	t.eq(_build(_catalog([_asset("t.a")], sources)), [])
	var tiles := _tiles(_load(), 0)
	var skipped := _asset("t.a", "CONFIRMED", {"tile_overrides": {"1,1": {"skip": true}}})
	var issues := _build(_catalog([skipped], sources))
	t.ok(_codes(issues).has("TILE-005"))
	t.eq(_tiles(_load(), 0), tiles, "no tile was removed")
	_cleanup()

# ---------------------------------------------------------------- side view (T14.02, T14.03)

func _build_as(cat: Dictionary, archetype: String) -> Array:
	var ctx := BuildContext.new("res://builder")
	ctx.catalog = CatalogReader.new(cat)
	ctx.config = {"archetype": archetype}
	return Recipe.new().build(ctx)

func _bytes() -> String:
	return FileAccess.get_file_as_string(TS_PATH)

## A sheet whose first tile has `profile` and whose second has the custom data `custom`.
func _side_sheet(profile: String, custom: Dictionary = {}) -> Dictionary:
	var overrides := {"0,0": {"collision": {"profile": profile}}}
	if not custom.is_empty():
		overrides["1,0"] = {"custom": custom}
	return _asset("t.a", "CONFIRMED", {"tile_overrides": overrides})

func test_a_top_down_tileset_is_the_same_with_one_way_ladder_or_none(t) -> void:
	var sources := [{"asset": "t.a", "source_id": 0}]
	var built: Array = []
	for profile: String in ["NONE", "ONE_WAY", "LADDER"]:
		for archetype: String in ["turn_based", "arpg"]:
			_cleanup()
			t.eq(_build_as(_catalog([_side_sheet(profile, {"hazard": true})], sources), archetype), [])
			built.append(_bytes())
	_cleanup()
	t.eq(_build(_catalog([_side_sheet("NONE", {"hazard": true})], sources)), [], "a build without a config, as before 1.2")
	built.append(_bytes())
	for text: String in built:
		t.ok(text == built[0], "every top-down TileSet has the same bytes")
	t.ok(not built[0].contains("one_way") and not built[0].contains("ladder") and not built[0].contains("physics_layer_1"), "and no side-view layer")
	_cleanup()

func test_a_side_view_tileset_has_the_one_way_layer_and_the_custom_data(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	var sheet := _asset("t.a", "CONFIRMED", {"tile_overrides": {
		"0,0": {"collision": {"profile": "ONE_WAY"}},
		"1,0": {"collision": {"profile": "LADDER"}},
		"2,0": {"collision": {"profile": "NONE"}, "custom": {"hazard": true}},
		"3,0": {"custom": {"breakable": true}},
	}})
	sheet["detected"].erase("collision")  # a GROUND sheet that names no collision: solid in a room
	t.eq(_build_as(_catalog([sheet], sources), "metroidvania"), [])
	var ts := _load()
	t.eq(ts.get_physics_layers_count(), 2)
	t.eq(ts.get_physics_layer_collision_layer(1), 1 << 10, "one-way platforms are on layer 11")
	for layer_name: String in ["ladder", "hazard", "breakable"]:
		t.ok(ts.get_custom_data_layer_by_name(layer_name) >= 0, layer_name)
	var src := ts.get_source(0) as TileSetAtlasSource
	var plank := src.get_tile_data(Vector2i(0, 0), 0)
	t.eq(plank.get_collision_polygons_count(0), 0, "a one-way tile is not solid")
	t.eq(plank.get_collision_polygons_count(1), 1)
	t.ok(plank.is_collision_polygon_one_way(1, 0))
	var points := plank.get_collision_polygon_points(1, 0)
	t.eq(points[0], Vector2(-16, -16))
	t.eq(points[2], Vector2(16, -6), "the top 10 px of a 32 px tile")
	var ladder := src.get_tile_data(Vector2i(1, 0), 0)
	t.eq(ladder.get_collision_polygons_count(0) + ladder.get_collision_polygons_count(1), 0, "a ladder blocks nothing")
	t.eq(ladder.get_custom_data("ladder"), true)
	var spikes := src.get_tile_data(Vector2i(2, 0), 0)
	t.eq(spikes.get_custom_data("hazard"), true)
	t.eq(spikes.get_collision_polygons_count(0), 0)
	var block := src.get_tile_data(Vector2i(3, 0), 0)
	t.eq(block.get_custom_data("breakable"), true)
	t.eq(block.get_collision_polygons_count(0), 1, "a breakable block is solid ground")
	t.eq(block.get_custom_data("hazard"), false)
	# a second build changes nothing, and never adds a second polygon
	var first := _bytes()
	t.eq(_build_as(_catalog([sheet], sources), "metroidvania"), [])
	t.ok(_bytes() == first, "building again gives the same file")
	t.eq((_load().get_source(0) as TileSetAtlasSource).get_tile_data(Vector2i(0, 0), 0).get_collision_polygons_count(1), 1)
	_cleanup()

func test_a_sheets_side_view_tags_decide_its_tiles(t) -> void:
	_cleanup()
	var planks := _asset("t.a")
	planks["detected"] = {"usage": "tiles", "role": "DECORATION", "tags": ["one_way"], "grid": {"cell": [32, 32], "margin": [0, 0], "separation": [0, 0]}}
	var spikes := _asset("t.b")
	spikes["detected"] = {"usage": "tiles", "role": "DECORATION", "tags": ["hazard"], "grid": {"cell": [32, 32], "margin": [0, 0], "separation": [0, 0]}}
	var sources := [{"asset": "t.a", "source_id": 0}, {"asset": "t.b", "source_id": 1}]
	t.eq(_build_as(_catalog([planks, spikes], sources), "metroidvania"), [])
	var ts := _load()
	var plank := (ts.get_source(0) as TileSetAtlasSource).get_tile_data(Vector2i(0, 0), 0)
	t.ok(plank.get_collision_polygons_count(1) == 1 and plank.is_collision_polygon_one_way(1, 0))
	var spike := (ts.get_source(1) as TileSetAtlasSource).get_tile_data(Vector2i(0, 0), 0)
	t.eq(spike.get_custom_data("hazard"), true)
	t.eq(spike.get_collision_polygons_count(0), 0)
	_cleanup()

# ---------------------------------------------------------------- the MDS kind of decorations

const SideTileset := preload("res://builder/lib/side_tileset.gd")

func test_a_decoration_sheets_name_says_the_mds_kind_of_its_tiles(t) -> void:
	var deco := {"role": "DECORATION"}
	var none := {"profile": "NONE"}
	t.eq(SideTileset.name_words("res://p/mushroomRed2.png"), ["mushroom", "red"])
	t.eq(SideTileset.tile_kind(deco, {}, none, "res://p/grass_tufts.png"), "grass")
	t.eq(SideTileset.tile_kind(deco, {}, none, "res://p/Mushrooms.png"), "mushroom")
	t.eq(SideTileset.tile_kind(deco, {}, none, "res://p/stalactites_large.png"), "stalactite_large")
	t.eq(SideTileset.tile_kind({"role": "BACKGROUND"}, {}, none, "res://p/bg_leaves.png"), "foliage")
	t.eq(SideTileset.tile_kind(deco, {}, none, "res://p/flowers_and_mushrooms.png"), "", "a mixed sheet has none")
	t.eq(SideTileset.tile_kind(deco, {}, none, "res://p/decorations.png"), "", "a name that says no kind")
	t.eq(SideTileset.tile_kind({"role": "GROUND"}, {}, none, "res://p/grass.png"), "", "the ground called grass is no tuft")
	t.eq(SideTileset.tile_kind(deco, {}, {"profile": "FULL"}, "res://p/grass.png"), "", "a tile that collides has none")
	t.eq(SideTileset.tile_kind(deco, {"custom": {"hazard": true}}, none, "res://p/grass.png"), "", "nor a hazard")
	t.eq(SideTileset.tile_kind({"role": "GROUND"}, {"custom": {"mds_kind": "vine_top"}}, {"profile": "FULL"}, "res://p/x.png"), "vine_top", "a tile's own kind is always its")

func test_a_side_view_tileset_tags_decorations_for_mds_and_keeps_a_kind_set_in_godot(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	var sheet := _asset("t.a", "CONFIRMED", {"tile_overrides": {
		"0,0": {"custom": {"mds_kind": "vine_top"}},
		"1,0": {"collision": {"profile": "FULL"}},
	}})
	t.eq(_build_as(_catalog([sheet], sources), "metroidvania"), [])
	var ts := _load()
	t.ok(ts.get_custom_data_layer_by_name("mds_kind") >= 0)
	t.eq(ts.get_custom_data_layer_type(ts.get_custom_data_layer_by_name("mds_kind")), TYPE_STRING, "a String layer, as MDS makes it")
	var src := ts.get_source(0) as TileSetAtlasSource
	t.eq(src.get_tile_data(Vector2i(0, 0), 0).get_custom_data("mds_kind"), "vine_top")
	t.eq(src.get_tile_data(Vector2i(1, 0), 0).get_custom_data("mds_kind"), "", "a solid tile has none")
	# a kind given in Godot (MDS's palette Tag) to a tile the catalog says nothing of stays
	src.get_tile_data(Vector2i(1, 0), 0).set_custom_data("mds_kind", "fern")
	ResourceSaver.save(ts, TS_PATH)
	t.eq(_build_as(_catalog([sheet], sources), "metroidvania"), [])
	t.eq((_load().get_source(0) as TileSetAtlasSource).get_tile_data(Vector2i(1, 0), 0).get_custom_data("mds_kind"), "fern")
	_cleanup()

func test_a_side_view_tileset_without_decorations_has_no_mds_kind_layer(t) -> void:
	_cleanup()
	var sources := [{"asset": "t.a", "source_id": 0}]
	t.eq(_build_as(_catalog([_side_sheet("ONE_WAY", {"hazard": true})], sources), "metroidvania"), [])
	t.eq(_load().get_custom_data_layer_by_name("mds_kind"), -1)
	_cleanup()
