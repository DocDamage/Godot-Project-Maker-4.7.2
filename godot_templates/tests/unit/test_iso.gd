extends RefCounted
## Isometric maps and actors (T17.14): the arithmetic of RpgIso against the table of cases it
## shares with rpggen/core/iso_math.py and against Godot's own TileMapLayer; the seam the map
## recipes take their positions, shapes and tiles from (MapGeo), for squares and for diamonds;
## roads laid from the pieces' joins; an object of several cells cut in two so that an actor who
## walks round it is drawn behind it and in front of it at the right moments; the door of an
## isometric house and the room behind it; walking on diamonds with both control options;
## navigation; the cell an actor faces.

const Fixtures := preload("../lib/fixtures.gd")
const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const ObjectRecipe := preload("res://builder/recipes/object_scenes_recipe.gd")
const InteriorRecipe := preload("res://builder/recipes/interior_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const IsoTileset := preload("res://builder/lib/iso_tileset.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const MapBuild := preload("res://builder/lib/map_build.gd")
const ObjectEntries := preload("res://builder/lib/object_entries.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const CASES := "res://tests/unit/iso_math_cases.json"
const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const TS_PATH := "res://generated/tilesets/iso.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
const HOUSE_PICTURE := "res://tests/fixtures/iso_tiles/house.png"
const OUT := "user://test_iso_object.tscn"
const ROOM := "user://test_iso_room.tscn"
const FOOT := Vector2i(60, 34)
const UNIT := 34  # a step from a diamond of 60 x 34 to the next is 34.48 px
const GRASS := "iso_tiles.png.isotile_001_0"
const ROAD_STRAIGHT := "iso_tiles.png.isotile_010_"
const ROAD_CORNER := "iso_tiles.png.isotile_011_"
const WALL := "iso_tiles.png.isotile_019_0"

# ---------------------------------------------------------------- the arithmetic

static func _v(a: Array, i: int) -> Vector2:
	return Vector2(float(a[i]), float(a[i + 1]))

static func _vi(a: Array, i: int) -> Vector2i:
	return Vector2i(int(a[i]), int(a[i + 1]))

static func _pair(v: Variant) -> Array:
	if v is Vector2:
		var f: Vector2 = v
		return [f.x, f.y]
	var c: Vector2i = v
	return [c.x, c.y]

static func _call(fn: String, a: Array) -> Variant:
	match fn:
		"cell_to_screen":
			return _pair(RpgIso.cell_to_screen(_vi(a, 0), _vi(a, 2)))
		"grid_point":
			return _pair(RpgIso.grid_point(_v(a, 0), _vi(a, 2)))
		"screen_to_cell":
			return _pair(RpgIso.screen_to_cell(_v(a, 0), _vi(a, 2)))
		"depth":
			return RpgIso.depth(_vi(a, 0), _vi(a, 2))
		"diamond":
			var corners: Array = []
			for corner in RpgIso.diamond(_vi(a, 0), _vi(a, 2)):
				corners.append([corner.x, corner.y])
			return corners
		"neighbours":
			var cells: Array = []
			for cell in RpgIso.neighbours(_vi(a, 0)):
				cells.append([cell.x, cell.y])
			return cells
		"step":
			return _pair(RpgIso.step(str(a[0]), _vi(a, 1)))
		"unit":
			return RpgIso.unit(_vi(a, 0))
		"side_of":
			return RpgIso.side_of(_v(a, 0))
		"facing_of":
			return RpgIso.facing_of(_v(a, 0))
		"faced_side":
			return RpgIso.faced_side(str(a[0]), _v(a, 1))
		"faced_cell":
			return _pair(RpgIso.faced_cell(_vi(a, 0), str(a[2]), _v(a, 3)))
		"pad_vector":
			return _pair(RpgIso.pad_vector(_v(a, 0), str(a[2]), _vi(a, 3)))
		"pad_side":
			return RpgIso.pad_side(_v(a, 0), str(a[2]))
		"bounds":
			var rect := RpgIso.bounds(_vi(a, 0), _vi(a, 2))
			return [rect.position.x, rect.position.y, rect.size.x, rect.size.y]
		"sort_keys":
			var keys: Array = []
			keys.assign(RpgIso.sort_keys(Rect2i(_vi(a, 0), _vi(a, 2)), _vi(a, 4)))
			return keys
		"in_front":
			return RpgIso.in_front(_v(a, 0), Rect2i(_vi(a, 2), _vi(a, 4)), _vi(a, 6))
	return null

static func _same(got: Variant, want: Variant) -> bool:
	if got is Array and want is Array:
		var g: Array = got
		var w: Array = want
		if g.size() != w.size():
			return false
		for i in g.size():
			if not _same(g[i], w[i]):
				return false
		return true
	if (got is float or got is int) and (want is float or want is int):
		var a: float = got
		var b: float = want
		return absf(a - b) < 0.00011
	return typeof(got) == typeof(want) and got == want

func test_the_table_of_cases_rpggen_counts_by(t) -> void:
	var cases := JsonUtil.to_array(JsonUtil.read(CASES))
	t.ok(cases.size() > 2000, "the table is there (python -m rpggen.core.iso_math writes it)")
	var seen := {}
	var wrong := 0
	for raw: Variant in cases:
		var case := JsonUtil.to_dict(raw)
		var fn := str(case["fn"])
		seen[fn] = true
		var got: Variant = _call(fn, JsonUtil.to_array(case["args"]))
		if not _same(got, case["result"]):
			wrong += 1
			if wrong <= 5:
				t.fail("%s%s is %s here and %s there" % [fn, case["args"], got, case["result"]])
	t.eq(wrong, 0)
	t.eq(seen.size(), 17, "every function of iso_math has a case")

func _plain_tile_set(footprint: Vector2i) -> TileSet:
	var ts := TileSet.new()
	IsoTileset.shape(ts, footprint)
	return ts

func test_it_agrees_with_godots_own_grid(t) -> void:
	for footprint: Vector2i in [FOOT, Vector2i(64, 32), Vector2i(180, 104), Vector2i(120, 74), Vector2i(33, 17)]:
		var layer := TileMapLayer.new()
		layer.tile_set = _plain_tile_set(footprint)
		for cell: Vector2i in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1), Vector2i(7, 3), Vector2i(39, 23), Vector2i(-2, 5), Vector2i(4, -6)]:
			var middle := RpgIso.cell_to_screen(cell, footprint)
			t.eq(layer.map_to_local(cell), middle, "map_to_local of %s on %s" % [cell, footprint])
			t.eq(RpgIso.screen_to_cell(middle, footprint), cell)
			t.eq(layer.local_to_map(middle), cell)
			# a point most of the way to each corner, and to the middle of each side
			var corners := RpgIso.diamond(cell, footprint)
			for i in 4:
				var inside := middle + (corners[i] - middle) * 0.9
				t.eq(RpgIso.screen_to_cell(inside, footprint), cell, "towards corner %d of %s" % [i, cell])
				t.eq(layer.local_to_map(inside), cell)
				var edge := (corners[i] + corners[(i + 1) % 4]) / 2.0
				var beyond := middle + (edge - middle) * 1.2
				t.eq(RpgIso.screen_to_cell(beyond, footprint), layer.local_to_map(beyond), "across side %d of %s" % [i, cell])
				t.ok(RpgIso.screen_to_cell(beyond, footprint) != cell)
			for side in RpgIso.SIDES:
				var by: Vector2i = RpgIso.STEPS[side]
				t.eq(layer.map_to_local(cell + by) - middle, RpgIso.step(side, footprint), "one step %s" % side)
				t.eq(layer.local_to_map(middle + RpgIso.step(side, footprint)), cell + by)
		# asking a map: the layer answers for both views
		t.eq(RpgIso.footprint_of(layer), footprint)
		t.eq(RpgIso.cell_position(layer, Vector2i(3, 2)), RpgIso.cell_to_screen(Vector2i(3, 2), footprint))
		t.eq(RpgIso.cell_at(layer, RpgIso.cell_to_screen(Vector2i(3, 2), footprint)), Vector2i(3, 2))
		t.eq(RpgIso.map_unit(layer), RpgIso.unit(footprint))
		t.eq(RpgUtil.map_tile_px(layer), 16, "a layer alone is no map")
		var map := Node2D.new()
		map.add_child(layer)
		t.eq(RpgUtil.map_tile_px(map), RpgIso.unit(footprint), "a tile of an isometric map is one step on it")
		map.free()

