extends RefCounted
## T17.28: an isometric Tiled map imported into an isometric project. The catalog's map (as
## rpggen/core/catalog.py writes it: `iso_tiles` layers of asset ids) is built on the tile set of
## the isometric fixture pack (tests/fixtures/iso_tiles, a diamond of 60 x 34): each picture at
## its own turn, the first layer in its place is the Ground and the others sort with the
## entities, moved as far as Tiled moves them, the walls' cells blocked a diamond each, and the
## objects on the middle of their diamonds. A map of the other view is not built.

const ImportedMaps := preload("res://builder/recipes/imported_maps_recipe.gd")
const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const TS_PATH := "res://generated/tilesets/iso.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"
const FOOT := Vector2i(60, 34)
const FLOOR_E := "iso_tiles.png.isotile_001_1"  # the second turn of a ground tile
const FLOOR_S := "iso_tiles.png.isotile_001_2"
const UPPER := "iso_tiles.png.isotile_002_0"
const WALL := "iso_tiles.png.isotile_019_2"
const ONLY_MAPS := "iso_tiles.png.isotile_005_0"  # in the set for the map alone

func _catalog(maps: Array) -> Dictionary:
	var cat := JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)
	for raw: Variant in JsonUtil.to_array(cat["tilesets"]):
		var def: Dictionary = raw
		if JsonUtil.to_str(def.get("projection", "")) == "isometric":
			var tiles: Dictionary = def["tiles"]
			var entry: Dictionary = tiles[ONLY_MAPS]
			entry["maps_only"] = true
	cat["maps"] = maps
	return cat

func _context(maps: Array, projection: String = "isometric", selection: Dictionary = {}) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": projection, "features": {}, "imported_maps": selection, "map_layers": MapUtil.DEFAULT_LAYERS.duplicate()}
	ctx.catalog = CatalogReader.new(_catalog(maps), projection)
	return ctx

func _geo(ctx: BuildContext) -> MapGeo:
	TilesetRecipe.new().build(ctx)
	var geo := MapGeo.new(ctx)
	geo.load_tile_set()
	return geo

func _cleanup() -> void:
	for p: String in [TS_PATH, STATE_PATH]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

## A point object of Tiled in the middle of the cell (x, y) of a map whose diamond is `unit` px
## high: both axes of an isometric map are counted in that height.
func _object(object_name: String, kind: String, cell: Vector2i, unit: int, props: Dictionary = {}) -> Dictionary:
	return {"name": object_name, "type": kind, "x": (cell.x + 0.5) * unit, "y": (cell.y + 0.5) * unit, "w": 0, "h": 0, "props": props}

## A map of 4 x 3 cells on diamonds of 120 x 68 (twice the project's): a floor of the second turn
## of a tile with a row of its third turn, a second floor drawn 20 px higher with one tile on
## (3, 0), two walls on (0, 0) and (1, 0) (the second flipped in Tiled), a spawn on (2, 1) and a
## sign on (1, 2).
func _map(map_id: String, with_spawn: bool = true) -> Dictionary:
	var objects: Array = [_object("notice", "sign", Vector2i(1, 2), 68, {"text": "Hello"})]
	if with_spawn:
		objects.push_front(_object("start", "spawn", Vector2i(2, 1), 68))
	return {
		"id": map_id, "pack_id": "pk", "source": "", "format": "tiled", "tile_size": [120, 68], "size": [4, 3],
		"projection": "isometric", "walls": [WALL],
		"layers": [
			{"name": "Upper", "kind": "iso_tiles", "pictures": [UPPER], "cells": [[3, -1, 0], [1, 0, 0], [8, -1, 0]], "offset": [0, -20]},
			{"name": "Floor", "kind": "iso_tiles", "pictures": [FLOOR_E, FLOOR_S], "cells": [[8, 0, 0], [4, 1, 0]]},
			{"name": "Walls", "kind": "iso_tiles", "pictures": [WALL], "cells": [[1, 0, 0], [1, 0, 1], [10, -1, 0]]},
			{"name": "Objects", "kind": "objects", "objects": objects},
		],
	}

