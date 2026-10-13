extends RefCounted
## The floor and the walls of a farm's rooms (T17.18).
##
## * generated/tilesets/farm_room.tres: a tile set of two drawn tiles, a floor of boards and a
##   plastered wall (FarmBuild.room_texture), on the grid of the project's maps: squares of the
##   maps' tile, or the diamonds of an isometric project's ground (one tile there, the floor).
##
## The farm's map recipe paints the farmhouse and the animal houses with it where the packs
## have no interior tiles of their own (`use_floor`, `use_wall`): until then such a room took
## the roles `GROUND` and `WALL` of the tile set of the maps outside, so it was floored with
## the pack's grass, which changed with the season (RpgFarmSeasons replaces the pictures of a
## tile set, and a tile set is one resource for every map that uses it), and walled with its
## hedge. The drawn tiles are a tile set of their own that no outdoor map uses: a season does
## not change them. The wall tile has no collision; what blocks is the invisible border every
## map without a wall tile gets (MapGeo.border_collision).
##
## A room that exists is never built again, so this is for the rooms of new projects.

const RECIPE_VERSION := 1

const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const MapUtil := preload("../../lib/map_util.gd")
const IsoTileset := preload("../../lib/iso_tileset.gd")
const FarmBuild := preload("farm_build.gd")

const SOURCE_ID := 0
const FLOOR_TILE := Vector2i(0, 0)
const WALL_TILE := Vector2i(1, 0)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([FarmBuild.ROOM_TILESET])

func input_hash(ctx: BuildContext) -> String:
	var hashed := {"v": RECIPE_VERSION, "tile": FarmBuild.tile(ctx)}
	if MapGeo.is_isometric(ctx):
		var footprint := MapGeo.new(ctx).footprint
		hashed["iso"] = [footprint.x, footprint.y]
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := FarmBuild.tile(ctx)
	var diamond := MapGeo.new(ctx).footprint if MapGeo.is_isometric(ctx) else Vector2i.ZERO
	var tile_set := TileSet.new()
	var source := TileSetAtlasSource.new()
	if diamond != Vector2i.ZERO:
		IsoTileset.shape(tile_set, diamond)
		source.texture = FarmBuild.iso_room_texture(diamond)
		source.texture_region_size = diamond
	else:
		tile_set.tile_size = Vector2i(tile, tile)
		source.texture = FarmBuild.room_texture(tile)
		source.texture_region_size = Vector2i(tile, tile)
	tile_set.add_source(source, SOURCE_ID)
	source.create_tile(FLOOR_TILE)
	if diamond == Vector2i.ZERO:
		source.create_tile(WALL_TILE)
	DirAccess.make_dir_recursive_absolute(FarmBuild.ROOM_TILESET.get_base_dir())
	var err := ResourceSaver.save(tile_set, FarmBuild.ROOM_TILESET)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FarmBuild.ROOM_TILESET, "err": err}, FarmBuild.ROOM_TILESET))
	return issues

# ---------------------------------------------------------------- in a room

## The drawn tile set, or null when it was not built.
static func drawn_tile_set() -> TileSet:
	return load(FarmBuild.ROOM_TILESET) as TileSet if ResourceLoader.exists(FarmBuild.ROOM_TILESET) else null

## Gives `layer` the drawn tile set and fills `rect` with the floor of boards. False when the
## tile set is missing: the caller then paints what it painted before.
static func use_floor(layer: TileMapLayer, rect: Rect2i) -> bool:
	var drawn := drawn_tile_set()
	if drawn == null or layer == null:
		return false
	layer.tile_set = drawn
	MapUtil.fill(layer, rect, {"source_id": SOURCE_ID, "coords": FLOOR_TILE})
	return true

## Gives `layer` the drawn tile set and paints the plastered wall round `rect`, the cells of
## `skip` left open. False when the tile set is missing or has no wall (diamonds).
static func use_wall(layer: TileMapLayer, rect: Rect2i, skip: Array = []) -> bool:
	var drawn := drawn_tile_set()
	if drawn == null or layer == null:
		return false
	var source := drawn.get_source(SOURCE_ID) as TileSetAtlasSource
	if source == null or not source.has_tile(WALL_TILE):
		return false
	layer.tile_set = drawn
	MapUtil.border(layer, rect, {"source_id": SOURCE_ID, "coords": WALL_TILE}, skip)
	return true