func test_a_map_of_squares_is_asked_the_same_way(t) -> void:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	var map := Node2D.new()
	map.add_child(layer)
	t.eq(RpgIso.footprint_of(map), Vector2i.ZERO, "squares have no diamond")
	t.eq(RpgIso.map_unit(map), 16)
	t.eq(RpgUtil.map_tile_px(map), 16)
	t.eq(RpgIso.cell_position(map, Vector2i(3, 2)), Vector2(56, 40))
	t.eq(RpgIso.cell_at(map, Vector2(56, 40)), Vector2i(3, 2))
	t.eq(RpgIso.move_vector(map, Vector2(1, 0)), Vector2(1, 0), "the pad is the screen")
	t.eq(RpgIso.cell_ahead(map, Vector2(56, 40), "up"), Vector2i(3, 1))
	t.eq(RpgIso.cell_ahead(map, Vector2(56, 40), "right", Vector2(0, 5)), Vector2i(4, 2), "the facing alone says it")
	t.eq(RpgIso.cell_ahead(map, Vector2(56, 40), "down"), Vector2i(3, 3))
	t.eq(RpgIso.cell_ahead(map, Vector2(56, 40), "left"), Vector2i(2, 2))
	t.eq(RpgIso.reach_dir(map, "left"), Vector2.LEFT)
	t.eq(RpgIso.used_rect(layer, Rect2i(1, 2, 4, 3)), Rect2(16, 32, 64, 48))
	map.free()

# ---------------------------------------------------------------- the seam of the recipes

func _catalog() -> Dictionary:
	return JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)

func _context(cat: Dictionary, projection: String = "isometric", navigation: bool = false) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": projection, "features": {"navigation": navigation}, "seed": 7, "map_layers": MapUtil.DEFAULT_LAYERS.duplicate()}
	if projection != "isometric":
		ctx.config.erase("projection")
	ctx.catalog = CatalogReader.new(cat, projection)
	return ctx

func _cleanup() -> void:
	for p: String in [TS_PATH, STATE_PATH, PLAYER_SCENE, OUT, ROOM]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## The catalog of a pack without a wall (the fixture names one: its tile 019).
func _no_wall() -> Dictionary:
	var cat := _catalog()
	for raw: Variant in JsonUtil.to_array(cat["assets"]):
		var asset: Dictionary = raw
		if str(asset["id"]).begins_with("iso_tiles.png.isotile_019_"):
			asset.erase("overrides")
	return cat

## The catalog with what the synthetic pack does not say: a road in two pieces that name their
## sides (a straight and a corner, each one tile turned four ways of which the first is
## annotated, as the audit would), water, and a wall.
func _annotated() -> Dictionary:
	var cat := _catalog()
	for raw: Variant in JsonUtil.to_array(cat["assets"]):
		var asset: Dictionary = raw
		var id := str(asset["id"])
		if id.begins_with(ROAD_STRAIGHT):
			asset["overrides"] = {"role": "ROAD", "joins": ["n", "s"]} if id.ends_with("_0") else {"role": "ROAD"}
		elif id.begins_with(ROAD_CORNER):
			asset["overrides"] = {"role": "ROAD", "joins": ["e", "s"]} if id.ends_with("_0") else {"role": "ROAD"}
		elif id.begins_with("iso_tiles.png.isotile_002_"):
			asset["overrides"] = {"role": "WATER"}
		elif id.begins_with("iso_tiles.png.isotile_019_"):
			asset["overrides"] = {"role": "WALL"}
	return cat

func test_squares_keep_their_arithmetic(t) -> void:
	var cat := {"assets": [], "tilesets": [{"name": "overworld", "tile_size": [16, 16], "sources": []}]}
	var geo := MapGeo.new(_context(cat, "top_down"))
	t.ok(not geo.isometric and geo.iso == null)
	t.eq(geo.tile_px, 16)
	t.eq(geo.footprint, Vector2i(16, 16))
	t.eq(geo.tileset_path(), "res://generated/tilesets/overworld.tres")
	t.eq(geo.center(Vector2i(3, 2)), MapUtil.tile_center(Vector2i(3, 2), 16))
	t.eq(geo.center(Vector2i(3, 2)), Vector2(56, 40))
	t.eq(geo.foot(Vector2i(3, 2)), Vector2(56, 47), "the feet of a thing sit on the bottom row")
	t.eq(geo.bottom(Vector2i(3, 2)), Vector2(56, 48))
	t.eq(geo.step(Vector2(1, 0)), Vector2(16, 0))
	t.eq(geo.gate_position(Vector2i(3, 2)), Vector2(56, 48))
	t.eq((geo.cell_shape() as RectangleShape2D).size, Vector2(16, 16))
	t.eq(geo.cells_outline(Rect2i(12, 1, 19, 18)), PackedVector2Array([Vector2(192, 16), Vector2(496, 16), Vector2(496, 304), Vector2(192, 304)]))
	t.eq(MapGeo.tile_unit(_context(cat, "top_down")), 16)
	t.eq(MapGeo.tile_unit(_context({"assets": [], "tilesets": []}, "top_down")), 16, "no tile set: the config's base tile size")
	# the house of the sample pack: 80 x 64 px, its door at (40, 63)
	var house := {"region": [16, 16, 80, 64], "origin": [40, 63], "door": [40, 63]}
	t.eq(geo.building_info(house), {"size": [5, 4], "door": [2, 4]})
	t.eq(geo.building_position(house, Vector2i(8, 6)), Vector2(168, 159), "the corner of its cell plus its origin")
	# a pack of isometric tiles in a project seen from above paints nothing
	var mixed := MapGeo.new(_context(_catalog(), "top_down"))
	t.ok(not mixed.isometric and mixed.def.is_empty(), "the isometric tile set is nobody's in a top-down project")

