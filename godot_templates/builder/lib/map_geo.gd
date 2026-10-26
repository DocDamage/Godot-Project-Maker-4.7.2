extends RefCounted
## The seam between a plan of cells and the px of a map (T17.14).
##
## A map is planned on a grid of cells whatever the view; only painting and positions differ.
## Every map recipe turns a cell into a position, a shape or a tile through one of these: for a
## project seen from above it is the arithmetic of squares the recipes always had (the same
## calls with the same numbers, so their output is byte for byte what it was), and for
## `projection: isometric` it is RpgIso (the runtime's arithmetic, shared with
## rpggen/core/iso_math.py) and IsoTileset.
##
##     var geo := MapGeo.new(ctx)                # the project's outdoor maps
##     var tile_set := geo.load_tile_set()
##     geo.center(cell)                          # where an actor stands
##     geo.cell_shape()                          # what blocks or triggers on one cell
##     geo.find_tile("GROUND")                   # {source_id, coords} for MapUtil.put / fill
##     geo.paint_joined(layer, cells, "ROAD", road)  # a road, piece by piece where a pack has them
##
## `tile_px` is what a recipe means by "a tile" where it needs one number (a reach, a light, a
## gate): the tile of a map of squares, and on diamonds the length of one step from a cell to
## the next (RpgIso.unit), not the width of the diamond.

const JsonUtil := preload("json_util.gd")
const MapUtil := preload("map_util.gd")
const MapBuild := preload("map_build.gd")
const SceneUtil := preload("scene_util.gd")
const BuildContext := preload("build_context.gd")
const IsoTileset := preload("iso_tileset.gd")
const Paths := preload("paths.gd")
const TextureUtil := preload("texture_util.gd")
const TerrainPaint := preload("terrain_paint.gd")

const OVERWORLD := "overworld"

var isometric := false
## The isometric tile set's reader; null for a project seen from above.
var iso: IsoTileset = null
## The definition of the tile set the maps are painted with ({} when the packs have none).
var def: Dictionary = {}
var tile_px := 16
## The size of a cell on the screen: (tile, tile), or the diamond.
var footprint := Vector2i(16, 16)
var tile_set: TileSet = null
## What the painting had to settle for, for a recipe to say once a map: the kind of piece
## ("ROAD") -> how many cells were laid with the nearest piece instead of the right one.
var notes: Dictionary = {}
## What a terrain of the tile set painted since the last notes (T17.31): the kind -> the set.
var painted: Dictionary = {}

var _ctx: BuildContext

## The geometry of the project's maps: of its outdoor tile set, or of the tile set
## `tileset_name` (an interior's own) when one is named. An isometric project has one tile set.
func _init(ctx: BuildContext, tileset_name: String = "") -> void:
	_ctx = ctx
	if IsoTileset.project_wanted(ctx.config):
		var reader := IsoTileset.new(ctx.catalog)
		if reader.has_tiles():
			isometric = true
			iso = reader
			def = ctx.catalog.tileset_def(reader.tileset_name())
			footprint = reader.footprint()
			tile_px = RpgIso.unit(footprint)
			return
	def = ctx.catalog.tileset_def(tileset_name if tileset_name != "" else OVERWORLD)
	if not def.is_empty():
		tile_px = JsonUtil.to_int(def["tile_size"][0])
	footprint = Vector2i(tile_px, tile_px)

## What a recipe that is no map means by "a tile" (an actor's reach, a light, a hit box): the
## tile of the outdoor tile set, else of the first one, else the config's `base_tile_size`; and
## for an isometric project the length of one step on its diamonds.
static func tile_unit(ctx: BuildContext) -> int:
	# an isometric project measures by its diamond, whatever sheets of squares its packs also
	# have (T17.30: *Lords Of Pain*'s effects are cut into a tile set of 16 px squares)
	for def: Dictionary in ctx.catalog.tileset_defs():
		if IsoTileset.wanted(def):
			return RpgIso.unit(BuildContext.vec2i(def["tile_size"]))
	var found: Dictionary = ctx.catalog.tileset_def(OVERWORLD)
	if found.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		found = ctx.catalog.tileset_defs()[0]
	if found.is_empty():
		return JsonUtil.to_int(ctx.config.get("base_tile_size", 16))
	if IsoTileset.wanted(found):
		return RpgIso.unit(BuildContext.vec2i(found["tile_size"]))
	return JsonUtil.to_int(found["tile_size"][0])

## How many diamonds an isometric game shows across its screen at least.
const DIAMONDS_ACROSS := 8

## The zoom of the player's camera: 1 for a project seen from above, and for an isometric one
## whose diamonds are so large that fewer than DIAMONDS_ACROSS of them would fit across the
## screen (180 px on a screen of 640) what makes that many fit.
static func camera_zoom(ctx: BuildContext) -> float:
	if not IsoTileset.project_wanted(ctx.config):
		return 1.0
	var reader := IsoTileset.new(ctx.catalog)
	if not reader.has_tiles() or reader.footprint().x <= 0:
		return 1.0
	var resolution := JsonUtil.to_array(ctx.config.get("resolution", [640, 360]))
	var width := JsonUtil.to_float(resolution[0]) if resolution.size() == 2 else 640.0
	return whole_step_zoom(minf(1.0, width / (DIAMONDS_ACROSS * reader.footprint().x)), reader.footprint())

