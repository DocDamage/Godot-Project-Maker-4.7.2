extends SceneTree
# Probe (T17.13): an isometric TileSet of single pictures in one atlas.
#
# * `TileSet.tile_shape = TILE_SHAPE_ISOMETRIC` with `tile_layout = TILE_LAYOUT_DIAMOND_DOWN`
#   and a tile size that is not 2:1 (60 x 34): where `TileMapLayer.map_to_local` puts the cells
#   of a grid counted x east, y south, and what `local_to_map` answers for points of a diamond;
#   whether `tile_offset_axis` changes anything for the diamond layouts.
# * `TileData.texture_origin` for a picture taller than its cell: three tiles in atlas cells of
#   60 x 120 (a flat tile, a block that rises 12 px, a tile three times as high as its diamond),
#   each with `texture_origin = (middle of its diamond in the cell) - (cell size / 2)`.
# * An alternative tile has no texture region of its own.
# * A `Sprite2D` standing on a cell (an object: a tree), placed by the same origin.
#
# Needs a renderer (run without --headless): it reads the pixels of the viewport and saves the
# picture to the path given after `--` (default `user://probe_iso_tileset.png`).

const FOOT := Vector2i(60, 34)
const CELL := Vector2i(60, 120)
const SIDE := 8
const GRASS := Color8(104, 170, 84)
const STONE := Color8(150, 150, 170)
const TOWER := Color8(200, 120, 60)
const LEFT := Color8(122, 86, 58)
const RIGHT := Color8(150, 108, 72)
const BACK := Color8(30, 30, 40)
const MAP_AT := Vector2(240, 60)

var _frames := 0
var _layer: TileMapLayer
var _origins := {}
var _failed := false

func _check(what: String, ok: bool) -> void:
	print("PROBE %s: %s" % ["ok" if ok else "FAILED", what])
	if not ok:
		_failed = true

## A diamond `FOOT` with `side` rows of block under it, its top corner `rise` rows above the
## diamond of the ground it stands on, drawn into `img` at the cell `column`. Returns the middle
## of the ground's diamond in the cell: what must lie on the middle of the map's cell.
func _draw_tile(img: Image, column: int, face: Color, rise: int) -> Vector2i:
	var x0 := column * CELL.x
	var ground_top := CELL.y - SIDE - FOOT.y  # the top corner of the diamond the tile stands on
	var top := ground_top - rise
	for x in FOOT.x:
		var first := (absi(2 * x + 1 - FOOT.x) * FOOT.y) / (2 * FOOT.x)
		var last := FOOT.y - 1 - first
		for y in range(first, last + 1):
			img.set_pixel(x0 + x, top + y, face)
		for y in range(last + 1, last + 1 + SIDE + rise):
			img.set_pixel(x0 + x, top + y, LEFT if x < FOOT.x / 2 else RIGHT)
	return Vector2i(FOOT.x / 2, ground_top + FOOT.y / 2)

