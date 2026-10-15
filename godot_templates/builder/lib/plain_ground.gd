extends RefCounted
## The plain ground of a farm's maps (after T17.29): the tile of the ground sheet that rpggen
## measured to be plain ground (rpggen/core/farm_ground.py writes it into the farm's section of
## the plan file: `farm.ground`), in the place of the sheet's first tile, which on the real
## farming packs is no ground to walk on. Only a farm seen from above has the key; every other
## project, and an isometric farm, paints its ground as it did.
##
##     var ground := PlainGround.tile(geo)    # {source_id, coords}, {} without the key
##
## One tile, laid everywhere: a ground that varies and joins the soil, the water and the paths
## is painted with the tile set's terrains (T17.31). The tile is a cell of the pack's own sheet,
## so a farm whose sheets change with the seasons (RpgFarmSeasons) swaps it as before.

const JsonUtil := preload("json_util.gd")
const MapUtil := preload("map_util.gd")
const MapGeo := preload("map_geo.gd")

const PLAN_PATH := "res://rpggen/world_plan.json"
## The version of what is painted, for the recipes' hashes.
const VERSION := 1

## `farm.ground` of the plan file, or {}.
static func stored() -> Dictionary:
	if not FileAccess.file_exists(PLAN_PATH):
		return {}
	var farm := JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.read(PLAN_PATH)).get("farm", {}))
	return JsonUtil.to_dict(farm.get("ground", {}))

## {source_id, coords} of the stored ground in the tile set of `geo`, or {} when there is none,
## the view is isometric, or the tile set has no source of its sheet or no such tile.
static func tile(geo: MapGeo) -> Dictionary:
	var ground := stored()
	if ground.is_empty() or geo.isometric:
		return {}
	var tile_set := geo.tile_set
	if tile_set == null:
		tile_set = geo.load_tile_set()
	if tile_set == null:
		return {}
	var source_id := -1
	for s in MapUtil._sorted_sources(geo.def):
		if JsonUtil.to_str(s["asset"]) == JsonUtil.to_str(ground.get("asset", "")):
			source_id = JsonUtil.to_int(s["source_id"])
	if source_id < 0 or not tile_set.has_source(source_id):
		return {}
	var src := tile_set.get_source(source_id) as TileSetAtlasSource
	var pair := JsonUtil.to_array(ground.get("base", []))
	if src == null or pair.size() != 2:
		return {}
	var coords := Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1]))
	return {"source_id": source_id, "coords": coords} if src.has_tile(coords) else {}