func test_diamonds_through_the_same_seam(t) -> void:
	var ctx := _context(_catalog())
	t.ok(MapGeo.is_isometric(ctx))
	var geo := MapGeo.new(ctx)
	t.ok(geo.isometric and geo.iso != null)
	t.eq(geo.footprint, FOOT)
	t.eq(geo.tile_px, UNIT, "a tile is one step, not the width of the diamond")
	t.eq(MapGeo.tile_unit(ctx), UNIT)
	t.eq(geo.tileset_path(), TS_PATH)
	t.eq(JsonUtil.to_str(geo.def.get("name", "")), "iso")
	t.eq(MapGeo.new(ctx, "interior").def, geo.def, "an isometric project has one tile set, indoors too")
	# the camera: as it is while eight diamonds fit across the screen, drawn back when they do not
	t.eq(MapGeo.camera_zoom(ctx), 1.0, "60 px diamonds on a screen of 640")
	t.eq(MapGeo.camera_zoom(_context(_catalog(), "top_down")), 1.0)
	var large := _catalog()
	for raw: Variant in JsonUtil.to_array(large["tilesets"]):
		var def: Dictionary = raw
		def["tile_size"] = [180, 104]
	var large_ctx := _context(large)
	# eight diamonds of 180 px across would be 0.444; the zoom is the nearest at which a step of
	# the grid is whole px each way (T17.22: no sliver of a block's side between two faces)
	t.near(MapGeo.camera_zoom(large_ctx), 0.5, 0.0001, "diamonds of 180 x 104: 45 px and 26 px a step")
	t.near(MapGeo.whole_step_zoom(640.0 / (8 * 256), Vector2i(256, 128)), 0.3125, 0.0001, "a zoom that is whole already stays")
	t.near(MapGeo.whole_step_zoom(0.8, Vector2i(100, 65)), 0.8, 0.0001)
	t.near(MapGeo.whole_step_zoom(0.3, Vector2i(180, 104)), 0.5, 0.0001, "never no zoom at all")
	t.eq(MapGeo.whole_step_zoom(1.0, Vector2i(60, 34)), 1.0)
	t.eq(MapGeo.tile_unit(large_ctx), 104)
	# the text of the menus follows the config's base tile size, not the diamond
	var ThemeRecipe: GDScript = load("res://builder/recipes/theme_recipe.gd")
	large_ctx.config["base_tile_size"] = 16
	var theme_recipe: RefCounted = ThemeRecipe.new()
	t.eq(theme_recipe.call("_base_tile", large_ctx), 16)
	t.eq(geo.center(Vector2i(3, 2)), Vector2(60, 102))
	t.eq(geo.foot(Vector2i(3, 2)), geo.center(Vector2i(3, 2)), "a thing stands on the middle of its diamond")
	t.eq(geo.bottom(Vector2i(3, 2)), geo.center(Vector2i(3, 2)))
	t.eq(geo.step(Vector2(1, 0)), Vector2(30, 17))
	t.eq(geo.step(Vector2(0, 1)), Vector2(-30, 17))
	t.eq(geo.step(Vector2(0, 0.5)), Vector2(-15, 8.5))
	t.eq(geo.gate_position(Vector2i(3, 2)), geo.center(Vector2i(3, 2)))
	t.eq((geo.cell_shape() as ConvexPolygonShape2D).points, IsoTileset.diamond(FOOT))
	# the outline of a rectangle of cells: its top, right, bottom and left corner
	var outline := geo.cells_outline(Rect2i(2, 1, 3, 2))
	t.eq(outline, PackedVector2Array([Vector2(60, 51), Vector2(150, 102), Vector2(90, 136), Vector2(0, 85)]))
	for corner in outline:
		t.ok(Geometry2D.is_point_in_polygon(geo.center(Vector2i(3, 2)), outline), "a cell of it is inside")
	t.ok(not Geometry2D.is_point_in_polygon(geo.center(Vector2i(5, 1)), outline))
	t.ok(not Geometry2D.is_point_in_polygon(geo.center(Vector2i(2, 3)), outline))
	# tiles: the ground and three others to vary it with, flat ones before blocks
	var ground := geo.find_tile("GROUND")
	t.eq(ground.get("asset_id"), GRASS)
	t.eq(geo.tile_of_asset("iso_tiles.png.isotile_003_0").get("asset_id"), "iso_tiles.png.isotile_003_0")
	t.eq(geo.tile_of_asset("no.such.tile"), {})
	var others := geo.other_tiles(ground, 3)
	t.eq(others.size(), 3)
	t.eq(others[0].get("asset_id"), "iso_tiles.png.isotile_002_0", "the next tile, not a turn of the first")
	t.eq(geo.nth_tile_with_role("GROUND", 1).get("asset_id"), "iso_tiles.png.isotile_002_0")
	t.eq(geo.iso.plain_tiles("GROUND").size(), 18, "the six blocks that rise are no floor while there are flat tiles")
	t.eq(geo.find_tile("ROAD"), {}, "the pack names no road")
	t.eq(geo.wall_tile().get("asset_id"), WALL, "the fixture's wall: a block that rises")
	t.eq(MapGeo.new(_context(_no_wall())).wall_tile(), {})
	# a building: the cells it stands on, its door in front of the middle of its south side
	for case: Array in [[[1, 1], [0, 1]], [[2, 1], [0, 1]], [[3, 2], [1, 2]], [[2, 2], [0, 2]]]:
		var entry := {"iso": [60, 34], "stands_on": case[0], "region": [0, 0, 60, 64], "origin": [30, 39], "door": []}
		t.eq(geo.building_info(entry), {"size": case[0], "door": case[1]}, "%s" % [case[0]])
	var wide := {"iso": [60, 34], "stands_on": [3, 2], "origin": [30, 39]}
	t.eq(geo.building_position(wide, Vector2i(8, 6)), geo.center(Vector2i(10, 7)), "on the cell nearest the camera")