func _initialize() -> void:
	DisplayServer.window_set_size(Vector2i(480, 320))
	RenderingServer.set_default_clear_color(BACK)
	var img := Image.create_empty(CELL.x * 3, CELL.y, false, Image.FORMAT_RGBA8)
	_origins[Vector2i(0, 0)] = _draw_tile(img, 0, GRASS, 0)
	_origins[Vector2i(1, 0)] = _draw_tile(img, 1, STONE, 12)
	_origins[Vector2i(2, 0)] = _draw_tile(img, 2, TOWER, 2 * FOOT.y)  # 3 x 34 = 102 rows high
	var ts := TileSet.new()
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	ts.tile_size = FOOT
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = CELL
	ts.add_source(src, 0)
	for coords: Vector2i in _origins.keys():
		src.create_tile(coords)
		var origin: Vector2i = _origins[coords]
		src.get_tile_data(coords, 0).texture_origin = origin - CELL / 2
	print("PROBE shape=%d layout=%d offset_axis=%d tile_size=%s region=%s" % [ts.tile_shape, ts.tile_layout, ts.tile_offset_axis, ts.tile_size, src.texture_region_size])
	print("PROBE texture_origin flat=%s block=%s tall=%s" % [src.get_tile_data(Vector2i(0, 0), 0).texture_origin, src.get_tile_data(Vector2i(1, 0), 0).texture_origin, src.get_tile_data(Vector2i(2, 0), 0).texture_origin])

	# an alternative tile is the same region of the atlas: it has nothing to say another with
	var alt := src.create_alternative_tile(Vector2i(0, 0))
	var names: Array[String] = []
	for p: Dictionary in src.get_tile_data(Vector2i(0, 0), alt).get_property_list():
		names.append(str(p["name"]))
	_check("an alternative tile has no region of its own (properties: flip_h %s, transpose %s, texture_region %s, atlas_coords %s)" % [names.has("flip_h"), names.has("transpose"), names.has("texture_region"), names.has("atlas_coords")], names.has("flip_h") and not names.has("texture_region") and not names.has("atlas_coords"))
	_check("the region of an alternative is the tile's", src.get_tile_texture_region(Vector2i(0, 0)) == Rect2i(0, 0, CELL.x, CELL.y))

	_layer = TileMapLayer.new()
	_layer.tile_set = ts
	_layer.position = MAP_AT
	# the second argument `nosort` leaves the layer unsorted, to see what that draws
	_layer.y_sort_enabled = not OS.get_cmdline_user_args().has("nosort")
	get_root().add_child(_layer)
	for y in 5:
		for x in 5:
			_layer.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	_layer.set_cell(Vector2i(1, 1), 0, Vector2i(1, 0))  # a block
	_layer.set_cell(Vector2i(3, 1), 0, Vector2i(2, 0))  # a tall tile
	_layer.set_cell(Vector2i(2, 3), -1)  # a hole: the background shows through one diamond

	# where the cells are
	var half := Vector2(FOOT) / 2.0
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1), Vector2i(1, 1), Vector2i(4, 2), Vector2i(-1, 3)]:
		var at := _layer.map_to_local(cell)
		var want := Vector2((cell.x - cell.y) * half.x, (cell.x + cell.y) * half.y) + half
		print("PROBE map_to_local%s = %s" % [cell, at])
		_check("map_to_local%s is ((x - y + 1) * w/2, (x + y + 1) * h/2) = %s" % [cell, want], at.is_equal_approx(want))
		_check("local_to_map of the middle of %s" % cell, _layer.local_to_map(at) == cell)
		# points just inside the four corners of the diamond are the cell's
		for d: Vector2 in [Vector2(half.x - 3, 0), Vector2(-half.x + 3, 0), Vector2(0, half.y - 2), Vector2(0, -half.y + 2)]:
			_check("local_to_map of %s + %s" % [cell, d], _layer.local_to_map(at + d) == cell)
	# a point of the bounding box that is outside the diamond belongs to the neighbour
	var corner := _layer.map_to_local(Vector2i(1, 1)) + Vector2(half.x - 4, half.y - 3)
	print("PROBE local_to_map of the lower right of the box of (1, 1) = %s" % _layer.local_to_map(corner))
	_check("the lower right of the box of (1, 1) is (2, 1)", _layer.local_to_map(corner) == Vector2i(2, 1))
	# the offset axis says nothing for a diamond layout
	var before := _layer.map_to_local(Vector2i(3, 2))
	ts.tile_offset_axis = TileSet.TILE_OFFSET_AXIS_VERTICAL
	var vertical := _layer.map_to_local(Vector2i(3, 2))
	ts.tile_offset_axis = TileSet.TILE_OFFSET_AXIS_HORIZONTAL
	print("PROBE offset axis horizontal %s vertical %s" % [before, vertical])
	_check("the offset axis moves no cell of a diamond layout (the size 60 x 34 is the same for both)", before.is_equal_approx(vertical))

	# an object standing on a cell: a tree, a picture whose foot is the middle of a diamond
	var tree_img := Image.create_empty(40, 70, false, Image.FORMAT_RGBA8)
	tree_img.fill_rect(Rect2i(17, 40, 6, 28), Color8(110, 74, 46))
	for y in 44:
		for x in 40:
			if Vector2(x - 19.5, y - 21.5).length() < 19.0:
				tree_img.set_pixel(x, y, Color8(52, 128, 66))
	var tree := Sprite2D.new()
	tree.texture = ImageTexture.create_from_image(tree_img)
	tree.centered = false
	tree.offset = -Vector2(20, 67)  # the catalog's origin: its foot
	tree.position = _layer.map_to_local(Vector2i(3, 3))
	_layer.add_child(tree)

