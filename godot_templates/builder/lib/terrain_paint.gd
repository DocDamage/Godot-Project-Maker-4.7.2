extends RefCounted
## Which terrain of a tile set paints what on a map (T17.31).
##
## The catalog's tile set definition lists its terrain sets in the order the TileSet has them
## (`tileset_recipe.ensure_terrain_sets`), each with what rpggen read of it: the `surface` of
## its middle (`grass`, `dirt`, `sand`, `water`, `stone`, `path`, `soil`, ...), whether it is
## drawn `over` another ground or over nothing, its `shape` (`any`: every shape of an area or a
## path, a 47-tile blob, a corner set, an RPG Maker block; `area`: areas two cells wide and
## more, a 3x3 block; `path`: a terrain that joins at its sides, one cell wide; `plain`: the
## variants of a plain ground and nothing else) and the `sheet` it was read from. A terrain set
## of a Tiled map (wang sets) has none of these: its terrains' names say the surface.
##
##     var found := TerrainPaint.find(ctx, def, tile_set, TerrainPaint.WATER_SURFACES, TerrainPaint.AREA_SHAPES)
##     if not found.is_empty():
##         RpgTerrain.paint_area(layer, cells, found["set"], found["terrain"], seed)
##
## A map recipe whose tile set has terrains adds `hash_part(ctx)` to its hash: the hash of every
## other project is what it was.

const JsonUtil := preload("json_util.gd")
const BuildContext := preload("build_context.gd")

## The version of how maps are painted with terrains, in the hash of a map recipe whose tile set
## has terrains.
const VERSION := 1

const ROAD_SURFACES: Array[String] = ["path", "road", "dirt", "sand", "stone", "soil"]
const WATER_SURFACES: Array[String] = ["water"]
const SOIL_SURFACES: Array[String] = ["soil", "dirt", "sand"]
const WET_SURFACES: Array[String] = ["soil_wet"]
## The surfaces a patch of other ground may be, in the order they are taken.
const PATCH_SURFACES: Array[String] = ["dirt", "sand", "grass", "stone", "snow", "path"]
const AREA_SHAPES: Array[String] = ["any", "area"]
const PATH_SHAPES: Array[String] = ["path", "any"]
const SOIL_SHAPES: Array[String] = ["any", "area", "path"]

