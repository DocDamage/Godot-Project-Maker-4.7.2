extends RefCounted
## The field of a farm (T17.05).
##
## * generated/tilesets/farm_soil.tres: the tile set of the `Soil` layer. Source 0 is drawn
##   here: ground that can be tilled (its custom data `tillable` is true: that, and nothing in
##   the art, is what the hoe asks), a tilled and a watered tile nobody uses while the catalog
##   has its own, and two tiles whose custom data `water` is true (a cell that fills the can):
##   drawn water, and a tile that shows nothing, for a cell whose water the map paints itself
##   (the pack's water tile on the ground, or a well). Source 1 is the tile of tilled soil and
##   source 2 the tile of watered soil: a pack's own (its tile sheet tagged `soil` or
##   `watered`), else the farm kit's (T17.02).
## * `add_field`, which the farm's map recipe calls (T17.06): the `Soil` layer under what
##   stands on the map and the node `Field` (RpgField). The recipe then writes the plan's
##   cells into the layer: `PLOT_TILE` where the plan says the ground can be tilled, a water
##   tile where the can is filled.
##
## Of a pack's soil terrain one tile is used, the one that joins on every side: a field has no
## edges of its own yet.

const RECIPE_VERSION := 3

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")

const SOURCE_ID := 0
const PLOT_TILE := Vector2i(0, 0)
const TILLED_TILE := Vector2i(1, 0)
const WATERED_TILE := Vector2i(2, 0)
## The sources of the tiles the catalog has, when it has them: the sheet, with its one tile.
const TILLED_SOURCE := 1
const WATERED_SOURCE := 2
const CUSTOM_DATA: Array[String] = ["tillable", "water"]
## Cells that fill the can: drawn water, and one that shows nothing (the map draws its water).
const WATER_TILE := Vector2i(3, 0)
const WATER_MARK := Vector2i(4, 0)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([FarmBuild.SOIL_TILESET])

func input_hash(ctx: BuildContext) -> String:
	var tile := FarmBuild.tile(ctx)
	return ctx.stable_hash({"v": RECIPE_VERSION, "tile": tile, "soil": FarmBuild.soil_tile(ctx, "soil", tile), "watered": FarmBuild.soil_tile(ctx, "watered", tile)})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := FarmBuild.tile(ctx)
	var tile_set := TileSet.new()
	tile_set.tile_size = Vector2i(tile, tile)
	for data_name in CUSTOM_DATA:
		tile_set.add_custom_data_layer()
		var index := tile_set.get_custom_data_layers_count() - 1
		tile_set.set_custom_data_layer_name(index, data_name)
		tile_set.set_custom_data_layer_type(index, TYPE_BOOL)
	var source := TileSetAtlasSource.new()
	source.texture = FarmBuild.soil_texture(tile)
	source.texture_region_size = Vector2i(tile, tile)
	tile_set.add_source(source, SOURCE_ID)
	for coords: Vector2i in [PLOT_TILE, TILLED_TILE, WATERED_TILE, WATER_TILE, WATER_MARK]:
		source.create_tile(coords)
	source.get_tile_data(PLOT_TILE, 0).set_custom_data("tillable", true)
	for coords: Vector2i in [WATER_TILE, WATER_MARK]:
		source.get_tile_data(coords, 0).set_custom_data("water", true)
	for entry: Array in [[TILLED_SOURCE, "soil"], [WATERED_SOURCE, "watered"]]:
		var tag: String = entry[1]
		var found := FarmBuild.soil_tile(ctx, tag, tile)
		if found.is_empty():
			continue
		var sheet := load(JsonUtil.to_str(found["path"])) as Texture2D
		if sheet == null:
			continue
		var coords: Vector2i = found["coords"]
		var own := TileSetAtlasSource.new()
		own.texture = sheet
		own.texture_region_size = Vector2i(tile, tile)
		var own_id: int = entry[0]
		tile_set.add_source(own, own_id)
		own.create_tile(coords)
	DirAccess.make_dir_recursive_absolute(FarmBuild.SOIL_TILESET.get_base_dir())
	var err := ResourceSaver.save(tile_set, FarmBuild.SOIL_TILESET)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": FarmBuild.SOIL_TILESET, "err": err}, FarmBuild.SOIL_TILESET))
	return issues

# ---------------------------------------------------------------- on a map

## Adds the `Soil` layer and the `Field` (RpgField) to a map that is being built, under what
## stands on it (`nodes` are the map's nodes by name, MapUtil.build_layers). Returns the layer,
## which the caller paints, or null when the tile set is missing.
static func add_field(root: Node2D, nodes: Dictionary) -> TileMapLayer:
	var tile_set := load(FarmBuild.SOIL_TILESET) as TileSet
	var ysorted: Node = nodes.get("YSorted")
	if tile_set == null or ysorted == null:
		return null
	var soil := TileMapLayer.new()
	soil.name = "Soil"
	soil.tile_set = tile_set
	soil.collision_enabled = false
	root.add_child(soil)
	root.move_child(soil, ysorted.get_index())
	var field := Node2D.new()
	field.name = "Field"
	SceneUtil.attach_script(field, FarmBuild.FIELD)
	# the catalog's own tiles of tilled and watered soil when the tile set has them, else drawn
	var tilled := _own_tile(tile_set, TILLED_SOURCE, TILLED_TILE)
	var watered := _own_tile(tile_set, WATERED_SOURCE, WATERED_TILE)
	field.set("tilled_source", tilled[0])
	field.set("tilled_tile", tilled[1])
	field.set("watered_source", watered[0])
	field.set("watered_tile", watered[1])
	field.set("tile_px", tile_set.tile_size.x)
	root.add_child(field)
	root.move_child(field, soil.get_index() + 1)
	return soil

## [source id, cell] of the one tile of `own_source` when the tile set has it, else the drawn
## tile `drawn` of source 0.
static func _own_tile(tile_set: TileSet, own_source: int, drawn: Vector2i) -> Array:
	if tile_set.has_source(own_source):
		var source := tile_set.get_source(own_source) as TileSetAtlasSource
		if source != null and source.get_tiles_count() > 0:
			return [own_source, source.get_tile_id(0)]
	return [SOURCE_ID, drawn]
