extends RefCounted
## The field of a farm (T17.05).
##
## * generated/tilesets/farm_soil.tres: the tile set of the `Soil` layer. Source 0 is drawn
##   here: ground that can be tilled (its custom data `tillable` is true: that, and nothing in
##   the art, is what the hoe asks), and a tilled and a watered tile nobody uses while the
##   catalog has its own. Source 1 is the tile of tilled soil and source 2 the tile of watered
##   soil: a pack's own (its tile sheet tagged `soil` or `watered`), else the farm kit's
##   (T17.02). The tile set also has the bool custom data `water` for a tile that fills the
##   can; no tile sets it yet.
## * `augment_map`, which starter_map_recipe calls for a farm: the `Soil` layer under the
##   entities, a plot of tillable ground on free cells near the spawn, and the node `Field`
##   (RpgField).
##
## **A stand-in until T17.06.** The world of a farm is, for now, the top-down starter map as it
## is planned for every kind, with this plot on it. The planned farm (the house with its bed,
## the bin, the pond, the yards) replaces `augment_map`; the tile set and the field stay. Of a
## pack's soil terrain one tile is used, the one that joins on every side: a field has no
## edges of its own yet.

const RECIPE_VERSION := 1

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
## The plot of the stand-in map: the first of these sizes (in cells) that finds room.
const PLOT_SIZES: Array[Vector2i] = [Vector2i(6, 4), Vector2i(5, 3), Vector2i(4, 3)]
## Cells kept free between the plot and the edge of the map.
const EDGE := 2

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
	for coords: Vector2i in [PLOT_TILE, TILLED_TILE, WATERED_TILE]:
		source.create_tile(coords)
	source.get_tile_data(PLOT_TILE, 0).set_custom_data("tillable", true)
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

# ---------------------------------------------------------------- the stand-in map (until T17.06)

## What the starter map's hash holds for a farm, so that a changed plot rebuilds nothing but a
## map that does not exist yet.
static func map_hash() -> Dictionary:
	return {"v": RECIPE_VERSION, "sizes": PLOT_SIZES, "edge": EDGE}

## Adds the `Soil` layer, the plot and the `Field` to a starter map that is being built. `nodes`
## are the map's nodes by name, `layout` is MapBuild.plan's, `house` the size of the starter
## building in cells ((0, 0) for none), `kept_free` cells nothing may lie on (doors).
static func augment_map(root: Node2D, nodes: Dictionary, layout: Dictionary, house: Vector2i, kept_free: Array[Vector2i]) -> void:
	var tile_set := load(FarmBuild.SOIL_TILESET) as TileSet
	var ysorted: Node = nodes.get("YSorted")
	if tile_set == null or ysorted == null:
		return
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
	var plot := plot_rect(layout, house, kept_free)
	if plot.size == Vector2i.ZERO:
		print("[rpggen] INFO starter_map: no room for a plot of tillable ground")
		return
	for y in range(plot.position.y, plot.end.y):
		for x in range(plot.position.x, plot.end.x):
			soil.set_cell(Vector2i(x, y), SOURCE_ID, PLOT_TILE)

## [source id, cell] of the one tile of `own_source` when the tile set has it, else the drawn
## tile `drawn` of source 0.
static func _own_tile(tile_set: TileSet, own_source: int, drawn: Vector2i) -> Array:
	if tile_set.has_source(own_source):
		var source := tile_set.get_source(own_source) as TileSetAtlasSource
		if source != null and source.get_tiles_count() > 0:
			return [own_source, source.get_tile_id(0)]
	return [SOURCE_ID, drawn]

## The cells of a layout nothing may be painted on: the houses with the row in front of their
## doors, what stands on the map, its paths, and where the player appears.
static func blocked_cells(layout: Dictionary, house: Vector2i, kept_free: Array[Vector2i]) -> Dictionary:
	var blocked := {}
	var houses: Array[Vector2i] = layout["buildings"]
	for at in houses:
		for dx in range(-1, maxi(1, house.x) + 1):
			for dy in range(-1, maxi(1, house.y) + 2):
				blocked[at + Vector2i(dx, dy)] = true
	for key: String in ["decorations", "npcs", "chests", "enemies", "path", "exit_path", "doors"]:
		if not layout.has(key):
			continue
		var raw: Array = layout[key]
		var cells: Array[Vector2i] = []
		cells.assign(raw)
		for cell in cells:
			blocked[cell] = true
	var spawn: Vector2i = layout["spawn"]
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			blocked[spawn + Vector2i(dx, dy)] = true
	for cell in kept_free:
		blocked[cell] = true
	return blocked

## The plot: the free rectangle nearest to the spawn, of the first size of PLOT_SIZES that fits.
## An empty rectangle when the map has no room.
static func plot_rect(layout: Dictionary, house: Vector2i, kept_free: Array[Vector2i]) -> Rect2i:
	var size: Vector2i = layout["size"]
	var spawn: Vector2i = layout["spawn"]
	var blocked := blocked_cells(layout, house, kept_free)
	for wanted in PLOT_SIZES:
		var best := Rect2i()
		var best_distance := -1
		for y in range(EDGE, size.y - EDGE - wanted.y + 1):
			for x in range(EDGE, size.x - EDGE - wanted.x + 1):
				var rect := Rect2i(Vector2i(x, y), wanted)
				if not _is_free(rect, blocked):
					continue
				var middle := rect.position * 2 + rect.size
				var distance := absi(middle.x - spawn.x * 2) + absi(middle.y - spawn.y * 2)
				if best_distance < 0 or distance < best_distance:
					best = rect
					best_distance = distance
		if best_distance >= 0:
			return best
	return Rect2i()

static func _is_free(rect: Rect2i, blocked: Dictionary) -> bool:
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			if blocked.has(Vector2i(x, y)):
				return false
	return true
