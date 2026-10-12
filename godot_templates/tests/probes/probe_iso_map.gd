extends SceneTree
# Probe (T17.13): a small map painted with the isometric tile set the recipe builds from the
# fixture of the synthetic pack `iso_tiles` (tests/fixtures/iso_tiles), drawn by a renderer.
#
# The ground is 9 x 7 cells of flat tiles in their four turns, with a pond of the water tile, a
# row of raised blocks (the walls), a tree and a house standing on cells (`IsoTileset.stand`).
# It checks by the pixels of the viewport that neighbouring flat tiles leave no seam, that a
# block's face is its rise above its cell and that the tree's trunk is on the middle of its
# cell, and saves the picture to the path given after `--` (default
# `user://probe_iso_map.png`) for somebody to look at.
#
# Run in a copy of godot_templates that was imported, with a renderer (not --headless):
#   godot --path <copy> --script res://tests/probes/probe_iso_map.gd -- <picture.png>

const Recipe := preload("res://builder/recipes/tileset_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const IsoTileset := preload("res://builder/lib/iso_tileset.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const SIZE := Vector2i(9, 7)
const MAP_AT := Vector2(440, 60)
const SCALE := 2.0
const BACK := Color8(28, 30, 40)
const WALL := "iso_tiles.png.isotile_019_0"
const WATER := "iso_tiles.png.isotile_002_0"
const POND: Array[Vector2i] = [Vector2i(5, 4), Vector2i(6, 4), Vector2i(5, 5), Vector2i(6, 5)]
const WALLS: Array[Vector2i] = [Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 1), Vector2i(1, 2)]
const TREE_AT := Vector2i(4, 3)
const HOUSE_AT := Vector2i(7, 1)

var _frames := 0
var _layer: TileMapLayer
var _iso: IsoTileset
var _failed := false

func _check(what: String, ok: bool) -> void:
	print("PROBE %s: %s" % ["ok" if ok else "FAILED", what])
	if not ok:
		_failed = true

func _ground(cell: Vector2i) -> String:
	# three of the pack's flat tiles in patches
	var n := 1 + posmod(cell.x / 3 + cell.y / 2 * 2, 3) * 3  # isoTile_001, _004, _007
	return "iso_tiles.png.isotile_%03d_0" % n

func _initialize() -> void:
	DisplayServer.window_set_size(Vector2i(1100, 660))
	RenderingServer.set_default_clear_color(BACK)
	var cat := JsonUtil.to_dict(JsonUtil.read(FIXTURE))
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": "isometric", "features": {}}
	ctx.catalog = CatalogReader.new(cat, "isometric")
	var issues: Array = Recipe.new().build(ctx)
	_check("the recipe builds the tile set without an issue (%s)" % [issues], issues.is_empty())
	_iso = IsoTileset.new(ctx.catalog)
	var ts := ResourceLoader.load(_iso.tileset_path(), "TileSet", ResourceLoader.CACHE_MODE_IGNORE) as TileSet
	_layer = TileMapLayer.new()
	_layer.tile_set = ts
	_layer.position = MAP_AT
	_layer.scale = Vector2(SCALE, SCALE)
	_layer.y_sort_enabled = true
	_layer.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	get_root().add_child(_layer)
	for y in SIZE.y:
		for x in SIZE.x:
			var cell := Vector2i(x, y)
			if POND.has(cell):
				_iso.paint(_layer, cell, WATER, 0)
			elif WALLS.has(cell):
				_iso.paint(_layer, cell, WALL, (x + y) % 4)
			else:
				_iso.paint(_layer, cell, _ground(cell), (x * 3 + y) % 4)
	for entry: Array in [["iso_tiles.png.tree_01_0", TREE_AT], ["iso_tiles.png.house_01_0", HOUSE_AT]]:
		var asset_id: String = entry[0]
		var cell: Vector2i = entry[1]
		var asset := ctx.catalog.asset(asset_id)
		var sprite := Sprite2D.new()
		sprite.texture = load("res://" + JsonUtil.to_str(asset["path"])) as Texture2D
		sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		IsoTileset.stand(sprite, CatalogReader.effective(asset), _layer.map_to_local(cell))
		_layer.add_child(sprite)
	print("PROBE footprint %s, %d tiles, sources %d" % [_iso.footprint(), _iso.tile_ids().size(), ts.get_source_count()])

