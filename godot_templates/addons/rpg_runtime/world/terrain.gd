class_name RpgTerrain
extends RefCounted
## Painting with the terrains of a TileSet (T17.31), for the builder's map recipes and for a
## farm's field at play.
##
## Godot paints a terrain itself (`TileMapLayer.set_cells_terrain_connect` for an area,
## `set_cells_terrain_path` for a path or a road): it chooses for every cell the tile whose
## peering bits fit its neighbours, and repaints the neighbours of the cells it paints. Where
## several tiles fit alike (the plain variants of a terrain's middle) it chooses at random,
## and the probe of T17.31 found that choice different on every run (it draws from the global
## random generator). So after Godot has painted, `settle` chooses again among the tiles with
## the same terrain and the same peering bits, by the cell and a seed, weighted by each tile's
## `probability`: the same map comes out of every run.
##
## A peering bit of `-1` is nothing: a terrain drawn over transparency, or over another ground
## that has no terrain, is painted over plain tiles and over empty cells alike, with
## `ignore_empty_terrains` false (the probe: the edges come out right in both, and plain cells
## around are not changed).

## TileSet instance id -> {signature: [[source, coords, probability], ...]}
static var _index: Dictionary = {}

## Paints `cells` with the terrain `terrain` of the set `terrain_set` and settles the variants
## of what Godot painted, by `map_seed`.
static func paint_area(layer: TileMapLayer, cells: Array[Vector2i], terrain_set: int, terrain: int, map_seed: int) -> void:
	if cells.is_empty() or layer.tile_set == null:
		return
	layer.set_cells_terrain_connect(cells, terrain_set, terrain, false)
	settle(layer, around(cells), map_seed)

## Paints a path through `cells` in their order (each cell joins the one before and after it,
## and no other) and settles the variants.
static func paint_path(layer: TileMapLayer, cells: Array[Vector2i], terrain_set: int, terrain: int, map_seed: int) -> void:
	if cells.is_empty() or layer.tile_set == null:
		return
	layer.set_cells_terrain_path(cells, terrain_set, terrain, false)
	settle(layer, around(cells), map_seed)

## The cells and their eight neighbours: what painting a terrain may have changed.
static func around(cells: Array[Vector2i]) -> Array[Vector2i]:
	var seen := {}
	var out: Array[Vector2i] = []
	for cell in cells:
		for dy in range(-1, 2):
			for dx in range(-1, 2):
				var at := cell + Vector2i(dx, dy)
				if not seen.has(at):
					seen[at] = true
					out.append(at)
	return out