func test_roads_are_laid_from_the_pieces_that_name_their_sides(t) -> void:
	_cleanup()
	var ctx := _context(_annotated())
	t.eq(TilesetRecipe.new().build(ctx), [])
	var geo := MapGeo.new(ctx)
	var tile_set := geo.load_tile_set()
	t.ok(tile_set != null)
	var iso := geo.iso
	# what the pieces can do: a straight in two ways, a corner in four
	t.eq(iso.laid_pieces("ROAD").size(), 8)
	t.eq(iso.piece_for("ROAD", ["e", "w"]), {"asset_id": ROAD_STRAIGHT + "1", "turn": 1})
	t.eq(iso.piece_for("ROAD", ["n", "e"]), {"asset_id": ROAD_CORNER + "3", "turn": 3})
	t.eq(iso.piece_for("ROAD", ["n", "e", "s"]), {}, "the pack has no junction")
	t.eq(iso.nearest_piece("ROAD", ["s", "n"]), {"asset_id": ROAD_STRAIGHT + "0", "turn": 0, "wrong": 0})
	t.eq(iso.nearest_piece("ROAD", ["n", "e", "s"]), {"asset_id": ROAD_STRAIGHT + "0", "turn": 0, "wrong": 1}, "the fewest wrong sides, the first by id")
	t.eq(iso.nearest_piece("ROAD", ["s"]), {"asset_id": ROAD_STRAIGHT + "0", "turn": 0, "wrong": 1})
	t.eq(iso.nearest_piece("WATER", ["n"]), {}, "water that names no sides has no pieces")
	t.eq(IsoTileset.wrong_sides(["n", "s"], ["e", "w"]), 4)
	var road := geo.find_tile("ROAD")
	t.eq(road.get("asset_id"), ROAD_STRAIGHT + "0", "no plain road: the first piece stands for the kind")
	# a road from (2, 2) east to (5, 2), then south to (5, 5), and a branch east from (5, 4)
	var layer := TileMapLayer.new()
	layer.tile_set = tile_set
	var cells: Array[Vector2i] = []
	for x in range(2, 6):
		cells.append(Vector2i(x, 2))
	for y in range(3, 6):
		cells.append(Vector2i(5, y))
	var branch: Array[Vector2i] = [Vector2i(5, 4), Vector2i(6, 4), Vector2i(7, 4)]
	geo.paint_runs(layer, [cells, branch], "ROAD", road)
	var want := {
		Vector2i(2, 2): ROAD_STRAIGHT + "1",  # an end: e only, the straight e-w is one side off
		Vector2i(3, 2): ROAD_STRAIGHT + "1",  # e and w
		Vector2i(5, 2): ROAD_CORNER + "1",  # s and w
		Vector2i(5, 3): ROAD_STRAIGHT + "0",  # n and s
		Vector2i(5, 4): ROAD_STRAIGHT + "0",  # n, e and s: no junction, the straight is nearest
		Vector2i(6, 4): ROAD_STRAIGHT + "1",
		Vector2i(5, 5): ROAD_STRAIGHT + "0",  # an end
	}
	for cell: Vector2i in want.keys():
		t.eq(layer.get_cell_tile_data(cell).get_custom_data("asset_id"), want[cell], "the piece at %s" % cell)
	t.eq(layer.get_used_cells().size(), 9, "two runs that meet are one road")
	var notes := geo.take_notes()
	t.eq(notes.size(), 1, "one note for the map, not one a cell")
	t.ok(notes[0].begins_with("road: 4 cells"), notes[0])
	t.eq(geo.take_notes().size(), 0, "said once")
	# water without pieces is its plain tile, cell by cell; nothing is laid without a tile
	var water := geo.find_tile("WATER")
	t.eq(water.get("asset_id"), "iso_tiles.png.isotile_002_0")
	geo.fill_joined(layer, Rect2i(10, 10, 2, 2), "WATER", water)
	t.eq(layer.get_cell_tile_data(Vector2i(11, 11)).get_custom_data("asset_id"), "iso_tiles.png.isotile_002_0")
	t.ok(layer.get_cell_tile_data(Vector2i(11, 11)).get_custom_data("water"))
	geo.paint_joined(layer, [Vector2i(20, 20)], "BRIDGE", {})
	t.eq(layer.get_cell_source_id(Vector2i(20, 20)), -1)
	t.eq(geo.take_notes().size(), 0)
	layer.free()
	_cleanup()