## The zoom nearest `wanted` (never above 1, never none) at which one step of the grid of
## diamonds is a whole number of px on the screen each way (T17.22). A tile of an isometric
## pack is a block: under its face it has the side of its block, which the tiles before it
## cover exactly. At a zoom where half a diamond is no whole number of px (0.444 on diamonds of
## 180 x 104: 40 px and 23.1 px) every tile lies at another fraction of a pixel, the nearest
## texel of one tile and of the tile behind it are a row apart here and there, and a sliver of
## the side of the tile behind shows between two faces: thin dark dashes along the edges of
## the diamonds. Where the steps are whole (0.5: 45 px and 26 px) every tile is sampled alike
## and none shows, wherever the camera stands. The zooms that do it are the multiples of
## 2 / gcd(w, h).
static func whole_step_zoom(wanted: float, footprint: Vector2i) -> float:
	if wanted >= 1.0 or footprint.x <= 0 or footprint.y <= 0:
		return minf(wanted, 1.0)
	var a := footprint.x
	var b := footprint.y
	while b != 0:
		var rest := a % b
		a = b
		b = rest
	var unit := 2.0 / a
	return minf(1.0, maxi(1, roundi(wanted / unit)) * unit)

## True for a project whose maps are isometric and whose packs have the tiles for it.
static func is_isometric(ctx: BuildContext) -> bool:
	return IsoTileset.project_wanted(ctx.config) and IsoTileset.new(ctx.catalog).has_tiles()

## The version of what the map recipes do with pieces that stand along a side of a diamond
## (T17.22: the edge of a map from wall segments, a house of pieces, a yard's fence). 2: posts
## where two sides of the edge or of a house meet, and a house's roof of pieces joined along a
## ridge.
const EDGE_VERSION := 2

## What a map recipe adds to its hash for such pieces: `{iso_edges: EDGE_VERSION}` for an
## isometric project whose tile set has one, and nothing for every other project, whose hash is
## what it was (a pack of whole wall tiles, a project seen from above).
static func edge_hash(ctx: BuildContext) -> Dictionary:
	if not IsoTileset.project_wanted(ctx.config):
		return {}
	var reader := IsoTileset.new(ctx.catalog)
	if reader.edge_sets().is_empty():
		return {}
	return {"iso_edges": EDGE_VERSION}

func tileset_path() -> String:
	if isometric:
		return iso.tileset_path()
	return Paths.TILESETS_DIR + "%s.tres" % JsonUtil.to_str(def.get("name", OVERWORLD))

## Loads the tile set the maps paint with (null when it was not built).
func load_tile_set() -> TileSet:
	tile_set = load(tileset_path()) as TileSet if ResourceLoader.exists(tileset_path()) else null
	return tile_set

# ---------------------------------------------------------------- positions

## The middle of a cell: where an actor, a marker or a trigger of that cell is.
func center(cell: Vector2i) -> Vector2:
	if isometric:
		return RpgIso.cell_to_screen(cell, footprint)
	return MapUtil.tile_center(cell, tile_px)

## Where the foot of a thing that stands on a cell is: the middle of the bottom row of a square
## (it is sorted by its feet), the middle of a diamond (it is sorted by the line through the
## diamond's left and right corner).
func foot(cell: Vector2i) -> Vector2:
	if isometric:
		return RpgIso.cell_to_screen(cell, footprint)
	return Vector2(cell) * tile_px + Vector2(tile_px / 2.0, tile_px - 1)

## The middle of the lower edge of a square cell (furniture stands there); the middle of a
## diamond.
func bottom(cell: Vector2i) -> Vector2:
	if isometric:
		return RpgIso.cell_to_screen(cell, footprint)
	return MapUtil.tile_center(cell, tile_px) + Vector2(0, tile_px / 2.0)

## How far `by` cells are on the screen.
func step(by: Vector2) -> Vector2:
	if isometric:
		return Vector2((by.x - by.y) * footprint.x / 2.0, (by.x + by.y) * footprint.y / 2.0)
	return by * tile_px

## The shape of one cell around its middle: what blocks or triggers on it.
func cell_shape() -> Shape2D:
	if isometric:
		var diamond := ConvexPolygonShape2D.new()
		diamond.points = IsoTileset.diamond(footprint)
		return diamond
	var rect := RectangleShape2D.new()
	rect.size = Vector2(tile_px, tile_px)
	return rect

## The outline of a rectangle of cells, in the px of the map.
func cells_outline(cells: Rect2i) -> PackedVector2Array:
	if isometric:
		var first := RpgIso.cell_to_screen(cells.position, footprint)
		var out := PackedVector2Array()
		for corner in IsoTileset.outline(cells.size, footprint):
			# `outline` is laid around the cell nearest the camera
			out.append(first + step(Vector2(cells.size - Vector2i.ONE)) + corner)
		return out
	var left := float(cells.position.x * tile_px)
	var top := float(cells.position.y * tile_px)
	var right := float(cells.end.x * tile_px)
	var bottom := float(cells.end.y * tile_px)
	return PackedVector2Array([Vector2(left, top), Vector2(right, top), Vector2(right, bottom), Vector2(left, bottom)])