## The cells of a rectangle, row by row.
static func rect_cells(rect: Rect2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in range(rect.position.y, rect.end.y):
		for x in range(rect.position.x, rect.end.x):
			out.append(Vector2i(x, y))
	return out

## Chooses again, for every cell of `cells` whose tile has a terrain, among the tiles of the
## TileSet with the same terrain and peering bits, by the cell and `map_seed`.
static func settle(layer: TileMapLayer, cells: Array[Vector2i], map_seed: int) -> void:
	var ts := layer.tile_set
	if ts == null:
		return
	var index := _tiles_by_signature(ts)
	for cell in cells:
		var source := layer.get_cell_source_id(cell)
		if source < 0:
			continue
		var td := layer.get_cell_tile_data(cell)
		if td == null or td.terrain_set < 0:
			continue
		var choices: Array = index.get(signature(td), [])
		if choices.size() < 2:
			continue
		var chosen: Array = pick(choices, cell, map_seed)
		var coords: Vector2i = chosen[1]
		if RpgUtil.to_int(chosen[0]) != source or coords != layer.get_cell_atlas_coords(cell):
			layer.set_cell(cell, RpgUtil.to_int(chosen[0]), coords, layer.get_cell_alternative_tile(cell))

## Paints `cells` with `tile` ({source_id, coords}) or, when the tile is the middle of a terrain
## that has plain variants, with one of them chosen by the cell and `map_seed`: a ground that varies.
static func fill_varied(layer: TileMapLayer, cells: Array[Vector2i], tile: Dictionary, map_seed: int) -> void:
	if tile.is_empty():
		return
	var source: int = tile["source_id"]
	var coords: Vector2i = tile["coords"]
	var choices := variants_of(layer.tile_set, source, coords)
	for cell in cells:
		if choices.size() < 2:
			layer.set_cell(cell, source, coords, 0)
			continue
		var chosen: Array = pick(choices, cell, map_seed)
		layer.set_cell(cell, RpgUtil.to_int(chosen[0]), chosen[1], 0)

## The tiles that are `coords` of `source` once more: the same terrain with the same peering
## bits ([[source, coords, probability], ...]); [] for a tile without a terrain.
static func variants_of(ts: TileSet, source: int, coords: Vector2i) -> Array:
	if ts == null or not ts.has_source(source):
		return []
	var src := ts.get_source(source) as TileSetAtlasSource
	if src == null or not src.has_tile(coords):
		return []
	var td := src.get_tile_data(coords, 0)
	if td == null or td.terrain_set < 0:
		return []
	return _tiles_by_signature(ts).get(signature(td), [])

## What a tile is to a terrain: its set, its terrain and every peering bit its set's mode has.
static func signature(td: TileData) -> String:
	var parts := PackedStringArray([str(td.terrain_set), str(td.terrain)])
	for bit in 16:
		if td.is_valid_terrain_peering_bit(bit as TileSet.CellNeighbor):
			parts.append(str(td.get_terrain_peering_bit(bit as TileSet.CellNeighbor)))
	return ",".join(parts)

## One of `choices` ([source, coords, probability]) for `cell`, weighted by the probabilities:
## the same for the same cell and seed on every run and every machine.
static func pick(choices: Array, cell: Vector2i, map_seed: int) -> Array:
	var total := 0.0
	for choice: Array in choices:
		total += maxf(0.0, RpgUtil.to_float(choice[2]))
	if total <= 0.0:
		return choices[0]
	var at := unit(cell, map_seed) * total
	for choice: Array in choices:
		at -= maxf(0.0, RpgUtil.to_float(choice[2]))
		if at < 0.0:
			return choice
	return choices[choices.size() - 1]

## A number from 0 to 1 (not 1) for a cell and a seed: integer arithmetic of 32 bits, the same
## everywhere.
static func unit(cell: Vector2i, map_seed: int) -> float:
	var h := (map_seed & 0x7fffffff) ^ 0x2545F491
	for value: int in [cell.x, cell.y]:
		h = (h ^ (value & 0xffffffff)) & 0xffffffff
		h = (h * 0x01000193) & 0xffffffff
		h = (h ^ (h >> 15)) & 0xffffffff
		h = (h * 0x2c1b3c6d) & 0xffffffff
		h = (h ^ (h >> 12)) & 0xffffffff
	return float(h & 0xffffff) / float(0x1000000)

## Every tile of the TileSet with a terrain, by its signature, in the order of the sources and
## their tiles; worked out once a TileSet (a TileSet is not changed while a map is painted).
static func _tiles_by_signature(ts: TileSet) -> Dictionary:
	var key := ts.get_instance_id()
	if _index.has(key):
		return _index[key]
	var out := {}
	for i in ts.get_source_count():
		var source_id := ts.get_source_id(i)
		var src := ts.get_source(source_id) as TileSetAtlasSource
		if src == null:
			continue
		for t in src.get_tiles_count():
			var coords := src.get_tile_id(t)
			var td := src.get_tile_data(coords, 0)
			if td == null or td.terrain_set < 0:
				continue
			var sig := signature(td)
			if not out.has(sig):
				out[sig] = []
			var list: Array = out[sig]
			list.append([source_id, coords, td.probability])
	_index[key] = out
	return out

## Forgets what was worked out of the TileSets (a recipe that changes one calls it).
static func forget() -> void:
	_index.clear()