## The terrain sets of a definition, each with its `index` in the TileSet.
static func specs(def: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var sets := JsonUtil.to_array(def.get("terrain_sets", []))
	for i in sets.size():
		var spec := JsonUtil.to_dict(sets[i]).duplicate()
		spec["index"] = i
		out.append(spec)
	return out

## What a map recipe adds to its hash: `{terrain_v: VERSION}` when a tile set of the project has
## terrains, nothing for any other project.
static func hash_part(ctx: BuildContext) -> Dictionary:
	for def: Dictionary in ctx.catalog.tileset_defs():
		if not JsonUtil.to_array(def.get("terrain_sets", [])).is_empty():
			return {"terrain_v": VERSION}
	return {}

## The surface a terrain of a set is: the set's `surface`, else the terrain's own name in small
## letters (a wang set of Tiled).
static func surface_of(spec: Dictionary, terrain: int = 0) -> String:
	if spec.has("surface"):
		return JsonUtil.to_str(spec["surface"])
	var terrains := JsonUtil.to_array(spec.get("terrains", []))
	if terrain < terrains.size():
		return JsonUtil.to_str(JsonUtil.to_dict(terrains[terrain]).get("name", "")).to_lower()
	return ""

## The terrain that paints one of `surfaces` (the first surface that has one), in a set whose
## shape is one of `shapes`: `{set, terrain, surface, shape, over, sheet}`, or {} when the tile
## set has none. Of several, a set read from a sheet whose role is one of `roles` goes first,
## then the first in the definition. `avoid` is a surface not to take (the ground's own).
## Without a `tile_set` (a recipe that runs before the maps) the definition alone is asked.
static func find(ctx: BuildContext, def: Dictionary, tile_set: TileSet, surfaces: Array, shapes: Array, roles: Array = [], avoid: String = "") -> Dictionary:
	# a terrain of a sheet that says it is indoors (a dungeon's floor, a house's) only when no
	# other has the surface: these are the maps outdoors
	var found := _find(ctx, def, tile_set, surfaces, shapes, roles, avoid, true)
	return found if not found.is_empty() else _find(ctx, def, tile_set, surfaces, shapes, roles, avoid, false)

## The words of a sheet's name and folders that say it is no ground outdoors.
const INDOOR_WORDS: Array[String] = ["dungeon", "cave", "caves", "house", "interior", "indoor", "temple", "castle", "barn", "mine"]

static func _indoors(ctx: BuildContext, asset_id: String) -> bool:
	if ctx == null or asset_id == "":
		return false
	var asset := ctx.catalog.asset(asset_id)
	var path := JsonUtil.to_str(asset.get("path", "")).to_lower()
	for separator: String in ["/", "_", "-", ".", " "]:
		path = path.replace(separator, " ")
	var words := path.split(" ", false)
	for word in INDOOR_WORDS:
		if words.has(word):
			return true
	return false

static func _find(ctx: BuildContext, def: Dictionary, tile_set: TileSet, surfaces: Array, shapes: Array, roles: Array, avoid: String, outdoors: bool) -> Dictionary:
	var all := specs(def)
	for surface: Variant in surfaces:
		var wanted := JsonUtil.to_str(surface)
		if wanted == avoid:
			continue
		var best := {}
		for spec in all:
			var index := JsonUtil.to_int(spec["index"])
			if tile_set != null and index >= tile_set.get_terrain_sets_count():
				continue
			if outdoors and _indoors(ctx, JsonUtil.to_str(spec.get("sheet", ""))):
				continue
			var shape := JsonUtil.to_str(spec.get("shape", "any"))
			if not shapes.has(shape):
				continue
			var terrains := JsonUtil.to_array(spec.get("terrains", []))
			for t in terrains.size():
				if not _names(surface_of(spec, t), wanted):
					continue
				var found := {
					"set": index, "terrain": t, "surface": wanted, "shape": shape,
					"over": JsonUtil.to_str(spec.get("over", "ground")),
					"sheet": JsonUtil.to_str(spec.get("sheet", "")),
					"mode": JsonUtil.to_str(spec.get("mode", "corners_and_sides")),
				}
				var role := _role_of(ctx, JsonUtil.to_str(spec.get("sheet", "")))
				if not roles.is_empty() and roles.has(role):
					return found
				if best.is_empty():
					best = found
				break
		if not best.is_empty():
			return best
	return {}

## terrain's name that has it among its words ("Dark Grass" is grass).
static func _names(have: String, want: String) -> bool:
	if have == want:
		return true
	if have.contains("_") and not want.contains("_"):
		return false  # soil_wet is no soil
	for word in have.replace("-", " ").replace("_", " ").split(" ", false):
		if word == want:
			return true
	return false

static func _role_of(ctx: BuildContext, asset_id: String) -> String:
	if ctx == null or asset_id == "":
		return ""
	var asset := ctx.catalog.asset(asset_id)
	if asset.is_empty():
		return ""
	return JsonUtil.to_str(ctx.catalog.effective(asset).get("role", ""))

## The surface of the tile `tile` ({source_id, coords}) of a tile set painted from `def`, when
## it is the middle of a terrain: "" for a tile of no terrain.
static func surface_of_tile(def: Dictionary, tile_set: TileSet, tile: Dictionary) -> String:
	if tile_set == null or tile.is_empty():
		return ""
	var source := JsonUtil.to_int(tile["source_id"])
	if not tile_set.has_source(source):
		return ""
	var src := tile_set.get_source(source) as TileSetAtlasSource
	var coords: Vector2i = tile["coords"]
	if src == null or not src.has_tile(coords):
		return ""
	var td := src.get_tile_data(coords, 0)
	if td == null or td.terrain_set < 0:
		return ""
	var all := specs(def)
	if td.terrain_set >= all.size():
		return ""
	return surface_of(all[td.terrain_set], td.terrain)

## The middle of the terrain set `set_index` of a tile set: the first tile (by source, then tile)
## of that set whose every peering bit is its terrain; {} when it has none.
static func middle_of(tile_set: TileSet, set_index: int) -> Dictionary:
	if tile_set == null or set_index < 0:
		return {}
	for i in tile_set.get_source_count():
		var source_id := tile_set.get_source_id(i)
		var src := tile_set.get_source(source_id) as TileSetAtlasSource
		if src == null:
			continue
		for t in src.get_tiles_count():
			var coords := src.get_tile_id(t)
			var td := src.get_tile_data(coords, 0)
			if td != null and td.terrain_set == set_index and _whole(td):
				return {"source_id": source_id, "coords": coords}
	return {}

static func _whole(td: TileData) -> bool:
	var any := false
	for bit in 16:
		if td.is_valid_terrain_peering_bit(bit as TileSet.CellNeighbor):
			any = true
			if td.get_terrain_peering_bit(bit as TileSet.CellNeighbor) != td.terrain:
				return false
	return any

## The ground a map is filled with when `tile` ({source_id, coords}, the first tile of the
## ground's sheet) is a piece of a terrain: the middle of that terrain (the first tile of a real
## sheet is mostly a corner of one, T17.31). The sheet of an RPG Maker A2 block, whose tiles
## have no terrain, gives the middle of the first terrain rpggen composed of it. `tile` itself
## for any other tile, and for every tile of a tile set without terrains.
static func ground_middle(def: Dictionary, tile_set: TileSet, tile: Dictionary, asset_id: String = "") -> Dictionary:
	if tile_set == null or tile.is_empty():
		return tile
	var source := JsonUtil.to_int(tile["source_id"])
	var src := tile_set.get_source(source) as TileSetAtlasSource if tile_set.has_source(source) else null
	var coords: Vector2i = tile["coords"]
	var td := src.get_tile_data(coords, 0) if src != null and src.has_tile(coords) else null
	if td != null and td.terrain_set >= 0:
		if _whole(td):
			return tile
		var middle := middle_of(tile_set, td.terrain_set)
		return middle if not middle.is_empty() else tile
	if asset_id == "":
		return tile
	# the A2 block's composed terrains are the assets generated.<the sheet's id as a slug>_b<n>
	var prefix := "generated." + asset_id.replace(".", "_").replace("#", "_") + "_"
	for spec in specs(def):
		if JsonUtil.to_str(spec.get("sheet", "")).begins_with(prefix):
			var middle := middle_of(tile_set, JsonUtil.to_int(spec["index"]))
			if not middle.is_empty():
				return middle
	return tile

## The note a map recipe gives when its map exists and is kept as it was painted while the tile
## set now has terrains (T17.31): a map made now would be painted with them. {} for a project
## without terrains, and for a map that was made from the inputs the recipe has now
## (`in_hash`, the recipe's hash as the build state recorded it for the map).
static func kept_map(ctx: BuildContext, path: String, in_hash: String) -> Dictionary:
	if hash_part(ctx).is_empty() or ctx.should_skip(path, in_hash):
		return {}
	return ctx.make_issue("TILE-015", {"map": path}, path)