## Where a gate of a cell stands (its origin is its foot).
func gate_position(cell: Vector2i) -> Vector2:
	if isometric:
		return RpgIso.cell_to_screen(cell, footprint)
	return Vector2(cell.x * tile_px + tile_px / 2.0, (cell.y + 1) * tile_px)

# ---------------------------------------------------------------- buildings and objects

## {size: [w, h] cells, door: [dx, dy] cells from the cell of its top-left corner, one row
## below its base} of a building entry (ObjectEntries) for MapBuild.plan; {} without one. Seen
## from above it is the picture measured in tiles. An isometric building stands on the cells
## its catalog entry says (`stands_on`), and its door is in the middle of its south side: the
## plan's door cell is the one in front of it, down and to the left on the screen.
func building_info(building: Dictionary) -> Dictionary:
	if building.is_empty():
		return {}
	if is_iso_entry(building):
		var size := entry_cells(building)
		@warning_ignore("integer_division")
		return {"size": [size.x, size.y], "door": [(size.x - 1) / 2, size.y]}
	var region: Array = building["region"]
	var door_px := Vector2(JsonUtil.to_float(region[2]) / 2.0, JsonUtil.to_float(region[3]) - 1.0)
	var door_info: Array = building["door"]
	if door_info.size() == 2:
		door_px = Vector2(JsonUtil.to_float(door_info[0]), JsonUtil.to_float(door_info[1]))
	return {
		"size": [ceili(JsonUtil.to_float(region[2]) / tile_px), ceili(JsonUtil.to_float(region[3]) / tile_px)],
		"door": [floori(float(int(door_px.x)) / tile_px), floori(float(int(door_px.y)) / tile_px) + 1],
	}

## True for an object entry that was drawn for the isometric view.
static func is_iso_entry(entry: Dictionary) -> bool:
	return JsonUtil.to_array(entry.get("iso", [])).size() == 2

## The cells an isometric object entry stands on, [columns, rows].
static func entry_cells(entry: Dictionary) -> Vector2i:
	var cells := JsonUtil.to_array(entry.get("stands_on", []))
	if cells.size() != 2:
		return Vector2i.ONE
	return Vector2i(maxi(1, JsonUtil.to_int(cells[0])), maxi(1, JsonUtil.to_int(cells[1])))

## Where the scene of a building is put whose top-left cell is `cell`: seen from above the
## corner of that cell plus the picture's origin; in the isometric view the middle of the cell
## of its footprint nearest the camera, which is where its picture's origin lies.
func building_position(building: Dictionary, cell: Vector2i) -> Vector2:
	if isometric:
		return center(cell + entry_cells(building) - Vector2i.ONE)
	var origin := Vector2(JsonUtil.to_float(building["origin"][0]), JsonUtil.to_float(building["origin"][1]))
	return Vector2(cell) * tile_px + origin

# ---------------------------------------------------------------- finding tiles

func _iso_tile(asset_id: String, turn: int = 0) -> Dictionary:
	var found := iso.tile_for(asset_id, turn)
	if found.is_empty():
		return {}
	return {"source_id": found["source"], "coords": found["coords"], "asset_id": found["asset_id"]}

## {source_id, coords} of the tile the maps paint for `role`, or {}.
func find_tile(role: String) -> Dictionary:
	if isometric:
		var plain := iso.plain_tile(role)
		return _iso_tile(plain) if plain != "" else {}
	return MapUtil.find_tile(_ctx, def, tile_set, role)

## {source_id, coords} of the first tile of the asset `asset_id`, or {}.
func tile_of_asset(asset_id: String) -> Dictionary:
	if isometric:
		return _iso_tile(asset_id)
	return MapUtil.tile_of_asset(_ctx, def, tile_set, asset_id)

## The tile of the `nth` (0-based) ground of the packs with `role`, or {}.
func nth_tile_with_role(role: String, nth: int) -> Dictionary:
	if isometric:
		var plain := iso.plain_tiles(role)
		return _iso_tile(plain[nth]) if nth < plain.size() else {}
	return MapBuild.nth_tile_with_role(_ctx, def, tile_set, role, nth)

## Up to `count` other tiles to vary the ground `base` with: of the same sheet, or the other
## flat ground tiles of an isometric pack.
func other_tiles(base: Dictionary, count: int) -> Array[Dictionary]:
	if not isometric:
		return MapUtil.other_tiles(tile_set, base, count)
	var out: Array[Dictionary] = []
	for asset_id in iso.plain_tiles("GROUND"):
		if asset_id == JsonUtil.to_str(base.get("asset_id", "")):
			continue
		out.append(_iso_tile(asset_id))
		if out.size() >= count:
			break
	return out

func wall_tile() -> Dictionary:
	if isometric:
		return find_tile("WALL")
	return MapUtil.wall_tile(_ctx, def, tile_set)

# ---------------------------------------------------------------- painting

