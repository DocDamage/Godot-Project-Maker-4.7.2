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
##
## **An isometric farm** (T17.14) gets the same tile set with diamonds: Godot's isometric shape
## with the footprint of the project's ground (IsoTileset.shape), and source 0 drawn as five
## diamonds (FarmBuild.iso_soil_texture). The `Soil` layer then lies on the same grid as the
## ground, and RpgField asks it for cells and places as it asks a layer of squares. Sources 1
## and 2 are there the isometric tile a pack tagged `soil` or `watered` (a flat tile of the
## project's tile set of diamonds, with the origin it has there); a sheet of square soil cannot
## lie on a diamond, so the kit's is not drawn for this view.

const RECIPE_VERSION := 3
## The version of what the recipe does for an isometric project only (T17.14): in the hash of
## such a project and of no other.
const ISO_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const IsoTileset := preload("../../lib/iso_tileset.gd")
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
## Ground that can be tilled and shows nothing: the plot of a field the map paints with a
## terrain of the ground (T17.31). Only a soil tile set of such a farm has it.
const PLOT_MARK := Vector2i(5, 0)
## The version of the field's terrains, in the hash of a farm that has them (T17.31).
const TERRAIN_VERSION := 1
const TilesetRecipe := preload("../tileset_recipe.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([FarmBuild.SOIL_TILESET])

func input_hash(ctx: BuildContext) -> String:
	var tile := FarmBuild.tile(ctx)
	var hashed := {"v": RECIPE_VERSION, "tile": tile, "soil": FarmBuild.soil_tile(ctx, "soil", tile), "watered": FarmBuild.soil_tile(ctx, "watered", tile)}
	if MapGeo.is_isometric(ctx):  # only an isometric project's hash has the keys (T17.14)
		var footprint := MapGeo.new(ctx).footprint
		hashed["iso"] = [footprint.x, footprint.y]
		hashed["iso_v"] = ISO_VERSION
		hashed["iso_soil"] = [FarmBuild.iso_soil_asset(ctx, "soil"), FarmBuild.iso_soil_asset(ctx, "watered")]
	# only a farm whose tile set has terrains for its field has the key (T17.31)
	var terrains := [FarmBuild.plot_terrain(ctx), FarmBuild.soil_terrain(ctx, "soil"), FarmBuild.soil_terrain(ctx, "watered")]
	if terrains != [{}, {}, {}]:
		hashed["terrain"] = [TERRAIN_VERSION, terrains]
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := FarmBuild.tile(ctx)
	var diamond := MapGeo.new(ctx).footprint if MapGeo.is_isometric(ctx) else Vector2i.ZERO
	var tile_set := TileSet.new()
	if diamond != Vector2i.ZERO:
		IsoTileset.shape(tile_set, diamond)
	else:
		tile_set.tile_size = Vector2i(tile, tile)
	for data_name in CUSTOM_DATA:
		tile_set.add_custom_data_layer()
		var index := tile_set.get_custom_data_layers_count() - 1
		tile_set.set_custom_data_layer_name(index, data_name)
		tile_set.set_custom_data_layer_type(index, TYPE_BOOL)
	var source := TileSetAtlasSource.new()
	# a field painted with a terrain of the ground (T17.31) is marked by a tile that shows nothing
	var marked := diamond == Vector2i.ZERO and not FarmBuild.plot_terrain(ctx).is_empty()
	if diamond != Vector2i.ZERO:
		source.texture = FarmBuild.iso_soil_texture(diamond)
		source.texture_region_size = diamond
	else:
		source.texture = FarmBuild.soil_texture(tile, marked)
		source.texture_region_size = Vector2i(tile, tile)
	tile_set.add_source(source, SOURCE_ID)
	for coords: Vector2i in [PLOT_TILE, TILLED_TILE, WATERED_TILE, WATER_TILE, WATER_MARK]:
		source.create_tile(coords)
	source.get_tile_data(PLOT_TILE, 0).set_custom_data("tillable", true)
	if marked:
		source.create_tile(PLOT_MARK)
		source.get_tile_data(PLOT_MARK, 0).set_custom_data("tillable", true)
	for coords: Vector2i in [WATER_TILE, WATER_MARK]:
		source.get_tile_data(coords, 0).set_custom_data("water", true)
	var soil_sets: Array = []
	for entry: Array in [[TILLED_SOURCE, "soil"], [WATERED_SOURCE, "watered"]]:
		var tag: String = entry[1]
		if diamond != Vector2i.ZERO:
			var iso_id: int = entry[0]
			_add_iso_soil(ctx, tile_set, iso_id, tag)
			continue
		var terrain := FarmBuild.soil_terrain(ctx, tag)
		if not terrain.is_empty() and _add_terrain_soil(tile_set, JsonUtil.to_int(entry[0]), tag, terrain, soil_sets, tile):
			continue
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

## Adds the tiles of a terrain of soil (FarmBuild.soil_terrain) to the soil's tile set as the
## source `own_id`, with a terrain set of their own named `tag` (T17.31): the field paints a
## tilled (or watered) cell with it, and its soil joins the soil round it. False, with nothing
## added, when the sheet cannot be loaded or its cell is not the farm's tile.
static func _add_terrain_soil(tile_set: TileSet, own_id: int, tag: String, terrain: Dictionary, sets: Array, tile: int) -> bool:
	var cell := JsonUtil.to_array(terrain.get("cell", []))
	var sheet := load(JsonUtil.to_str(terrain["path"])) as Texture2D
	if sheet == null or cell.size() != 2 or JsonUtil.to_int(cell[0]) != tile or JsonUtil.to_int(cell[1]) != tile:
		return false
	var spec := JsonUtil.to_dict(terrain["spec"])
	var set_index := tile_set.get_terrain_sets_count()
	tile_set.add_terrain_set()
	tile_set.set_terrain_set_mode(set_index, TilesetRecipe.TERRAIN_MODES.get(JsonUtil.to_str(spec.get("mode", "corners_and_sides")), TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES))
	tile_set.add_terrain(set_index)
	tile_set.set_terrain_name(set_index, 0, tag)
	sets.append({"name": JsonUtil.to_str(spec.get("name", ""))})
	var own := TileSetAtlasSource.new()
	own.texture = sheet
	own.texture_region_size = Vector2i(tile, tile)
	tile_set.add_source(own, own_id)
	for entry: Array in JsonUtil.to_array(terrain["tiles"]):
		var coords: Vector2i = entry[0]
		if (coords.x + 1) * tile > sheet.get_width() or (coords.y + 1) * tile > sheet.get_height():
			continue
		own.create_tile(coords)
		var td := own.get_tile_data(coords, 0)
		TilesetRecipe.apply_terrain(td, tile_set, sets, JsonUtil.to_dict(entry[1]))
		td.probability = JsonUtil.to_float(entry[2], 1.0)
	return own.get_tiles_count() > 0

## Adds the isometric tile a pack tagged `tag` to the soil's tile set as the one tile of the
## source `own_id`: the same picture of the same atlas, with the origin it has in the project's
## tile set of diamonds. Nothing when the packs have no such tile.
static func _add_iso_soil(ctx: BuildContext, tile_set: TileSet, own_id: int, tag: String) -> void:
	var asset_id := FarmBuild.iso_soil_asset(ctx, tag)
	if asset_id == "":
		return
	var geo := MapGeo.new(ctx)
	var iso_set := geo.load_tile_set()
	var found := geo.iso.tile_for(asset_id)
	if iso_set == null or found.is_empty():
		return
	var coords: Vector2i = found["coords"]
	var from := iso_set.get_source(JsonUtil.to_int(found["source"])) as TileSetAtlasSource
	if from == null or not from.has_tile(coords):
		return
	var own := TileSetAtlasSource.new()
	own.texture = from.texture
	own.margins = from.margins
	own.separation = from.separation
	own.texture_region_size = from.texture_region_size
	tile_set.add_source(own, own_id)
	own.create_tile(coords)
	own.get_tile_data(coords, 0).texture_origin = from.get_tile_data(coords, 0).texture_origin

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
	field.set("tile_px", RpgIso.unit(tile_set.tile_size) if RpgIso.is_iso(tile_set) else tile_set.tile_size.x)
	# tilled and watered soil painted with the terrains of their sheets (T17.31): a property
	# only a field that has them sets, so every other farm's map is what it was
	for i in tile_set.get_terrain_sets_count():
		if tile_set.get_terrains_count(i) < 1:
			continue
		match tile_set.get_terrain_name(i, 0):
			"soil":
				field.set("soil_terrain", i)
			"watered":
				field.set("watered_terrain", i)
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