func _square(map_id: String) -> Dictionary:
	return {"id": map_id, "pack_id": "pk", "source": "", "format": "tiled", "tile_size": [16, 16], "size": [2, 2], "layers": []}

func test_the_layers_are_painted_with_each_picture_at_its_turn(t) -> void:
	var ctx := _context([_map("pk.sample")])
	var geo := _geo(ctx)
	t.ok(geo.isometric and geo.tile_set != null, "the fixture's tile set of diamonds")
	var built := ImportedMaps.iso_scene(ctx, geo, ctx.catalog.map_def("pk.sample"), "StarterMap", "starter_map")
	var root: Node2D = built["root"]
	var ground: TileMapLayer = root.get_node("Ground")
	t.eq(ground.get_used_cells().size(), 12, "the layer drawn in its place is the Ground")
	var east: Dictionary = geo.iso.tile_for(FLOOR_E, 1)
	var first: Dictionary = geo.iso.tile_for(FLOOR_E, 0)
	t.eq(ground.get_cell_atlas_coords(Vector2i(0, 0)), east["coords"], "the picture itself, not the first turn of its tile")
	t.ok(east["coords"] != first["coords"])
	t.eq(ground.get_cell_atlas_coords(Vector2i(3, 2)), geo.iso.tile_for(FLOOR_S, 2)["coords"])
	var upper: TileMapLayer = root.get_node("YSorted/Upper")
	t.eq(upper.get_used_cells(), [Vector2i(3, 0)])
	t.eq(upper.position, Vector2(0, -10), "moved as far as Tiled moves it, in the project's px")
	t.ok(upper.y_sort_enabled and upper.collision_enabled, "it sorts with who walks there")
	var walls: TileMapLayer = root.get_node("YSorted/Walls")
	t.eq(walls.get_used_cells().size(), 2, "a flipped cell is painted unflipped")
	var entities := root.get_node("YSorted/Entities")
	t.ok(walls.get_index() < entities.get_index() and upper.get_index() < entities.get_index())
	t.eq(walls.get_cell_alternative_tile(Vector2i(1, 0)), 0)
	root.free()
	_cleanup()

func test_the_walls_block_their_diamonds_and_the_objects_stand_on_theirs(t) -> void:
	var ctx := _context([_map("pk.sample")])
	var geo := _geo(ctx)
	var built := ImportedMaps.iso_scene(ctx, geo, ctx.catalog.map_def("pk.sample"), "StarterMap", "starter_map")
	var root: Node2D = built["root"]
	var body: StaticBody2D = root.get_node(ImportedMaps.ISO_WALLS)
	var shapes := body.get_children()
	t.eq(shapes.size(), 2)
	t.eq((shapes[0] as Node2D).position, RpgIso.cell_to_screen(Vector2i(0, 0), FOOT))
	t.eq((shapes[1] as Node2D).position, RpgIso.cell_to_screen(Vector2i(1, 0), FOOT))
	var shape: CollisionShape2D = shapes[0]
	t.ok(shape.shape is ConvexPolygonShape2D, "a diamond")
	var spawn: Marker2D = root.get_node("SpawnPoints/default")
	t.eq(spawn.position, RpgIso.cell_to_screen(Vector2i(2, 1), FOOT), "the middle of the spawn's diamond")
	t.eq(root.get_node("SpawnPoints/start").position, spawn.position)
	t.eq(built["default"], spawn.position)
	var sign_marker: Marker2D = root.get_node("SpawnPoints/Sign_notice")
	t.eq(sign_marker.position, RpgIso.cell_to_screen(Vector2i(1, 2), FOOT))
	t.eq(sign_marker.get_meta("text"), "Hello")
	root.free()
	# without a spawn the player stands on the free floor cell nearest the middle of the floor
	var bare := _context([_map("pk.bare", false)])
	var geo2 := _geo(bare)
	var built2 := ImportedMaps.iso_scene(bare, geo2, bare.catalog.map_def("pk.bare"), "Bare", "bare")
	var root2: Node2D = built2["root"]
	t.eq(built2["default"], RpgIso.cell_to_screen(Vector2i(1, 1), FOOT))
	root2.free()
	_cleanup()