func _pixel(img: Image, local: Vector2) -> Color:
	var at := Vector2i((MAP_AT + local * SCALE).round())
	return img.get_pixel(at.x, at.y)

func _same(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) < 0.02 and absf(a.g - b.g) < 0.02 and absf(a.b - b.b) < 0.02

func _process(_delta: float) -> bool:
	_frames += 1
	if _frames < 12:
		return false
	var img := get_root().get_texture().get_image()
	var foot := Vector2(_iso.footprint())
	# no seam: on the way from a point of a flat cell to the same point of its neighbour of the
	# same ground, a little off the middle (the middle has the tile's turn mark), every pixel
	# has one colour
	var off := Vector2(0, -3)
	var seams := 0
	var walked := 0
	for y in SIZE.y:
		for x in SIZE.x:
			var cell := Vector2i(x, y)
			for n: Vector2i in [Vector2i(1, 0), Vector2i(0, 1)]:
				var next := cell + n
				if next.x >= SIZE.x or next.y >= SIZE.y or _ground(cell) != _ground(next):
					continue
				var busy := false
				for c: Vector2i in [cell, next, cell + Vector2i(1, 1), cell + Vector2i(-1, 0), cell + Vector2i(0, -1), next + Vector2i(-1, 0), next + Vector2i(0, -1), cell + Vector2i(-1, -1), next + Vector2i(-1, -1)]:
					if POND.has(c) or WALLS.has(c) or c == TREE_AT or c == HOUSE_AT:
						busy = true
				if busy:
					continue
				var a := _layer.map_to_local(cell) + off
				var b := _layer.map_to_local(next) + off
				var face := _pixel(img, a)
				walked += 1
				for i in 81:
					if not _same(_pixel(img, a.lerp(b, i / 80.0)), face):
						seams += 1
	_check("no seam on %d ways between neighbouring flat tiles (%d pixels of another colour)" % [walked, seams], walked > 20 and seams == 0)
	# the background shows nowhere inside the map: the middle of every cell is painted
	var holes := 0
	for y in SIZE.y:
		for x in SIZE.x:
			if _same(_pixel(img, _layer.map_to_local(Vector2i(x, y)) + off), BACK):
				holes += 1
	_check("every cell is painted (%d holes)" % holes, holes == 0)
	# a block rises 12 px: its face is over the middle of its cell, 12 px up, and the flat
	# tile's face colour is not there
	var block := _layer.map_to_local(WALLS[2])  # the end of the row: nothing stands in front of it
	var face_colour := _pixel(img, block + Vector2(8, -12))
	_check("the face of a block is one colour from 12 px above the middle of its cell up to its top corner", _same(_pixel(img, block + Vector2(8, -18)), face_colour) and _same(_pixel(img, block + Vector2(-8, -12)), face_colour))
	_check("under the face is the block's side, down to the ground", not _same(_pixel(img, block + Vector2(-10, 6)), face_colour))
	# the tree: its trunk on the middle of its cell, its crown above
	var foot_at := _layer.map_to_local(TREE_AT)
	_check("the trunk of the tree stands on the middle of its cell", _same(_pixel(img, foot_at + Vector2(0, -3)), Color8(110, 74, 46)))
	_check("the crown is above it", _same(_pixel(img, foot_at + Vector2(0, -26)), Color8(52, 128, 66)))
	_check("the ground beside the trunk is the cell's", _same(_pixel(img, foot_at + Vector2(foot.x * 0.3, 0)), _pixel(img, foot_at + Vector2(-foot.x * 0.3, 0))))
	var out := "user://probe_iso_map.png"
	var args := OS.get_cmdline_user_args()
	if not args.is_empty():
		out = args[0]
	img.save_png(out)
	print("PROBE picture %s (%s)" % [out, img.get_size()])
	quit(1 if _failed else 0)
	return true
