extends SceneTree
# Probe (T17.31): how Godot 4.7 paints with terrains.
#
# * `TileMapLayer.set_cells_terrain_connect(cells, set, terrain, ignore_empty_terrains)` on a
#   terrain of one terrain whose peering bits are -1 where it ends (a block over transparency,
#   or over another ground that has no terrain), with `ignore_empty_terrains` false and true:
#   over plain tiles without a terrain and over empty cells, are the edges right and are the
#   plain cells round it changed?
# * The same over a ground that is a terrain 0 of the same set (two terrains).
# * Several tiles with one peering (the middle and two variants, `TileData.probability` 1 and
#   0.5): which does Godot choose, twice in a run and after `seed()`?
# * One more cell painted beside an area, and a cell painted with the terrain -1.
# * `set_cells_terrain_path` on a set of `TERRAIN_MODE_MATCH_SIDES`: does it join only the cells
#   before and after, and a closed loop given with its first cell again at the end?
# * The isometric shape (`TILE_LAYOUT_DIAMOND_DOWN`): which `CELL_NEIGHBOR_*` are valid peering
#   bits in each mode, and which cell `get_neighbor_cell` gives for each.
#
# Run: godot --headless --path godot_templates --script res://tests/probes/probe_terrain_paint.gd

const BITS := [
	[1, TileSet.CELL_NEIGHBOR_TOP_SIDE], [2, TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER],
	[4, TileSet.CELL_NEIGHBOR_RIGHT_SIDE], [8, TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER],
	[16, TileSet.CELL_NEIGHBOR_BOTTOM_SIDE], [32, TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER],
	[64, TileSet.CELL_NEIGHBOR_LEFT_SIDE], [128, TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER],
]
const MASKS := {
	Vector2i(0, 0): 28, Vector2i(1, 0): 124, Vector2i(2, 0): 112,
	Vector2i(0, 1): 31, Vector2i(1, 1): 255, Vector2i(2, 1): 241,
	Vector2i(0, 2): 7, Vector2i(1, 2): 199, Vector2i(2, 2): 193,
	Vector2i(3, 0): 253, Vector2i(4, 0): 247, Vector2i(3, 1): 223, Vector2i(4, 1): 127,
	Vector2i(5, 0): 255, Vector2i(6, 0): 255,
}
const GRASS := Vector2i(7, 3)