func test_the_blocked_edge_of_a_map(t) -> void:
	_cleanup()
	# with a wall tile: on the Y-sorted Props layer, where it blocks by its own diamond
	var ctx := _context(_annotated())
	t.eq(TilesetRecipe.new().build(ctx), [])
	var geo := MapGeo.new(ctx)
	var tile_set := geo.load_tile_set()
	var root := MapUtil.new_map_root("Test", "test")
	var nodes := MapUtil.build_layers(root, MapUtil.DEFAULT_LAYERS, tile_set)
	var gap := Vector2i(5, 2)
	geo.paint_walls(root, nodes, Vector2i(6, 5), [gap])
	var props: TileMapLayer = nodes["Props"]
	var ground: TileMapLayer = nodes["Ground"]
	# the near sides (the last row and the last column) sort with who walks behind them; the far
	# sides lie in the place of the ground, whose tiles before them cover the earth under them
	# (T17.18: over the ground it was a brown footing along the two far walls)
	t.eq(props.get_used_cells().size(), 5 + 3 - 1, "the near sides, without the gap")
	t.eq(ground.get_used_cells().size(), 6 + 4, "the far sides: the first row and the first column")
	t.eq(props.get_cell_source_id(gap), -1)
	t.eq(ground.get_cell_source_id(gap), -1)
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(5, 0), Vector2i(0, 4), Vector2i(0, 2), Vector2i(3, 0)]:
		t.eq(ground.get_cell_tile_data(cell).get_custom_data("asset_id"), WALL, "%s is a far wall" % cell)
		t.eq(props.get_cell_source_id(cell), -1)
	for cell: Vector2i in [Vector2i(5, 4), Vector2i(1, 4), Vector2i(5, 1), Vector2i(5, 3)]:
		t.eq(props.get_cell_tile_data(cell).get_custom_data("asset_id"), WALL, "%s is a near wall" % cell)
		t.eq(props.get_cell_tile_data(cell).get_collision_polygons_count(0), 1)
		t.eq(ground.get_cell_source_id(cell), -1)
	t.ok(props.y_sort_enabled and props.collision_enabled, "a wall rises: it is sorted with who stands by it")
	# the tiles of the near sides block; the ground's layer blocks nothing, so the far walls
	# keep their diamonds as unseen shapes
	var unseen := root.get_node_or_null("BorderCollision") as StaticBody2D
	t.ok(unseen != null and not ground.collision_enabled)
	t.eq(unseen.get_child_count(), 6 + 4, "a diamond for every far wall, and for no other")
	t.ok(unseen.get_node_or_null("Wall_0_0") != null and unseen.get_node_or_null("Wall_0_4") != null and unseen.get_node_or_null("Wall_5_4") == null)
	root.free()
	# without one: an invisible diamond a cell
	var bare_ctx := _context(_no_wall())
	var bare := MapGeo.new(bare_ctx)
	bare.load_tile_set()
	var plain_root := MapUtil.new_map_root("Test", "test")
	var plain_nodes := MapUtil.build_layers(plain_root, MapUtil.DEFAULT_LAYERS, tile_set)
	bare.paint_walls(plain_root, plain_nodes, Vector2i(6, 5), [gap])
	var body := plain_root.get_node("BorderCollision") as StaticBody2D
	t.eq(body.get_child_count(), 17)
	t.ok(body.get_node_or_null("Wall_5_2") == null, "the gap is open")
	var corner := body.get_node("Wall_5_4") as CollisionShape2D
	t.eq(corner.position, RpgIso.cell_to_screen(Vector2i(5, 4), FOOT))
	t.eq((corner.shape as ConvexPolygonShape2D).points, IsoTileset.diamond(FOOT))
	# the door of a map's edge is a diamond on its cell
	var triggers: Node2D = plain_nodes["Triggers"]
	var door := bare.add_exit_door(triggers, plain_root, "east_exit", gap, "res://game/maps/field_1.tscn", &"west_entry")
	t.eq(door.position, RpgIso.cell_to_screen(gap, FOOT))
	t.eq(((door.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, IsoTileset.diamond(FOOT))
	t.eq(door.get("target_spawn"), &"west_entry")
	plain_root.free()
	_cleanup()

# ---------------------------------------------------------------- objects, sorting, doors

func _house(stands_on: Array, role: String = "BUILDING") -> Dictionary:
	return {
		"id": "pack.house", "name": "house", "role": role, "tags": [],
		"texture_path": HOUSE_PICTURE, "region": [0, 0, 60, 64], "origin": [30, 39],
		"footprint": [], "collision": {"profile": "NONE"}, "door": [], "sha256": "", "open_region": [],
		"iso": [60, 34], "stands_on": stands_on,
	}

func _built(entry: Dictionary) -> Node2D:
	var err: int = ObjectRecipe.new()._build_scene(entry, OUT, UNIT)
	if err != OK:
		return null
	return (ResourceLoader.load(OUT, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate() as Node2D

## What the sort keys say about an actor whose feet are at `at`: for each half of the object the
## actor overlaps, 1 when the actor is drawn after it (in front), -1 before it.
func _drawn(house: Node2D, at: Vector2) -> Array[int]:
	var out: Array[int] = []
	var left := house.get_node("Sprite") as Sprite2D
	var right := house.get_node_or_null("SpriteRight") as Sprite2D
	var halves: Array[Sprite2D] = []
	if right == null:
		halves.append(left)
	else:
		if at.x <= house.position.x:
			halves.append(left)
		if at.x >= house.position.x:
			halves.append(right)
	for half in halves:
		var key := house.position.y + half.position.y
		out.append(1 if at.y > key else (-1 if at.y < key else 0))
	return out

func test_an_actor_who_walks_round_a_house_is_drawn_behind_it_and_in_front_of_it(t) -> void:
	_cleanup()
	for size: Vector2i in [Vector2i(1, 1), Vector2i(2, 2), Vector2i(2, 1), Vector2i(1, 2), Vector2i(3, 2), Vector2i(2, 3), Vector2i(4, 2)]:
		var entry := _house([size.x, size.y])
		var house := _built(entry)
		t.ok(house != null, "the scene of a house on %s cells" % size)
		if house == null:
			continue
		var first := Vector2i(8, 6)  # the plan's cell of its top-left corner
		var cells := Rect2i(first, size)
		house.position = RpgIso.cell_to_screen(first + size - Vector2i.ONE, FOOT)
		# what blocks is what it stands on: nobody walks where the keys would be wrong
		var footprint := (house.get_node("Footprint") as CollisionPolygon2D).polygon
		t.eq(footprint, IsoTileset.outline(size, FOOT), "it blocks the cells it stands on")
		var keys := RpgIso.sort_keys(cells, FOOT)
		var left := house.get_node("Sprite") as Sprite2D
		var right := house.get_node_or_null("SpriteRight") as Sprite2D
		t.near(house.position.x, keys[0], 0.001, "it is cut at the corner nearest the camera")
		t.near(house.position.y + left.position.y, keys[1], 0.001, "the left half sorts by the left corner")
		if size.x == size.y:
			t.ok(right == null, "a square of cells is one picture")
			t.near(keys[1], keys[2], 0.001)
			t.eq(left.offset + left.position, Vector2(-30, -39), "the picture lies where it lay")
			t.eq(house.y_sort_enabled, size != Vector2i.ONE, "a picture that is moved from its root sorts by itself")
		else:
			t.ok(house.y_sort_enabled, "the halves are sorted among the actors of the map")
			t.near(house.position.y + right.position.y, keys[2], 0.001, "the right half sorts by the right corner")
			t.eq((left.texture as AtlasTexture).region, Rect2(0, 0, 30, 64))
			t.eq((right.texture as AtlasTexture).region, Rect2(30, 0, 30, 64))
			t.eq(left.offset + left.position, Vector2(-30, -39), "the left half lies where the picture lay")
			t.eq(right.offset + right.position, Vector2(0, -39), "... and the right half beside it")
		# every point of the ground two cells around it, a quarter of a cell apart
		var checked := 0
		var wrong := 0
		for iy in range(-8, size.y * 4 + 9):
			for ix in range(-8, size.x * 4 + 9):
				var g := Vector2(first.x + ix / 4.0, first.y + iy / 4.0)
				var at := Vector2((g.x - g.y + 1) * FOOT.x / 2.0, (g.x + g.y) * FOOT.y / 2.0)
				var truth := RpgIso.in_front(at, cells, FOOT)
				if truth == 0 or (g.x >= first.x and g.x <= first.x + size.x and g.y >= first.y and g.y <= first.y + size.y):
					continue  # beside it, where neither hides the other; or on it, where nobody stands
				checked += 1
				for seen in _drawn(house, at):
					if seen != truth:
						wrong += 1
						if wrong <= 3:
							t.fail("%s cells: at %s the actor is %s and is drawn %s" % [size, g, truth, seen])
		t.ok(checked > 150, "%d points were asked" % checked)
		t.eq(wrong, 0, "%s cells" % size)
		# the walk round it, cell by cell: behind on its north and west, in front on its south and east
		var behind := first + Vector2i(0, -1)
		var before := first + Vector2i(size.x - 1, size.y)
		t.eq(_drawn(house, RpgIso.cell_to_screen(behind, FOOT)).max(), -1, "north of it: behind")
		t.eq(_drawn(house, RpgIso.cell_to_screen(first + Vector2i(-1, 0), FOOT)).max(), -1, "west of it: behind")
		t.eq(_drawn(house, RpgIso.cell_to_screen(before, FOOT)).min(), 1, "south of it: in front")
		t.eq(_drawn(house, RpgIso.cell_to_screen(first + Vector2i(size.x, size.y - 1), FOOT)).min(), 1, "east of it: in front")
		t.eq(house.get_meta("iso"), [60, 34])
		t.eq(house.get_meta("stands_on"), [size.x, size.y])
		house.free()
	# a tree: one cell, an obstacle that stands on the middle of its diamond
	var tree := _built(_house([1, 1], "DECORATION"))
	t.ok(tree is StaticBody2D, "what stands on a diamond blocks it")
	t.ok(tree.get_node_or_null("SpriteRight") == null and not tree.y_sort_enabled)
	t.eq((tree.get_node("Sprite") as Sprite2D).position, Vector2.ZERO)
	t.eq((tree.get_node("Footprint") as CollisionPolygon2D).polygon, IsoTileset.diamond(FOOT))
	tree.free()
	_cleanup()

func test_cells_under_an_object(t) -> void:
	var under := IsoTileset.cells_under(Vector2i(10, 7), {"stands_on": [3, 2]})
	t.eq(under.size(), 6)
	for cell: Vector2i in [Vector2i(8, 6), Vector2i(10, 7), Vector2i(8, 7), Vector2i(10, 6)]:
		t.ok(under.has(cell), "%s is under it" % cell)
	t.eq(IsoTileset.cells_under(Vector2i(4, 4), {}), [Vector2i(4, 4)] as Array[Vector2i])
	t.eq(IsoTileset.stands_on({"stands_on": [0, 2]}), Vector2i(1, 2))
	# the outline of what a 3 x 2 object stands on, around the middle of its nearest cell
	t.eq(IsoTileset.outline(Vector2i(3, 2), FOOT), PackedVector2Array([Vector2(-30, -68), Vector2(60, -17), Vector2(0, 17), Vector2(-90, -34)]))
	var at := RpgIso.cell_to_screen(Vector2i(10, 7), FOOT)
	var polygon := PackedVector2Array()
	for corner in IsoTileset.outline(Vector2i(3, 2), FOOT):
		polygon.append(corner + at)
	for cell in under:
		t.ok(Geometry2D.is_point_in_polygon(RpgIso.cell_to_screen(cell, FOOT), polygon), "%s lies in the outline" % cell)
	for cell: Vector2i in [Vector2i(7, 6), Vector2i(11, 7), Vector2i(9, 8), Vector2i(9, 5)]:
		t.ok(not Geometry2D.is_point_in_polygon(RpgIso.cell_to_screen(cell, FOOT), polygon), "%s does not" % cell)

func _walker() -> RpgActor:
	var actor := ActorBuild.build("base", "Walker", null, Vector2i(24, 36), Vector2i(12, 35), UNIT) as RpgActor
	actor.set_collision_layer_value(2, true)  # found as the player is
	return actor

func _frames(n: int) -> void:
	for i in n:
		await Fixtures.tree().physics_frame

func test_the_door_of_a_house_faces_the_camera(t) -> void:
	_cleanup()
	var geo := MapGeo.new(_context(_catalog()))
	for size: Vector2i in [Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 2)]:
		var entry := _house([size.x, size.y])
		var info := geo.building_info(entry)
		var house := _built(entry)
		var first := Vector2i(8, 6)
		house.position = geo.building_position(entry, first)
		var door_cell := first + Vector2i(int(info["door"][0]), int(info["door"][1]))
		t.eq(door_cell.y, first.y + size.y, "the plan's door cell is south of what the house stands on")
		var exit_spawn := house.get_node("ExitSpawn") as Marker2D
		t.eq(house.position + exit_spawn.position, geo.center(door_cell), "who comes out stands on the door cell")
		t.eq(exit_spawn.get("facing"), "down")
		t.eq(exit_spawn.get("spawn_id"), &"pack__house_exit")
		# the trigger lies along the side between the door cell and the house, just outside it
		var entrance := house.get_node("Entrance") as Area2D
		var side := (geo.center(door_cell) + geo.center(door_cell + Vector2i(0, -1))) / 2.0
		t.ok((house.position + entrance.position).distance_to(side) < 2.5, "on the south side of %s" % size)
		t.eq(RpgIso.screen_to_cell(house.position + entrance.position, FOOT), door_cell, "outside the house")
		var band := entrance.get_node("Shape") as CollisionShape2D
		t.near(band.rotation, Vector2(30, 17).angle(), 0.0001, "along the side")
		t.eq((band.shape as RectangleShape2D).size, Vector2(UNIT * 0.6, 6.0))
		t.eq(entrance.collision_mask, 2, "the player")
		house.free()
	# in a running world: nobody is sent back in on coming out, and walking against the door enters
	var world := Node2D.new()
	Fixtures.tree().root.add_child(world)
	var built := _built(_house([2, 1]))
	built.position = geo.building_position(_house([2, 1]), Vector2i(8, 6))
	(built.get_node("Entrance") as Area2D).set("target_map", "")  # it leads nowhere here
	world.add_child(built)
	var walker := _walker()
	world.add_child(walker)
	var door := Vector2i(8, 7)
	walker.position = geo.center(door)
	await _frames(4)
	var entrance_area := built.get_node("Entrance") as Area2D
	t.eq(entrance_area.get_overlapping_bodies().size(), 0, "on the door cell the door is not touched")
	var entered := false
	for i in 90:
		walker.move_dir(RpgIso.step("n", FOOT).normalized())
		await Fixtures.tree().physics_frame
		if entrance_area.get_overlapping_bodies().has(walker):
			entered = true
			break
	walker.move_dir(Vector2.ZERO)
	t.ok(entered, "walking north from the door cell reaches the door")
	t.eq(RpgIso.screen_to_cell(walker.position, FOOT), door, "... from outside: the house blocks")
	world.queue_free()
	await _frames(2)
	_cleanup()

func test_the_room_behind_the_door(t) -> void:
	_cleanup()
	var ctx := _context(_no_wall())
	t.eq(TilesetRecipe.new().build(ctx), [])
	var player := ActorBuild.build("player", "Player", null, Vector2i(24, 36), Vector2i(12, 35), UNIT)
	t.eq(SceneUtil.save_scene(player, PLAYER_SCENE), OK)
	var geo := MapGeo.new(ctx)
	var tile_set := geo.load_tile_set()
	# the room of a house of one cell: 10 by 8 cells, its exit in the south wall
	var spec: Dictionary = MapBuild.interiors_for(1, geo.building_info(_house([1, 1])))[0]
	t.eq(spec, {"id": "interior_1", "size": [10, 8], "door": 1})
	var size := Vector2i(10, 8)
	var exit_cell := Vector2i(1, 7)
	var issues: Array = []
	InteriorRecipe.new()._build_one(ctx, issues, 1, ROOM, &"pack__house_exit", geo, tile_set, size, exit_cell)
	t.eq(issues, [])
	var room := (ResourceLoader.load(ROOM, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate() as Node2D
	t.eq(room.get("is_interior"), true)
	var ground := room.get_node("Ground") as TileMapLayer
	t.ok(RpgIso.is_iso(ground.tile_set), "an isometric room")
	t.eq(ground.get_used_cells().size(), 80)
	t.eq(ground.get_cell_tile_data(Vector2i(4, 4)).get_custom_data("asset_id"), GRASS, "the floor is the project's ground")
	var edge := room.get_node("BorderCollision") as StaticBody2D
	t.eq(edge.get_child_count(), 10 * 2 + 6 * 2 - 1, "the pack has no wall: the edge blocks unseen")
	t.ok(edge.get_node_or_null("Wall_1_7") == null, "the way out is open")
	var exit_door := room.get_node("Triggers/Exit") as Area2D
	t.eq(exit_door.position, geo.center(exit_cell))
	t.eq(exit_door.get("target_map"), "res://game/maps/starter_map.tscn")
	t.eq(exit_door.get("target_spawn"), &"pack__house_exit", "back to the door of its house")
	t.eq(((exit_door.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, IsoTileset.diamond(FOOT))
	var spawn := room.get_node("SpawnPoints/default") as Marker2D
	t.eq(spawn.position, geo.center(Vector2i(1, 6)), "who comes in stands on the cell north of the way out")
	t.eq(spawn.get("facing"), "up")
	t.eq((room.get_node("YSorted/Entities/Player") as Node2D).position, spawn.position)
	t.eq((room as RpgMapRoot).used_rect_px(), RpgIso.bounds(size, FOOT), "the camera's rectangle is the one around the diamonds")
	room.free()
	_cleanup()

# ---------------------------------------------------------------- walking

func _ground(parent: Node, size: Vector2i, navigation: bool = false, holes: Array = []) -> TileMapLayer:
	var ctx := _context(_catalog(), "isometric", navigation)
	TilesetRecipe.new().build(ctx)
	var geo := MapGeo.new(ctx)
	var layer := TileMapLayer.new()
	layer.name = "Ground"
	layer.tile_set = geo.load_tile_set()
	var tile := geo.find_tile("GROUND")
	for y in size.y:
		for x in size.x:
			if not holes.has(Vector2i(x, y)):
				MapUtil.put(layer, Vector2i(x, y), tile)
	parent.add_child(layer)
	return layer

func _controls(value: Variant) -> void:
	ProjectSettings.set_setting(RpgIso.CONTROLS_SETTING, value)

func test_walking_on_diamonds_with_both_controls(t) -> void:
	_cleanup()
	var map := MapUtil.new_map_root("Test", "test")
	Fixtures.tree().root.add_child(map)
	var ground := _ground(map, Vector2i(12, 12))
	var walker := _walker()
	map.add_child(walker)
	var start := Vector2i(5, 5)
	t.eq(walker.map_node(), map, "an actor finds its map")
	# the pad, as the player's input component turns it
	var pad := RpgPlayerInput.new()
	pad.actor = walker
	_controls(null)
	t.eq(RpgIso.controls(), "screen", "up is up on the screen unless the project says otherwise")
	t.eq(pad.pad(Vector2.RIGHT), Vector2.RIGHT)
	t.eq(pad.pad(Vector2.UP), Vector2.UP)
	_controls("grid")
	t.eq(RpgIso.controls(), "grid")
	var east := RpgIso.step("e", FOOT).normalized()
	t.ok(pad.pad(Vector2.RIGHT).distance_to(east) < 0.0001, "right follows the diamond's east axis")
	t.ok(pad.pad(Vector2.UP).distance_to(RpgIso.step("n", FOOT).normalized()) < 0.0001, "up its north axis")
	t.ok(pad.pad(Vector2.DOWN).distance_to(RpgIso.step("s", FOOT).normalized()) < 0.0001)
	t.ok(pad.pad(Vector2.LEFT).distance_to(RpgIso.step("w", FOOT).normalized()) < 0.0001)
	t.eq(pad.pad(Vector2.ZERO), Vector2.ZERO)
	# grid controls: one direction held walks along a row of cells, a cell every `unit` px
	var steps := RpgEncounterSteps.new()
	steps.tile_px = RpgEncounterSteps.tile_of(map)
	t.eq(steps.tile_px, float(UNIT))
	for case: Array in [[Vector2.RIGHT, "e"], [Vector2.DOWN, "s"], [Vector2.LEFT, "w"], [Vector2.UP, "n"]]:
		var input: Vector2 = case[0]
		var side: String = case[1]
		var by: Vector2i = RpgIso.STEPS[side]
		walker.position = RpgIso.cell_to_screen(start, FOOT)
		steps.reset()
		steps.walk(walker.position)
		t.eq(RpgIso.pad_side(input, "grid"), side)
		var counted := 0
		var cells: Array[Vector2i] = [walker.map_cell()]
		for i in 78:  # three cells at 80 px a second: 103.4 px
			walker.move_dir(pad.pad(input))
			await Fixtures.tree().physics_frame
			counted += steps.walk(walker.position)
			if walker.map_cell() != cells[cells.size() - 1]:
				cells.append(walker.map_cell())
		walker.move_dir(Vector2.ZERO)
		await Fixtures.tree().physics_frame
		t.eq(cells, [start, start + by, start + by * 2, start + by * 3] as Array[Vector2i], "%s steps from diamond to diamond" % side)
		t.ok(walker.position.distance_to(RpgIso.cell_to_screen(start + by * 3, FOOT)) < 2.0, "three steps %s end on the middle of the third cell" % side)
		t.eq(counted, 3, "a step is a cell")
		t.eq(walker.cell_ahead(), start + by * 4, "it faces the next cell of its row")
	# screen controls: right is right on the screen, across the corners of the diamonds
	_controls("screen")
	walker.position = RpgIso.cell_to_screen(start, FOOT)
	for i in 45:  # the width of a diamond: 60 px
		walker.move_dir(pad.pad(Vector2.RIGHT))
		await Fixtures.tree().physics_frame
	walker.move_dir(Vector2.ZERO)
	await Fixtures.tree().physics_frame
	t.near(walker.position.y, RpgIso.cell_to_screen(start, FOOT).y, 0.01, "it keeps its height on the screen")
	t.eq(walker.map_cell(), start + Vector2i(1, -1), "a diamond to the right is one east and one north")
	t.eq(RpgIso.pad_side(Vector2.RIGHT, "screen"), "e")
	_controls(null)
	pad.free()
	map.queue_free()
	await _frames(2)
	_cleanup()

func test_the_cell_an_actor_faces(t) -> void:
	_cleanup()
	var map := MapUtil.new_map_root("Test", "test")
	var ground := _ground(map, Vector2i(8, 8))
	var actor := _walker()
	map.add_child(actor)
	actor.position = RpgIso.cell_to_screen(Vector2i(3, 4), FOOT)
	t.eq(actor.map_cell(), Vector2i(3, 4), "asked of the map, outside a tree too")
	# a facing alone: up n, right e, down s, left w
	for case: Array in [["up", Vector2i(3, 3)], ["right", Vector2i(4, 4)], ["down", Vector2i(3, 5)], ["left", Vector2i(2, 4)]]:
		actor.facing = case[0]
		t.eq(actor.cell_ahead(), case[1], "facing %s" % [case[0]])
		t.eq(RpgIso.cell_ahead(map, actor.position, str(case[0])), case[1])
	# where it last went says more: the neighbour in that quarter of the screen
	for case: Array in [[Vector2(30, -17), "right", Vector2i(3, 3)], [Vector2(30, 17), "right", Vector2i(4, 4)], [Vector2(-30, 17), "left", Vector2i(3, 5)], [Vector2(-30, -17), "left", Vector2i(2, 4)], [Vector2(2, -9), "up", Vector2i(3, 3)], [Vector2(-2, -9), "up", Vector2i(2, 4)]]:
		var look: Vector2 = case[0]
		t.eq(RpgIso.facing_of(look), case[1])
		t.eq(RpgIso.cell_ahead(map, actor.position, str(case[1]), look), case[2], "going %s" % look)
	# ... until something turns the actor (a spawn point): then the facing says it again
	t.eq(RpgIso.cell_ahead(map, actor.position, "down", Vector2(30, -17)), Vector2i(3, 5))
	# what it reaches for: the screen's direction, or with grid controls the neighbour's
	_controls(null)
	t.eq(RpgIso.reach_dir(map, "up"), Vector2.UP)
	_controls("grid")
	t.ok(RpgIso.reach_dir(map, "up").distance_to(RpgIso.step("n", FOOT).normalized()) < 0.0001)
	t.ok(RpgIso.reach_dir(map, "right", Vector2(30, -17)).distance_to(RpgIso.step("n", FOOT).normalized()) < 0.0001)
	_controls(null)
	t.eq(ground.get_used_cells().size(), 64)
	map.free()
	_cleanup()

func test_navigation_finds_a_way_over_the_diamonds_that_can_be_walked(t) -> void:
	_cleanup()
	var map := MapUtil.new_map_root("Test", "test")
	Fixtures.tree().root.add_child(map)
	# 9 by 7 cells with a wall of holes from the north edge down to row 4 in column 4
	var holes: Array = []
	for y in range(0, 5):
		holes.append(Vector2i(4, y))
	var ground := _ground(map, Vector2i(9, 7), true, holes)
	t.ok(ground.tile_set.get_navigation_layers_count() == 1, "features.navigation: the tile set has the layer")
	var polygon := ground.get_cell_tile_data(Vector2i(0, 0)).get_navigation_polygon(0)
	t.eq(polygon.vertices, IsoTileset.diamond(FOOT), "a ground tile can be walked over its diamond")
	var from := RpgIso.cell_to_screen(Vector2i(1, 1), FOOT)
	var to := RpgIso.cell_to_screen(Vector2i(7, 1), FOOT)
	var nav := map.get_world_2d().navigation_map
	var path := PackedVector2Array()
	for i in 20:  # the navigation map is made in a physics frame
		await Fixtures.tree().physics_frame
		path = NavigationServer2D.map_get_path(nav, from, to, true)
		if path.size() >= 2:
			break
	t.ok(path.size() >= 3, "a way round the holes (%d points)" % path.size())
	if path.size() >= 2:
		t.ok(path[0].distance_to(from) < 1.0 and path[path.size() - 1].distance_to(to) < 1.0, "from the one cell to the other")
		var lowest := 0
		var off := 0
		for i in path.size() - 1:
			for k in 9:  # along every leg: no point of it lies on a hole
				var at := path[i].lerp(path[i + 1], (k + 0.5) / 9.0)
				var cell := ground.local_to_map(at)
				lowest = maxi(lowest, cell.y)
				if ground.get_cell_source_id(cell) == -1:
					# on the very corner of a diamond the cell is a matter of rounding
					var near_floor := false
					for by: Vector2 in [Vector2(1.5, 0), Vector2(-1.5, 0), Vector2(0, 1.5), Vector2(0, -1.5)]:
						if ground.get_cell_source_id(ground.local_to_map(at + by)) != -1:
							near_floor = true
					if not near_floor:
						off += 1
		t.eq(off, 0, "the way keeps to the diamonds that are there")
		t.ok(lowest >= 5, "it goes round the south end of the holes")
	map.queue_free()
	await _frames(2)
	_cleanup()

func test_the_minimap_of_an_isometric_map_is_its_plan(t) -> void:
	_cleanup()
	var map := MapUtil.new_map_root("Test", "test")
	var ground := _ground(map, Vector2i(6, 4))
	var layers: Array[TileMapLayer] = [ground]
	var MinimapRecipe: GDScript = load("res://builder/recipes/minimap_recipe.gd")
	var texture: ImageTexture = MinimapRecipe.call("render_layers", layers)
	t.eq(texture.get_size(), Vector2(6, 4), "a pixel a cell, from above")
	t.ok(RpgMinimapData.is_isometric(texture))
	t.eq(RpgMinimapData.tile_of(texture), FOOT)
	t.ok(texture.get_image().get_pixel(5, 3).a > 0.9)
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(5, 0), Vector2i(0, 3), Vector2i(5, 3), Vector2i(2, 1)]:
		t.eq(RpgMinimapData.cell_at(texture, RpgIso.cell_to_screen(cell, FOOT)), cell, "the player's dot at %s" % cell)
	map.free()
	_cleanup()