## The layer the roads of a map are painted on, or null when the map has none for them. Seen
## from above it is `GroundDetails`, over the ground, as it always was: a road tile is a flat
## picture and what it does not cover is the ground under it. On diamonds it is the `Ground`
## layer itself (T17.18): a tile of an isometric pack is a whole block, the diamond with the
## earth under it, and one layer draws its cells from the back to the front, so the earth of a
## tile is covered by the tiles before it. A road piece laid on a layer above the ground kept
## its earth in sight over the grass before it, a dark kerb along the lower edges of every
## path. Laid in the place of the ground tile of its cell it is covered as the ground is. (The
## map must still have `GroundDetails` among its layers to get roads at all, in both views:
## which maps have roads is not the view's to change.)
func road_layer(nodes: Dictionary) -> TileMapLayer:
	if not nodes.has("GroundDetails"):
		return null
	var layer: TileMapLayer = nodes["Ground"] if isometric and nodes.has("Ground") else nodes["GroundDetails"]
	return layer

## Paints `cells` as one run of `what` (a role: ROAD, WATER, WALL). Seen from above every cell
## gets `plain`. On diamonds a cell gets the piece that joins on exactly the sides where its
## neighbours are cells of the run too, turned as it must be (the packs' `joins`); when the
## packs have no piece for those sides the nearest one (the fewest wrong sides), which is
## counted in `notes[what]`; and `plain` when no piece of `what` says its sides.
func paint_joined(layer: TileMapLayer, cells: Array[Vector2i], what: String, plain: Dictionary) -> void:
	# a terrain of the tile set for roads or water paints them, joined where they meet (T17.31)
	var found := terrain_for(what)
	if not found.is_empty() and not cells.is_empty():
		RpgTerrain.paint_area(terrain_layer(layer, found), cells, JsonUtil.to_int(found["set"]), JsonUtil.to_int(found["terrain"]), seed_for(what.to_lower()))
		_painted(what, found)
		return
	if not isometric:
		if plain.is_empty():
			return
		for cell in cells:
			MapUtil.put(layer, cell, plain)
		return
	var run := {}
	for cell in cells:
		run[cell] = true
	var has_pieces := not iso.laid_pieces(what).is_empty()
	for cell in cells:
		var tile := plain
		if has_pieces:
			var sides: Array[String] = []
			for side in RpgIso.SIDES:
				var by: Vector2i = RpgIso.STEPS[side]
				if run.has(cell + by):
					sides.append(side)
			var piece := iso.nearest_piece(what, sides)
			if not piece.is_empty():
				tile = _iso_tile(JsonUtil.to_str(piece["asset_id"]), JsonUtil.to_int(piece["turn"]))
				if JsonUtil.to_int(piece["wrong"]) > 0:
					notes[what] = JsonUtil.to_int(notes.get(what, 0)) + 1
		if not tile.is_empty():
			MapUtil.put(layer, cell, tile)

## Paints cells of `what` whose sides are known and not read off their neighbours (T17.15: the
## loop of a race track, where two cells that lie side by side need not be joined): `sides` is
## cell (Vector2i) -> the sides it joins on (of n, e, s, w). Seen from above every cell gets
## `plain`. On diamonds a cell gets the piece for exactly its sides, as `paint_joined` chooses
## it: the nearest one when the packs have none (counted in `notes[what]`), and `plain` when no
## piece of `what` says its sides. The cells are painted in the order of the dictionary.
func paint_sides(layer: TileMapLayer, sides: Dictionary, what: String, plain: Dictionary) -> void:
	# a terrain of the tile set paints the loop as one path through its cells in their order,
	# back to the first (T17.31): two cells side by side join only where the loop goes on
	var found := terrain_for(what)
	if not found.is_empty() and not sides.is_empty():
		var path: Array[Vector2i] = []
		for key: Variant in sides:
			path.append(key)
		path.append(path[0])
		RpgTerrain.paint_path(terrain_layer(layer, found), path, JsonUtil.to_int(found["set"]), JsonUtil.to_int(found["terrain"]), seed_for(what.to_lower()))
		_painted(what, found)
		return
	var has_pieces := isometric and not iso.laid_pieces(what).is_empty()
	for key: Variant in sides:
		var cell: Vector2i = key
		var tile := plain
		if has_pieces:
			var piece := iso.nearest_piece(what, JsonUtil.to_array(sides[key]))
			if not piece.is_empty():
				tile = _iso_tile(JsonUtil.to_str(piece["asset_id"]), JsonUtil.to_int(piece["turn"]))
				if JsonUtil.to_int(piece["wrong"]) > 0:
					notes[what] = JsonUtil.to_int(notes.get(what, 0)) + 1
		if not tile.is_empty():
			MapUtil.put(layer, cell, tile)

## Paints several runs of `what` (the roads of a map). Seen from above each run is painted
## in its turn, as `paint_joined` paints one; on diamonds they are one run, so that two roads
## that meet join.
func paint_runs(layer: TileMapLayer, runs: Array, what: String, plain: Dictionary) -> void:
	if not isometric and terrain_for(what).is_empty():
		for run: Array[Vector2i] in runs:
			paint_joined(layer, run, what, plain)
		return
	var all: Array[Vector2i] = []
	for run: Array[Vector2i] in runs:
		for cell in run:
			if not all.has(cell):
				all.append(cell)
	paint_joined(layer, all, what, plain)

