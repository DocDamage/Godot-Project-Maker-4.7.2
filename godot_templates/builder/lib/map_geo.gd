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
	return minf(1.0, width / (DIAMONDS_ACROSS * reader.footprint().x))

## True for a project whose maps are isometric and whose packs have the tiles for it.
static func is_isometric(ctx: BuildContext) -> bool:
	return IsoTileset.project_wanted(ctx.config) and IsoTileset.new(ctx.catalog).has_tiles()

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
	if not isometric:
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
	if not isometric:
		MapUtil.fill(layer, cells, plain)
		return
	var run: Array[Vector2i] = []
	for y in range(cells.position.y, cells.end.y):
		for x in range(cells.position.x, cells.end.x):
			run.append(Vector2i(x, y))
	paint_joined(layer, run, what, plain)

## The notes of what was painted since the last call, one line a kind, for the recipe to print
## once a map; the count starts again.
func take_notes() -> Array[String]:
	var out: Array[String] = []
	var kinds := notes.keys()
	kinds.sort()
	for kind: String in kinds:
		out.append("%s: %d cells were laid with the nearest piece (the packs have no piece that joins on exactly their sides)" % [kind.to_lower(), JsonUtil.to_int(notes[kind])])
	notes.clear()
	return out

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
func paint_walls(root: Node2D, nodes: Dictionary, size: Vector2i, skip: Array = []) -> void:
	if not isometric:
		MapBuild.paint_walls(root, nodes, size, wall_tile(), tile_px, skip)
		return
	var wall := wall_tile()
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

## Invisible collision along the edge of a map of `size` cells, a shape a cell (`skip` left
## open): MapUtil.border_collision's rectangles, or diamonds.
func border_collision(root: Node2D, size: Vector2i, skip: Array = []) -> StaticBody2D:
	if not isometric:
		return MapUtil.border_collision(root, size, tile_px, skip)
	return _blocked_cells(root, border_cells(size, skip))

## An unseen body (`BorderCollision`) that blocks `cells`, a shape of the cell each.
func _blocked_cells(root: Node2D, cells: Array[Vector2i]) -> StaticBody2D:
	var body := StaticBody2D.new()
	body.name = "BorderCollision"
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