func test_the_free_floor_cell_and_the_cells_of_objects(t) -> void:
	var floor_cells := {}
	for y in 3:
		for x in 4:
			floor_cells[Vector2i(x, y)] = true
	t.eq(ImportedMaps.free_floor_cell(floor_cells, {}, Vector2i(9, 9)), Vector2i(1, 1), "of the nearest, the first by row")
	t.eq(ImportedMaps.free_floor_cell(floor_cells, {Vector2i(1, 1): true}, Vector2i(9, 9)), Vector2i(2, 1))
	t.eq(ImportedMaps.free_floor_cell({}, {}, Vector2i(9, 7)), Vector2i(4, 3), "the middle of a map without floor")
	t.eq(ImportedMaps.object_cell({"x": 100.0, "y": 40.0, "w": 0, "h": 0}, Vector2i(64, 32)), Vector2i(3, 1))
	t.eq(ImportedMaps.object_cell({"x": 32.0, "y": 32.0, "w": 64, "h": 32}, Vector2i(64, 32)), Vector2i(2, 1), "its middle decides")
	t.eq(ImportedMaps.sorted_cells({Vector2i(2, 1): true, Vector2i(0, 2): true, Vector2i(1, 1): true}), [Vector2i(1, 1), Vector2i(2, 1), Vector2i(0, 2)])
	var raised: Array = [{"kind": "iso_tiles", "offset": [0, -78]}, {"kind": "objects"}, {"kind": "iso_tiles", "offset": [4, 0]}]
	t.eq(ImportedMaps.ground_layer_index(raised), 0, "every layer moved: the first")
	raised.append({"kind": "iso_tiles"})
	t.eq(ImportedMaps.ground_layer_index(raised), 3, "the first in its place")
	t.eq(ImportedMaps.layer_offset({"offset": [3, -7]}), Vector2(3, -7))
	t.eq(ImportedMaps.layer_offset({}), Vector2.ZERO)

func test_a_map_of_the_other_view_is_not_built(t) -> void:
	var maps: Array = [_map("pk.diamonds"), _square("pk.squares")]
	var both := {"include": ["pk.diamonds", "pk.squares"], "starter": "pk.diamonds"}
	var iso := _context(maps, "isometric", both)
	t.ok(ImportedMaps.fits(iso, maps[0]) and not ImportedMaps.fits(iso, maps[1]))
	t.eq(ImportedMaps.starter_map(iso)["id"], "pk.diamonds")
	t.eq(ImportedMaps.extra_maps(iso).size(), 0, "the map of squares is not built on diamonds")
	t.eq(ImportedMaps.resolve_target(iso, "squares"), "", "and no door leads to it")
	var top := _context(maps, "top_down", both)
	t.ok(ImportedMaps.starter_map(top).is_empty(), "the starter is planned as without one")
	var extra := ImportedMaps.extra_maps(top)
	t.eq(extra.size(), 1)
	t.eq(extra[0]["id"], "pk.squares")
	t.eq(ImportedMaps.map_projection(maps[0]), "isometric")
	t.eq(ImportedMaps.map_projection(maps[1]), "top_down")

func test_a_picture_in_the_set_for_a_map_alone_is_painted_by_no_plan(t) -> void:
	var ctx := _context([])
	var geo := _geo(ctx)
	t.ok(geo.iso.maps_only(ONLY_MAPS))
	t.ok(not geo.iso.plain_tiles("GROUND").has(ONLY_MAPS))
	t.ok(not geo.iso.pieces("").has(ONLY_MAPS))
	t.ok(not geo.iso.tile_for(ONLY_MAPS, 0).is_empty(), "a map still finds it")
	t.ok(not geo.iso.maps_only(FLOOR_E))
	_cleanup()
