extends RefCounted
## Real side-view packs (T17.32): a room and a stage painted with the side-view terrain of the
## ground's sheet (a set of the shape `side` in the mode *match sides*), the ground of a sheet
## without one painted as before, and the parallax set nearest the ground used behind a room.

const Recipe := preload("res://builder/recipes/tileset_recipe.gd")
const RoomsRecipe := preload("res://builder/recipes/metroidvania/rooms_recipe.gd")
const StageRecipe := preload("res://builder/recipes/run_and_gun/stage_recipe.gd")
const SideKit := preload("res://builder/recipes/metroidvania/side_kit.gd")
const Parallax := preload("res://builder/recipes/metroidvania/parallax_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")

# the pieces rpggen lays into a sheet from names like grassCenter, grassMid, grassLeft,
# grassRight and grass (side_packs._make_sheet): the sides where the ground goes on
const N := 1
const E := 4
const S := 16
const W := 64
const CENTER := Vector2i(0, 0)
const MID := Vector2i(1, 0)
const LEFT := Vector2i(2, 0)
const RIGHT := Vector2i(3, 0)
const SINGLE := Vector2i(4, 0)
const PIECES := {CENTER: N | E | S | W, MID: E | S | W, LEFT: E | S, RIGHT: S | W, SINGLE: S}
const KEYS := {N: "top_side", E: "right_side", S: "bottom_side", W: "left_side"}
const SHEET := "generated.pack_grass_side"

func _sets() -> Array:
	return [{"name": "grass_side", "mode": "sides", "terrains": [{"name": "grass", "color": "#4caf50"}],
		"surface": "grass", "over": "nothing", "shape": "side", "layout": "side", "sheet": SHEET}]

func _def() -> Dictionary:
	return {"name": "overworld", "sources": [{"asset": SHEET, "source_id": 0}], "terrain_sets": _sets()}

func _tileset() -> TileSet:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_physics_layer()
	Recipe.ensure_terrain_sets(ts, _sets())
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(80, 16, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(16, 16)
	ts.add_source(src, 0)
	for coords: Vector2i in PIECES:
		src.create_tile(coords)
		var peering := {"top_left_corner": -1, "top_right_corner": -1, "bottom_left_corner": -1, "bottom_right_corner": -1}
		for bit: int in KEYS:
			peering[KEYS[bit]] = 0 if PIECES[coords] & bit else -1
		var td := src.get_tile_data(coords, 0)
		Recipe.apply_terrain(td, ts, _sets(), {"set": "grass_side", "terrain": 0, "peering": peering})
		td.add_collision_polygon(0)
		td.set_collision_polygon_points(0, 0, PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, 8), Vector2(-8, 8)]))
	return ts

func _ctx() -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	var sheet := {"id": SHEET, "pack_id": "generated", "path": "generated/side_terrain/a.png", "status": "AUTO_DETECTED",
		"detected": {"usage": "tiles", "role": "GROUND", "tags": ["side_terrain"]}, "overrides": {}}
	ctx.catalog = CatalogReader.new({"assets": [sheet], "tilesets": [_def()], "objects": []})
	ctx.config = {"archetype": "metroidvania", "resolution": [640, 360], "starter": {"ground": SHEET}}
	return ctx

func _layers(ts: TileSet) -> Dictionary:
	var out := {}
	for layer_name: String in RoomsRecipe.LAYERS:
		var layer := TileMapLayer.new()
		layer.tile_set = ts
		out[layer_name] = layer
	return out

func _free(layers: Dictionary) -> void:
	for layer_name: String in layers:
		(layers[layer_name] as Node).free()

func test_the_kit_finds_the_terrain_of_the_grounds_sheet(t) -> void:
	var ts := _tileset()
	var kit := SideKit.find(_ctx(), _def(), ts)
	t.eq(kit["terrain"], {"set": 0, "terrain": 0}, "the side-view set of the sheet chosen as ground")
	t.eq(SideKit.side_sets(_def()).size(), 1)
	var other := _def()
	other["terrain_sets"] = [{"name": "plain", "mode": "sides", "terrains": [], "shape": "plain", "sheet": SHEET}]
	t.eq(SideKit.side_terrain(_ctx(), other, ts, kit["top"]), {}, "a set of another shape is not the ground's")
	t.eq(SideKit.side_sets(other), [], "nothing for the hash of a project without one")