func _pixel(img: Image, local: Vector2) -> Color:
	var at := Vector2i((MAP_AT + local).round())
	return img.get_pixel(at.x, at.y)

func _is(c: Color, want: Color) -> bool:
	return absf(c.r - want.r) < 0.02 and absf(c.g - want.g) < 0.02 and absf(c.b - want.b) < 0.02

func _process(_delta: float) -> bool:
	_frames += 1
	if _frames < 12:
		return false
	var img := get_root().get_texture().get_image()
	var half := Vector2(FOOT) / 2.0
	# a flat tile lies on its cell: the middle and the points just inside the corners are grass
	var flat := _layer.map_to_local(Vector2i(0, 2))
	_check("the middle of a flat cell is its face", _is(_pixel(img, flat), GRASS))
	for d: Vector2 in [Vector2(half.x - 3, 0), Vector2(-half.x + 3, 0), Vector2(0, half.y - 2), Vector2(0, -half.y + 2)]:
		_check("the corner %s of a flat cell is its face" % d, _is(_pixel(img, flat + d), GRASS))
	# ... and the hole shows the background, but for the sides of the two tiles behind it,
	# which hang 8 px into it from its upper edges
	var hole := _layer.map_to_local(Vector2i(2, 3))
	_check("an empty cell shows the background in its middle", _is(_pixel(img, hole), BACK))
	_check("an empty cell shows the background at its lower corner", _is(_pixel(img, hole + Vector2(0, half.y - 2)), BACK))
	_check("the sides of the tiles behind an empty cell hang into it", _is(_pixel(img, hole + Vector2(-2, -half.y + 4)), LEFT) or _is(_pixel(img, hole + Vector2(-2, -half.y + 4)), RIGHT))
	# no seam: every pixel on the way from the middle of a cell to the middle of each of its
	# neighbours is grass
	var seams := 0
	for cell: Vector2i in [Vector2i(0, 2), Vector2i(0, 3)]:
		for n: Vector2i in [Vector2i(1, 0), Vector2i(0, 1)]:
			var a := _layer.map_to_local(cell)
			var b := _layer.map_to_local(cell + n)
			for i in 61:
				if not _is(_pixel(img, a.lerp(b, i / 60.0)), GRASS):
					seams += 1
	_check("no pixel between the middles of neighbouring flat cells is anything but their face (%d)" % seams, seams == 0)
	# a block: its face is 12 px above the middle of its cell, its side reaches down to the ground
	var block := _layer.map_to_local(Vector2i(1, 1))
	_check("the face of a block is its rise above the middle of its cell", _is(_pixel(img, block + Vector2(0, -12)), STONE))
	_check("the top corner of a block is rise + h/2 above the middle", _is(_pixel(img, block + Vector2(0, -12 - half.y + 2)), STONE) and not _is(_pixel(img, block + Vector2(0, -12 - half.y - 2)), STONE))
	# a tile three times as high as its diamond stands on its cell
	var tall := _layer.map_to_local(Vector2i(3, 1))
	_check("the face of the tall tile is 2 h above the middle of its cell", _is(_pixel(img, tall + Vector2(0, -2 * FOOT.y)), TOWER))
	_check("its top corner is 2.5 h above the middle", _is(_pixel(img, tall + Vector2(0, -2.5 * FOOT.y + 2)), TOWER) and _is(_pixel(img, tall + Vector2(0, -2.5 * FOOT.y - 2)), BACK))
	_check("its side stands on the cell: the pixel just above the cell's lower corner is its side", _is(_pixel(img, tall + Vector2(-3, half.y - 4)), LEFT))
	# the tree stands with its foot on the middle of (3, 3)
	var foot := _layer.map_to_local(Vector2i(3, 3))
	_check("the trunk of the tree is at the middle of its cell", _is(_pixel(img, foot + Vector2(0, -2)), Color8(110, 74, 46)))
	_check("the crown is above it", _is(_pixel(img, foot + Vector2(0, -50)), Color8(52, 128, 66)))
	var out := "user://probe_iso_tileset.png"
	var args := OS.get_cmdline_user_args()
	if not args.is_empty():
		out = args[0]
	img.save_png(out)
	print("PROBE picture %s (%s)" % [out, img.get_size()])
	quit(1 if _failed else 0)
	return true
