extends RefCounted
## Which tiles of a TileSet a room is painted with. The TileSet says it itself (the side-view parts
## the TileSet recipe gave it): a tile with a polygon on the one-way physics layer is a platform,
## one with the custom data `ladder`, `hazard` or `breakable` is that, and the ground is the sheet
## chosen as GROUND. A kind the packs do not have comes from the generated kit sheet
## (generated/side_kit/side_kit.png, rpggen adds it to the catalog), so a room can always be built.

const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const ONE_WAY_PHYSICS := 1
const KIT_PACK := "rpggen_side_kit"

## {top, fill, one_way: [left, middle, right], ladder, hazard, breakable}: each a tile
## {source_id, coords}, or {} when the TileSet has none (the ground is never {}).
static func find(ctx: BuildContext, def: Dictionary, tile_set: TileSet) -> Dictionary:
	var kit := {"top": {}, "fill": {}, "one_way": [], "ladder": {}, "hazard": {}, "breakable": {}}
	var kit_sources := {}
	var def_sources: Array = def.get("sources", [])
	for s: Dictionary in def_sources:
		var asset_id: String = s["asset"]
		if asset_id.begins_with(KIT_PACK + "."):
			kit_sources[JsonUtil.to_int(s["source_id"])] = true
	# the packs' own tiles first, the kit's only for what they lack
	for pass_kit: bool in [false, true]:
		for i in tile_set.get_source_count():
			var source_id := tile_set.get_source_id(i)
			if kit_sources.has(source_id) != pass_kit:
				continue
			var src := tile_set.get_source(source_id) as TileSetAtlasSource
			if src == null:
				continue
			_scan(tile_set, src, source_id, kit)
	_ground(ctx, def, tile_set, kit)
	return kit

static func _has(tile_set: TileSet, data: TileData, layer_name: String) -> bool:
	return tile_set.get_custom_data_layer_by_name(layer_name) >= 0 and JsonUtil.to_bool(data.get_custom_data(layer_name))

static func _scan(tile_set: TileSet, src: TileSetAtlasSource, source_id: int, kit: Dictionary) -> void:
	var coords_list: Array[Vector2i] = []
	for i in src.get_tiles_count():
		coords_list.append(src.get_tile_id(i))
	coords_list.sort_custom(func(a: Vector2i, b: Vector2i) -> bool: return a.y < b.y or (a.y == b.y and a.x < b.x))
	var planks: Array = kit["one_way"]
	var first_run := planks.is_empty()
	for coords in coords_list:
		var data := src.get_tile_data(coords, 0)
		var tile := {"source_id": source_id, "coords": coords}
		if tile_set.get_physics_layers_count() > ONE_WAY_PHYSICS and data.get_collision_polygons_count(ONE_WAY_PHYSICS) > 0:
			# the first run of neighbours in a row is a plank: its left end, middle and right end
			if first_run and (planks.is_empty() or _beside(planks[planks.size() - 1], tile)) and planks.size() < 3:
				planks.append(tile)
		elif _has(tile_set, data, "ladder"):
			if JsonUtil.to_dict(kit["ladder"]).is_empty():
				kit["ladder"] = tile
		elif _has(tile_set, data, "hazard"):
			if JsonUtil.to_dict(kit["hazard"]).is_empty():
				kit["hazard"] = tile
		elif _has(tile_set, data, "breakable"):
			if JsonUtil.to_dict(kit["breakable"]).is_empty():
				kit["breakable"] = tile

static func _beside(a: Variant, b: Dictionary) -> bool:
	var left := JsonUtil.to_dict(a)
	var left_coords: Vector2i = left["coords"]
	var right_coords: Vector2i = b["coords"]
	return left["source_id"] == b["source_id"] and left_coords + Vector2i(1, 0) == right_coords

## A tile of plain solid ground: on the world physics layer, and none of the special kinds.
static func _plain(tile_set: TileSet, src: TileSetAtlasSource, coords: Vector2i) -> bool:
	if not src.has_tile(coords):
		return false
	var data := src.get_tile_data(coords, 0)
	if data.get_collision_polygons_count(0) == 0:
		return false
	for layer_name: String in ["ladder", "hazard", "breakable"]:
		if _has(tile_set, data, layer_name):
			return false
	return true

## The ground: the sheet chosen in Mapping (config.starter.ground), else the first GROUND sheet,
## else any sheet with a solid tile. `top` is its first plain tile and `fill` the tile below it
## (what lies under the surface) when that one is plain ground too.
static func _ground(ctx: BuildContext, def: Dictionary, tile_set: TileSet, kit: Dictionary) -> void:
	var wanted := JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	var candidates: Array[Dictionary] = []
	if wanted != "":
		candidates.append(MapUtil.tile_of_asset(ctx, def, tile_set, wanted))
	candidates.append(MapUtil.find_tile(ctx, def, tile_set, "GROUND"))
	for found in candidates:
		if found.is_empty():
			continue
		var source_id: int = found["source_id"]
		var src := tile_set.get_source(source_id) as TileSetAtlasSource
		for i in src.get_tiles_count():
			var coords := src.get_tile_id(i)
			if _plain(tile_set, src, coords):
				kit["top"] = {"source_id": source_id, "coords": coords}
				var below := coords + Vector2i(0, 1)
				kit["fill"] = {"source_id": source_id, "coords": below} if _plain(tile_set, src, below) else kit["top"]
				return
	for i in tile_set.get_source_count():  # no GROUND sheet at all: anything solid
		var source_id := tile_set.get_source_id(i)
		var src := tile_set.get_source(source_id) as TileSetAtlasSource
		if src == null:
			continue
		for t in src.get_tiles_count():
			if _plain(tile_set, src, src.get_tile_id(t)):
				kit["top"] = {"source_id": source_id, "coords": src.get_tile_id(t)}
				kit["fill"] = kit["top"]
				return

## The plank tile for a cell of a run: `left` and `right` say whether the run goes on there.
static func plank(kit: Dictionary, left: bool, right: bool) -> Dictionary:
	var planks: Array = kit["one_way"]
	if planks.is_empty():
		return {}
	if planks.size() < 3:
		return planks[0]
	if not left:
		return planks[0]
	return planks[1] if right else planks[2]