## Fills a rectangle of cells with one run of `what` (water): MapUtil.fill seen from above.
func fill_joined(layer: TileMapLayer, cells: Rect2i, what: String, plain: Dictionary) -> void:
	if not isometric and terrain_for(what).is_empty():
		MapUtil.fill(layer, cells, plain)
		return
	var run: Array[Vector2i] = []
	for y in range(cells.position.y, cells.end.y):
		for x in range(cells.position.x, cells.end.x):
			run.append(Vector2i(x, y))
	paint_joined(layer, run, what, plain)

# ---------------------------------------------------------------- terrains (T17.31)

## The seed the painting of `label` (a kind, a map) takes its variants by: the project's seed
## and the label.
func seed_for(label: String) -> int:
	return MapBuild.stream_seed(JsonUtil.to_int(_ctx.config.get("seed", 12345)), "terrain:" + label)

## The terrain of the tile set that paints `what` (ROAD, WATER, PATCH: a patch of another
## ground than `avoid`, SOIL: the ground of a field), as `TerrainPaint.find` gives it; {} when
## it has none, and always for WALL. A road takes a terrain that says it is a path or a road
## and joins at its sides or has every shape, else a terrain of earth, sand or stone that has
## every shape (a block of 3x3 has no piece for a road one cell wide).
func terrain_for(what: String, avoid: String = "") -> Dictionary:
	if tile_set == null or def.is_empty():
		return {}
	if isometric and (what == "PATCH" or what == "SOIL"):
		return {}  # on diamonds patches are other flat tiles, and the field has its own diamonds
	match what:
		"ROAD":
			# a terrain that joins at its sides first: one that fills its corners too is a lot,
			# a square, more than a road
			var road := TerrainPaint.find(_ctx, def, tile_set, ["path", "road"], ["path"], ["ROAD"])
			if road.is_empty():
				road = TerrainPaint.find(_ctx, def, tile_set, ["path", "road"], ["any"], ["ROAD"])
			if road.is_empty():
				road = TerrainPaint.find(_ctx, def, tile_set, ["dirt", "sand", "stone"], ["any"], ["ROAD"])
			return road
		"WATER":
			return TerrainPaint.find(_ctx, def, tile_set, TerrainPaint.WATER_SURFACES, TerrainPaint.AREA_SHAPES, ["WATER"])
		"PATCH":
			return TerrainPaint.find(_ctx, def, tile_set, TerrainPaint.PATCH_SURFACES, TerrainPaint.AREA_SHAPES, ["GROUND"], avoid)
		"SOIL":
			return TerrainPaint.find(_ctx, def, tile_set, TerrainPaint.SOIL_SURFACES, TerrainPaint.SOIL_SHAPES, ["GROUND"])
		"SAND":
			return TerrainPaint.find(_ctx, def, tile_set, ["sand"], TerrainPaint.AREA_SHAPES, ["GROUND"])
	return {}

## The layer a terrain is painted on instead of `layer`: on diamonds a terrain drawn over nothing
## (a path laid on the ground, Screaming Brain's) goes on the map's `GroundDetails` over the
## `Ground` it was asked for, which keeps its ground under it; everything else on `layer`.
func terrain_layer(layer: TileMapLayer, found: Dictionary) -> TileMapLayer:
	if not isometric or JsonUtil.to_str(found.get("over", "")) != "nothing" or String(layer.name) != "Ground":
		return layer
	var details := layer.get_parent().get_node_or_null("GroundDetails") as TileMapLayer if layer.get_parent() != null else null
	return details if details != null else layer

## Fills `rect` with the ground `base` ({source_id, coords}): seen from above, when the tile is
## the middle of a terrain with plain variants, each cell takes one of them by the seed of
## `label` (a ground that varies, T17.31); else every cell the tile, as MapUtil.fill.
func fill_ground(layer: TileMapLayer, rect: Rect2i, base: Dictionary, label: String) -> void:
	if base.is_empty():
		return
	var base_coords: Vector2i = base["coords"]
	if isometric or tile_set == null or RpgTerrain.variants_of(tile_set, JsonUtil.to_int(base["source_id"]), base_coords).size() < 2:
		MapUtil.fill(layer, rect, base)
		return
	RpgTerrain.fill_varied(layer, RpgTerrain.rect_cells(rect), base, seed_for(label))

## The ground to fill a map with for `tile`, the first tile of a ground's sheet (`asset_id`, when
## known): seen from above the middle of the terrain the tile is a piece of, or of the terrain
## composed of the sheet (TerrainPaint.ground_middle); the tile itself on diamonds and for a
## tile set without terrains.
func ground_of(tile: Dictionary, asset_id: String = "") -> Dictionary:
	if isometric or tile.is_empty():
		return tile
	return TerrainPaint.ground_middle(def, tile_set, tile, asset_id)

