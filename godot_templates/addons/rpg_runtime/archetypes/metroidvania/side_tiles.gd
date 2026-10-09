class_name RpgSideTiles
extends RefCounted
## What the tiles of a side-view room say: the custom data `ladder`, `hazard` and `breakable`
## (bool, set by the TileSet recipe for a metroidvania) and the one-way physics layer.

const LADDER := "ladder"
const HAZARD := "hazard"
const BREAKABLE := "breakable"
## The TileSet's physics layer for one-way platforms (the first, 0, is the solid world).
const ONE_WAY_PHYSICS := 1
## The collision layer one-way platforms are on (named "one_way" in the project settings).
const ONE_WAY_LAYER := 11

## Every TileMapLayer below `root`, in tree order.
static func layers_of(root: Node) -> Array[TileMapLayer]:
	var out: Array[TileMapLayer] = []
	if root == null:
		return out
	for node in root.find_children("*", "TileMapLayer", true, false):
		out.append(node as TileMapLayer)
	return out

## The cell of `layer` that holds the global point `at`.
static func cell_at(layer: TileMapLayer, at: Vector2) -> Vector2i:
	var local := at - RpgUtil.world_position(layer)
	var tile := layer.tile_set.tile_size
	return Vector2i(floori(local.x / tile.x), floori(local.y / tile.y))

## The middle of a cell of `layer`, as a global point.
static func cell_center(layer: TileMapLayer, cell: Vector2i) -> Vector2:
	var tile := Vector2(layer.tile_set.tile_size)
	return RpgUtil.world_position(layer) + (Vector2(cell) + Vector2(0.5, 0.5)) * tile

## True when the tile of `layer` at `cell` has the bool custom data `data_name` set.
static func cell_has(layer: TileMapLayer, cell: Vector2i, data_name: String) -> bool:
	if layer == null or layer.tile_set == null or layer.tile_set.get_custom_data_layer_by_name(data_name) < 0:
		return false
	var data := layer.get_cell_tile_data(cell)
	return data != null and RpgUtil.to_bool(data.get_custom_data(data_name))

## True when any of `layers` has a tile with `data_name` at the global point `at`.
static func has_at(layers: Array[TileMapLayer], at: Vector2, data_name: String) -> bool:
	for layer in layers:
		if is_instance_valid(layer) and layer.tile_set != null and cell_has(layer, cell_at(layer, at), data_name):
			return true
	return false

## True when the tile at the global point `at` is a one-way platform in any of `layers`.
static func one_way_at(layers: Array[TileMapLayer], at: Vector2) -> bool:
	for layer in layers:
		if not is_instance_valid(layer) or layer.tile_set == null or layer.tile_set.get_physics_layers_count() <= ONE_WAY_PHYSICS:
			continue
		var data := layer.get_cell_tile_data(cell_at(layer, at))
		if data != null and data.get_collision_polygons_count(ONE_WAY_PHYSICS) > 0:
			return true
	return false

## The cells of `layers` inside the global rectangle `area` whose tile has `data_name`, as
## [layer, cell] pairs.
static func cells_in(layers: Array[TileMapLayer], area: Rect2, data_name: String) -> Array:
	var out: Array = []
	for layer in layers:
		if not is_instance_valid(layer) or layer.tile_set == null:
			continue
		var first := cell_at(layer, area.position)
		var last := cell_at(layer, area.end - Vector2(0.01, 0.01))
		for y in range(first.y, last.y + 1):
			for x in range(first.x, last.x + 1):
				if cell_has(layer, Vector2i(x, y), data_name):
					out.append([layer, Vector2i(x, y)])
	return out