func _tileset(outside: int) -> TileSet:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_terrain_set()
	ts.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
	ts.add_terrain(0)
	if outside >= 0:
		ts.add_terrain(0)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(128, 64, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(16, 16)
	ts.add_source(src, 0)
	var dirt := 1 if outside >= 0 else 0
	for coords: Vector2i in MASKS:
		src.create_tile(coords)
		var td := src.get_tile_data(coords, 0)
		td.terrain_set = 0
		td.terrain = dirt
		for pair: Array in BITS:
			var bit: TileSet.CellNeighbor = pair[1]
			td.set_terrain_peering_bit(bit, dirt if (JsonGuard.mask(MASKS[coords]) & int(pair[0])) != 0 else outside)
		if coords == Vector2i(6, 0):
			td.probability = 0.5
	src.create_tile(GRASS)
	if outside >= 0:
		var gd := src.get_tile_data(GRASS, 0)
		gd.terrain_set = 0
		gd.terrain = 0
		for pair: Array in BITS:
			var bit: TileSet.CellNeighbor = pair[1]
			gd.set_terrain_peering_bit(bit, 0)
	return ts

class JsonGuard:
	static func mask(v: Variant) -> int:
		return int(v)

func _grid(layer: TileMapLayer, size: int) -> String:
	var lines: PackedStringArray = []
	for y in size:
		var row := ""
		for x in size:
			var c := layer.get_cell_atlas_coords(Vector2i(x, y))
			row += " .." if c == Vector2i(-1, -1) else " %d%d" % [c.x, c.y]
		lines.append(row)
	return "\n".join(lines)

func _rect(at: Vector2i, size: Vector2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for y in size.y:
		for x in size.x:
			out.append(at + Vector2i(x, y))
	return out

func _case(title: String, ts: TileSet, grass: bool, ignore_empty: bool, terrain: int) -> void:
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	root.add_child(layer)
	if grass:
		for cell in _rect(Vector2i.ZERO, Vector2i(9, 9)):
			layer.set_cell(cell, 0, GRASS)
	layer.set_cells_terrain_connect(_rect(Vector2i(2, 2), Vector2i(4, 3)), 0, terrain, ignore_empty)
	print("== ", title, " ignore_empty=", ignore_empty)
	print(_grid(layer, 9))
	layer.queue_free()

func _variants(ts: TileSet) -> String:
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	root.add_child(layer)
	layer.set_cells_terrain_connect(_rect(Vector2i.ZERO, Vector2i(12, 12)), 0, 0, false)
	var s := ""
	for y in range(1, 11):
		for x in range(1, 11):
			s += str(layer.get_cell_atlas_coords(Vector2i(x, y)).x)
	layer.queue_free()
	return s

func _initialize() -> void:
	var over_nothing := _tileset(-1)
	for ignore: bool in [false, true]:
		_case("plain grass without terrain, dirt over nothing", over_nothing, true, ignore, 0)
		_case("empty layer, dirt over nothing", over_nothing, false, ignore, 0)
		_case("grass terrain 0 painted cell by cell, dirt terrain 1", _tileset(0), true, ignore, 1)
	print("variants (1 = the middle, 5 = a middle of probability 1, 6 = of 0.5):")
	print(_variants(over_nothing))
	print(_variants(over_nothing))
	seed(12345)
	var a := _variants(over_nothing)
	seed(12345)
	print("after seed() twice the same: ", a == _variants(over_nothing))
	var layer := TileMapLayer.new()
	layer.tile_set = over_nothing
	root.add_child(layer)
	for cell in _rect(Vector2i.ZERO, Vector2i(9, 9)):
		layer.set_cell(cell, 0, GRASS)
	layer.set_cells_terrain_connect(_rect(Vector2i(2, 2), Vector2i(3, 3)), 0, 0, false)
	layer.set_cells_terrain_connect([Vector2i(5, 3)] as Array[Vector2i], 0, 0, false)
	print("== one cell more at (5,3)")
	print(_grid(layer, 9))
	layer.set_cells_terrain_connect([Vector2i(5, 3)] as Array[Vector2i], 0, -1, false)
	print("== (5,3) painted with the terrain -1")
	print(_grid(layer, 9))
	_paths()
	_diamonds()
	quit(0)

func _paths() -> void:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_terrain_set()
	ts.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_SIDES)
	ts.add_terrain(0)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(64, 64, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(16, 16)
	ts.add_source(src, 0)
	var side_bits: Array[TileSet.CellNeighbor] = [TileSet.CELL_NEIGHBOR_TOP_SIDE, TileSet.CELL_NEIGHBOR_RIGHT_SIDE, TileSet.CELL_NEIGHBOR_BOTTOM_SIDE, TileSet.CELL_NEIGHBOR_LEFT_SIDE]
	for sides in 16:
		var coords := Vector2i(sides % 4, sides / 4)
		src.create_tile(coords)
		var td := src.get_tile_data(coords, 0)
		td.terrain_set = 0
		td.terrain = 0
		for i in 4:
			if sides & (1 << i):
				td.set_terrain_peering_bit(side_bits[i], 0)
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	root.add_child(layer)
	layer.set_cells_terrain_path([Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 1), Vector2i(3, 2), Vector2i(3, 3), Vector2i(2, 3)] as Array[Vector2i], 0, 0, false)
	layer.set_cells_terrain_path([Vector2i(1, 2), Vector2i(2, 2)] as Array[Vector2i], 0, 0, false)
	print("== two paths side by side (sides: n 1, e 2, s 4, w 8)")
	for y in 5:
		var row := ""
		for x in 5:
			var c := layer.get_cell_atlas_coords(Vector2i(x, y))
			row += " ." if c == Vector2i(-1, -1) else " %d" % (c.x + c.y * 4)
		print(row)
	var loop := TileMapLayer.new()
	loop.tile_set = ts
	root.add_child(loop)
	loop.set_cells_terrain_path([Vector2i(1, 1), Vector2i(2, 1), Vector2i(2, 2), Vector2i(1, 2), Vector2i(1, 1)] as Array[Vector2i], 0, 0, false)
	print("== a closed loop: ", [loop.get_cell_atlas_coords(Vector2i(1, 1)), loop.get_cell_atlas_coords(Vector2i(2, 2))])

func _diamonds() -> void:
	var iso := TileSet.new()
	iso.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	iso.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	iso.tile_size = Vector2i(64, 32)
	iso.add_terrain_set()
	iso.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_SIDES)
	iso.add_terrain(0)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(Image.create(64, 32, false, Image.FORMAT_RGBA8))
	src.texture_region_size = Vector2i(64, 32)
	iso.add_source(src, 0)
	src.create_tile(Vector2i.ZERO)
	var td := src.get_tile_data(Vector2i.ZERO, 0)
	td.terrain_set = 0
	var layer := TileMapLayer.new()
	layer.tile_set = iso
	root.add_child(layer)
	for n in ["RIGHT_SIDE", "BOTTOM_RIGHT_SIDE", "BOTTOM_SIDE", "BOTTOM_LEFT_SIDE", "LEFT_SIDE", "TOP_LEFT_SIDE", "TOP_SIDE", "TOP_RIGHT_SIDE", "RIGHT_CORNER", "BOTTOM_CORNER", "LEFT_CORNER", "TOP_CORNER"]:
		var bit: int = ClassDB.class_get_integer_constant("TileSet", "CELL_NEIGHBOR_" + n)
		var square := n in ["RIGHT_SIDE", "BOTTOM_SIDE", "LEFT_SIDE", "TOP_SIDE"]  # no neighbour of a diamond
		var neighbour: Variant = "-" if square else layer.get_neighbor_cell(Vector2i(2, 2), bit as TileSet.CellNeighbor)
		print("diamond, sides: %s valid %s, neighbour of (2,2) %s" % [n, td.is_valid_terrain_peering_bit(bit as TileSet.CellNeighbor), neighbour])
	iso.set_terrain_set_mode(0, TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
	for n in ["RIGHT_CORNER", "BOTTOM_CORNER", "LEFT_CORNER", "TOP_CORNER"]:
		var bit: int = ClassDB.class_get_integer_constant("TileSet", "CELL_NEIGHBOR_" + n)
		print("diamond, corners and sides: %s valid %s" % [n, td.is_valid_terrain_peering_bit(bit as TileSet.CellNeighbor)])
	print("TileData.probability by default: ", TileData.new().probability)