## The surface of the ground `base` when it is the middle of a terrain ("" otherwise).
func surface_of(base: Dictionary) -> String:
	if isometric:
		return ""
	return TerrainPaint.surface_of_tile(def, tile_set, base)

## Paints the planned patches (MapBuild.plan's `patches`, rectangles) of other ground: seen
## from above, with a terrain of another surface than the ground's when the tile set has one
## (soft edges, T17.31), else with the tiles `others` as MapBuild.paint_planned_patches does.
func paint_patches(layer: TileMapLayer, patches: Array, others: Array, base: Dictionary, label: String) -> void:
	var found := {} if isometric else terrain_for("PATCH", surface_of(base))
	if found.is_empty():
		if not others.is_empty():
			MapBuild.paint_planned_patches(layer, patches, others)
		return
	for item: Dictionary in patches:
		var patch_rect: Rect2i = item["rect"]
		RpgTerrain.paint_area(layer, RpgTerrain.rect_cells(patch_rect), JsonUtil.to_int(found["set"]), JsonUtil.to_int(found["terrain"]), seed_for(label))
	if not patches.is_empty():
		_painted("PATCH", found)

## Up to `count` other tiles to vary the ground with, as `other_tiles`, without the pieces of a
## terrain (its edges and corners: a patch of them is no ground, T17.31). For a tile set without
## terrains it is `other_tiles`.
func plain_others(base: Dictionary, count: int) -> Array[Dictionary]:
	if isometric or tile_set == null:
		return other_tiles(base, count)
	var out: Array[Dictionary] = []
	for tile in other_tiles(base, 64):
		var src := tile_set.get_source(JsonUtil.to_int(tile["source_id"])) as TileSetAtlasSource
		var tile_coords: Vector2i = tile["coords"]
		var td := src.get_tile_data(tile_coords, 0) if src != null else null
		if td != null and td.terrain_set >= 0:
			continue
		# a patch of ground is walked on: no tile that blocks (a side view's slope piece
		# painted about a map seen from above walled its player in)
		if td != null and _blocks(td):
			continue
		out.append(tile)
		if out.size() >= count:
			break
	return out

## True when a tile has a collision shape on any physics layer of the tile set.
func _blocks(td: TileData) -> bool:
	for layer in tile_set.get_physics_layers_count():
		if td.get_collision_polygons_count(layer) > 0:
			return true
	return false

## The notes of what was painted since the last call, one line a kind, for the recipe to print
## once a map; the count starts again.
func take_notes() -> Array[String]:
	var out: Array[String] = []
	var kinds := notes.keys()
	kinds.sort()
	for kind: String in kinds:
		out.append("%s: %d cells were laid with the nearest piece (the packs have no piece that joins on exactly their sides)" % [kind.to_lower(), JsonUtil.to_int(notes[kind])])
	notes.clear()
	var with_terrain := painted.keys()
	with_terrain.sort()
	for kind: String in with_terrain:
		out.append("%s: painted with the terrain %s of the tile set" % [kind.to_lower(), JsonUtil.to_str(painted[kind])])
	painted.clear()
	return out

## Remembers which terrain painted `what`, for `take_notes` (T17.31).
func _painted(what: String, found: Dictionary) -> void:
	var all := TerrainPaint.specs(def)
	var index := JsonUtil.to_int(found.get("set", -1))
	painted[what] = JsonUtil.to_str(all[index].get("name", "")) if index >= 0 and index < all.size() else str(index)

## The cells of the border of a map of `size` cells, without those of `skip`, row by row.
static func border_cells(size: Vector2i, skip: Array = []) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in size.y:
		for x in size.x:
			var on_edge := x == 0 or y == 0 or x == size.x - 1 or y == size.y - 1
			if on_edge and not skip.has(Vector2i(x, y)):
				out.append(Vector2i(x, y))
	return out

## The blocked edge of a map. Seen from above: MapBuild.paint_walls (wall tiles on the Walls
## layer, else invisible rectangles). On diamonds: the wall tiles of the packs, joined by their
## sides where they say them, on the Y-sorted Props layer (a wall rises: who stands behind it
## is drawn behind it) or the Walls layer when the map has no Props, and the two far sides on
## the Ground layer; without a wall tile, or when a wall tile blocks nothing, an invisible
## diamond a cell.
##
## A pack whose walls are segments along a side of a diamond and no whole tiles (T17.22) gets
## its edge laid from them (`paint_edge_walls`); `fence_first` asks for a fence where the packs
## have both (a farm).
func paint_walls(root: Node2D, nodes: Dictionary, size: Vector2i, skip: Array = [], fence_first: bool = false) -> void:
	if not isometric:
		MapBuild.paint_walls(root, nodes, size, wall_tile(), tile_px, skip)
		return
	var wall := wall_tile()
	if wall.is_empty() and paint_edge_walls(root, nodes, size, skip, fence_first):
		return
	var layer: TileMapLayer = null
	for layer_name: String in ["Props", "Walls"]:
		if layer == null and nodes.has(layer_name):
			layer = nodes[layer_name]
	var blocks := false
	if not wall.is_empty() and layer != null:
		var cells := border_cells(size, skip)
		# The far sides of the edge (the first row and the first column) are laid in the place
		# of the ground of their cells (T17.18): nobody can stand behind them, and on a layer
		# above the ground the earth under a wall lay over the grass before it, a brown footing
		# all along the two far walls. On the ground's layer the tiles before a wall cover its
		# earth as they cover the ground's. The near sides stay where they sort with who walks
		# behind them; their earth looks out of the map.
		var back: TileMapLayer = nodes.get("Ground")
		paint_joined(layer, cells, "WALL", wall)
		var first := layer.get_cell_tile_data(cells[0]) if not cells.is_empty() else null
		blocks = first != null and first.get_collision_polygons_count(0) > 0 and layer.collision_enabled
		var far: Array[Vector2i] = []
		if back != null and back != layer:
			for cell in cells:
				if cell.x != 0 and cell.y != 0:
					continue
				back.set_cell(cell, layer.get_cell_source_id(cell), layer.get_cell_atlas_coords(cell), layer.get_cell_alternative_tile(cell))
				layer.erase_cell(cell)
				far.append(cell)
		# the ground's layer blocks nothing (MapUtil.COLLIDING_LAYERS): what was moved onto it
		# keeps its diamond as an unseen shape
		if blocks and not far.is_empty() and not back.collision_enabled:
			_blocked_cells(root, far)
	if not blocks:
		border_collision(root, size, skip)