func test_a_room_is_painted_with_its_surface_its_ends_and_its_inside(t) -> void:
	var ts := _tileset()
	var kit := SideKit.find(_ctx(), _def(), ts)
	var layers := _layers(ts)
	var rows := [
		"..........",
		"..####....",
		"..####..#.",
		"..####..#.",
	]
	RoomsRecipe.paint(rows, layers, kit)
	var ground: TileMapLayer = layers["Ground"]
	t.eq(ground.get_cell_atlas_coords(Vector2i(2, 1)), LEFT, "the left end of the surface")
	t.eq(ground.get_cell_atlas_coords(Vector2i(3, 1)), MID, "the surface's middle")
	t.eq(ground.get_cell_atlas_coords(Vector2i(5, 1)), RIGHT, "the right end")
	t.eq(ground.get_cell_atlas_coords(Vector2i(3, 2)), CENTER, "the inside")
	t.eq(ground.get_cell_atlas_coords(Vector2i(8, 2)), SINGLE, "a column one cell wide has its own top")
	t.eq(ground.get_cell_atlas_coords(Vector2i(0, 0)), Vector2i(-1, -1), "the air is left empty")
	for y in range(1, 4):
		for x in range(2, 6):
			t.ok(ground.get_cell_source_id(Vector2i(x, y)) == 0, "every cell of ground is painted")
	var again := _layers(ts)
	RoomsRecipe.paint(rows, again, kit)
	for y in rows.size():
		for x in 10:
			var cell := Vector2i(x, y)
			t.eq((again["Ground"] as TileMapLayer).get_cell_atlas_coords(cell), ground.get_cell_atlas_coords(cell), "the same rows paint the same room")
	_free(layers)
	_free(again)

func test_a_stage_floor_is_painted_with_the_terrain(t) -> void:
	var ts := _tileset()
	var kit := SideKit.find(_ctx(), _def(), ts)
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	StageRecipe.paint_floor(layer, Vector2i(6, 8), kit)
	var top := StageRecipe.floor_row(8)
	t.eq(layer.get_cell_atlas_coords(Vector2i(2, top)), MID, "the floor's surface")
	t.eq(layer.get_cell_atlas_coords(Vector2i(2, top + 1)), CENTER, "under it the inside")
	layer.free()

func _layer_asset(id: String, pack: String, folder: String, depth: int) -> Dictionary:
	return {"id": id, "pack_id": pack, "path": "icon.svg", "status": "AUTO_DETECTED", "overrides": {},
		"detected": {"usage": "background", "role": "BACKGROUND", "tags": ["parallax:%d" % depth, "parallax_set:" + folder]}}

func test_the_parallax_set_nearest_the_ground_is_used(t) -> void:
	var ctx := BuildContext.new("res://builder")
	var ground := {"id": "p.castle.tiles", "pack_id": "p", "path": "assets/packs/p/Env/Castle/layers/tiles.png",
		"status": "AUTO_DETECTED", "detected": {"usage": "tiles", "role": "GROUND"}, "overrides": {}}
	var assets := [
		ground,
		_layer_asset("p.cave.back", "p", "Env/Cave/layers", 1),
		_layer_asset("p.cave.front", "p", "Env/Cave/layers", 2),
		_layer_asset("p.castle.sky", "p", "Env/Castle/layers", 1),
		_layer_asset("p.castle.walls", "p", "Env/Castle/layers", 2),
	]
	ctx.catalog = CatalogReader.new({"assets": assets, "tilesets": [], "objects": []})
	ctx.config = {"archetype": "metroidvania", "starter": {"ground": "p.castle.tiles"}}
	var found := Parallax.layers(ctx)
	t.eq(found.map(func(e: Dictionary) -> String: return str(e["asset"])), ["p.castle.sky", "p.castle.walls"], "the castle's layers, far first")
	ctx.config = {"archetype": "metroidvania"}
	found = Parallax.layers(ctx)
	t.eq(found.map(func(e: Dictionary) -> String: return str(e["asset"])), ["p.castle.sky", "p.castle.walls"], "without a ground: the first set by name")
	t.eq(Parallax.set_of({"tags": ["parallax_set:Env/Cave/layers"]}), "Env/Cave/layers")
	t.eq(Parallax.set_of({"tags": ["parallax:1"]}), "")