## The sides of a cell of the edge of a map of `size` cells that look out of the map, the far
## ones first: `n` on the first row, `w` on the first column, `e` on the last column, `s` on the
## last row. A corner cell has two.
static func outward_sides(cell: Vector2i, size: Vector2i) -> Array[String]:
	var out: Array[String] = []
	if cell.y == 0:
		out.append("n")
	if cell.x == 0:
		out.append("w")
	if cell.x == size.x - 1:
		out.append("e")
	if cell.y == size.y - 1:
		out.append("s")
	return out

## True for the two sides of a diamond that lie away from the camera.
static func is_far_side(side: String) -> bool:
	return side == "n" or side == "w"

## Where the pieces of one cell of a map's edge go: [[side, layer name], ..] for its sides
## (`outward_sides`). A cell holds one tile a layer. **A cell with one side** has its piece on
## `Props`, which is sorted with the actors by the middle of the cell: a piece on a far side is
## drawn before whoever stands further south or east, a piece on a near side after whoever
## stands on the cells before it and over him (nobody stands on the cell itself: it is
## blocked). **A corner cell** has two pieces: the corner of two far sides has `n` on `Props`
## and `w` on `GroundDetails`; a corner of a far and a near side has the near one on `Props`
## and the far one on `GroundDetails`; the corner of the two near sides has `e` on `Props` and
## `s` on `Overhead`. `GroundDetails` lies under the actors (a far wall is behind everybody; an
## isometric map paints nothing else on that layer, its roads lie in the ground's) and
## `Overhead` over them (nothing of a map is nearer the camera than that corner).
static func edge_places(sides: Array[String]) -> Array:
	if sides.size() < 2:
		return [[sides[0], "Props"]] if sides.size() == 1 else []
	var first := sides[0]
	var second := sides[1]
	if is_far_side(first) and is_far_side(second):
		return [[first, "Props"], [second, "GroundDetails"]]
	if is_far_side(first):
		return [[second, "Props"], [first, "GroundDetails"]]
	return [[first, "Props"], [second, "Overhead"]]

## Lays the edge of an isometric map from the packs' wall segments (T17.22): on every cell of
## the edge the member of one wall's set that stands along the side that looks out of the map
## (`outward_sides`; the side is the piece's `edge`, never its turn), `skip` left open, a corner
## cell with a piece for each of its two sides on two layers (`edge_places`; a map without
## `Props` takes `Walls`, and one without the layer of a corner's second piece has one piece on
## that corner: the packs' walls carry their own end posts). The cells are blocked by the
## tiles' own collision (a wall blocks its diamond: the plan counts the cells of the edge as
## wall), or by unseen diamonds when the tiles block nothing. False, with nothing painted,
## when the packs have no wall that stands along all four sides or the map no layer for it.
func paint_edge_walls(root: Node2D, nodes: Dictionary, size: Vector2i, skip: Array = [], fence_first: bool = false) -> bool:
	if not isometric:
		return false
	var wall_set := iso.border_set(fence_first)
	var main_name := "Props" if nodes.has("Props") else "Walls"
	if wall_set == "" or not nodes.has(main_name):
		return false
	var unblocked: Array[Vector2i] = []
	for cell in border_cells(size, skip):
		var blocked := false
		for place: Array in edge_places(outward_sides(cell, size)):
			var side := JsonUtil.to_str(place[0])
			var layer_name := JsonUtil.to_str(place[1])
			var layer: TileMapLayer = nodes.get(main_name if layer_name == "Props" else layer_name)
			var piece := iso.edge_piece(wall_set, side)
			if layer == null or piece.is_empty():
				continue
			MapUtil.put(layer, cell, _iso_tile(JsonUtil.to_str(piece["asset_id"]), JsonUtil.to_int(piece["turn"])))
			var data := layer.get_cell_tile_data(cell)
			if layer.collision_enabled and data != null and data.get_collision_polygons_count(0) > 0:
				blocked = true
		if not blocked:
			unblocked.append(cell)
	if not unblocked.is_empty():
		_blocked_cells(root, unblocked)
	add_edge_posts(root, nodes, size, skip, iso.post_set_for(wall_set))
	return true

## The posts at the corners of a map's edge laid from wall segments (after T17.22): where the
## two sides of the edge meet, at each corner of the map whose cell is not left open, a post of
## `post_set` (`IsoTileset.post_set_for`: the packs' posts of the wall's colour). Sprites under
## `EdgePosts` in `YSorted`, each sorted just after the walls of its cell (a cell's middle and a
## pixel), so that it covers their ends; the post at the corner nearest the camera is drawn
## over the `Overhead` layer the near wall of that corner lies on. Nothing is done when the
## packs have no posts, or the map no `YSorted`.
func add_edge_posts(root: Node2D, nodes: Dictionary, size: Vector2i, skip: Array, post_set: String) -> Node2D:
	if not isometric or post_set == "" or not nodes.has("YSorted"):
		return null
	var holder: Node2D = null
	var corners := {
		Vector2i(0, 0): "nw",
		Vector2i(size.x - 1, 0): "ne",
		Vector2i(size.x - 1, size.y - 1): "es",
		Vector2i(0, size.y - 1): "sw",
	}
	for key: Variant in corners:
		var cell: Vector2i = key
		var corner := JsonUtil.to_str(corners[key])
		if skip.has(cell):
			continue
		var piece := iso.post_piece(post_set, corner)
		var sprite := post_sprite(iso, JsonUtil.to_str(piece.get("asset_id", "")), center(cell))
		if sprite == null:
			continue
		if holder == null:
			holder = Node2D.new()
			holder.y_sort_enabled = true
			var ysorted: Node = nodes["YSorted"]
			SceneUtil.add(ysorted, holder, root, "EdgePosts")
		if corner == "es":
			sprite.z_index = 11  # over the Overhead layer (10), where the near wall lies
		SceneUtil.add(holder, sprite, root, "Post_%s" % corner)
	return holder

## A sprite of the post `asset_id` standing on the cell whose middle is `at`, sorted a pixel
## after that middle (after the walls of the cell), or null for no picture.
static func post_sprite(tiles: IsoTileset, asset_id: String, at: Vector2) -> Sprite2D:
	var picture := tiles.picture_of(asset_id)
	var region := JsonUtil.to_array(picture.get("region", []))
	if region.size() != 4:
		return null
	var texture := TextureUtil.region_texture(JsonUtil.to_str(picture["texture"]), Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3])))
	if texture == null:
		return null
	var sprite := Sprite2D.new()
	sprite.texture = texture
	IsoTileset.stand(sprite, tiles.facets(asset_id), at)
	sprite.position.y += 1.0
	sprite.offset.y -= 1.0
	sprite.set_meta(&"asset_id", asset_id)
	return sprite

## Invisible collision along the edge of a map of `size` cells, a shape a cell (`skip` left
## open): MapUtil.border_collision's rectangles, or diamonds.
func border_collision(root: Node2D, size: Vector2i, skip: Array = []) -> StaticBody2D:
	if not isometric:
		return MapUtil.border_collision(root, size, tile_px, skip)
	return _blocked_cells(root, border_cells(size, skip))

## An unseen body (`BorderCollision`) that blocks `cells`, a shape of the cell each.
func _blocked_cells(root: Node2D, cells: Array[Vector2i]) -> StaticBody2D:
	return block_cells(root, cells, "BorderCollision")

## An unseen body named `body_name` that blocks `cells`, a shape of the cell each (a square or
## a diamond), in the order given.
func block_cells(root: Node2D, cells: Array[Vector2i], body_name: String) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.name = body_name
	body.collision_layer = 0
	body.collision_mask = 0
	body.set_collision_layer_value(1, true)
	root.add_child(body)
	body.owner = root
	var diamond := cell_shape()
	for cell in cells:
		var shape := CollisionShape2D.new()
		shape.name = "Wall_%d_%d" % [cell.x, cell.y]
		shape.shape = diamond
		shape.position = center(cell)
		body.add_child(shape)
		shape.owner = root
	return body

## A trigger on a cell that sends the player to another map (MapBuild.add_exit_door).
func add_exit_door(triggers: Node, root: Node, node_name: String, cell: Vector2i, target_map: String, target_spawn: StringName) -> Area2D:
	if not isometric:
		return MapBuild.add_exit_door(triggers, root, node_name, cell, tile_px, target_map, target_spawn)
	var door := Area2D.new()
	SceneUtil.attach_script(door, MapUtil.DOOR_SCRIPT)
	door.collision_layer = 0
	door.collision_mask = 0
	door.set_collision_layer_value(6, true)  # triggers
	door.set_collision_mask_value(2, true)  # player
	door.position = center(cell)
	door.set("target_map", target_map)
	door.set("target_spawn", target_spawn)
	SceneUtil.add(triggers, door, root, node_name)
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	shape.shape = cell_shape()
	door.add_child(shape)
	return door
