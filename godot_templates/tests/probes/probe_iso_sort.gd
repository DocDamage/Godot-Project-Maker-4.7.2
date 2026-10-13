extends SceneTree
# Probe (T17.14): what a renderer draws in front of what on an isometric map.
#
# A house that stands on 3 x 2 cells is built by the object recipe (so it is cut in two halves
# that sort apart: object_scenes_recipe.gd, RpgIso.sort_keys) and put among "actors" under a
# Y-sorted node, as a map has them: an actor on every cell of the ring around the house. The
# house is one flat colour and every actor another, so the pixel at an actor's chest says who
# was drawn last there. An actor north or west of the house must be hidden by it where they
# overlap, an actor south or east of it must cover it. A wall tile of the tile set (the
# fixture's block that rises) is painted on a Y-sorted layer beside them and checked the same
# way, and the picture is saved to the path given after `--` (default
# `user://probe_iso_sort.png`) for somebody to look at.
#
# Run in a copy of godot_templates that was imported, with a renderer (not --headless):
#   godot --path <copy> --script res://tests/probes/probe_iso_sort.gd -- <picture.png>

const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const ObjectRecipe := preload("res://builder/recipes/object_scenes_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const HOUSE_PICTURE := "user://probe_iso_house.tres"
const HOUSE_SCENE := "user://probe_iso_house.tscn"
const FOOT := Vector2i(60, 34)
const SIZE := Vector2i(11, 10)
const HOUSE_AT := Vector2i(4, 4)  # the cell of its top-left corner
const HOUSE_CELLS := Vector2i(3, 2)
const HOUSE_HIGH := 60  # px its walls rise
const MAP_AT := Vector2(560, 20)
const SCALE := 2.0
const BACK := Color8(28, 30, 40)
const HOUSE_COLOUR := Color8(200, 60, 60)
const ACTOR_COLOUR := Color8(60, 90, 220)
const WALL := "iso_tiles.png.isotile_019_0"
const WALL_AT := Vector2i(8, 2)
const ACTOR_HIGH := 30

var _frames := 0
var _failed := false
var _map: Node2D
var _actors: Array[Sprite2D] = []
var _cells: Array[Vector2i] = []
var _wall_actors: Array[Sprite2D] = []
var _house_image: Image
var _house_at := Vector2.ZERO  # where the top-left corner of its picture lies on the map

func _check(what: String, ok: bool) -> void:
	print("PROBE %s: %s" % ["ok" if ok else "FAILED", what])
	if not ok:
		_failed = true

## The picture of a block that stands on HOUSE_CELLS and rises HOUSE_HIGH px, in one colour, and
## where in it the middle of its cell nearest the camera is.
func _house_picture() -> Dictionary:
	var half := Vector2(FOOT) / 2.0
	var width := int((HOUSE_CELLS.x + HOUSE_CELLS.y) * half.x)
	var height := int((HOUSE_CELLS.x + HOUSE_CELLS.y) * half.y) + HOUSE_HIGH
	var image := Image.create_empty(width, height, false, Image.FORMAT_RGBA8)
	# the outline on the ground: left corner, top corner, right corner, bottom corner
	var left := Vector2(0, HOUSE_HIGH + HOUSE_CELLS.y * half.y)
	var top := Vector2(HOUSE_CELLS.y * half.x, HOUSE_HIGH)
	var right := Vector2(width, HOUSE_HIGH + HOUSE_CELLS.x * half.y)
	var bottom := Vector2(HOUSE_CELLS.x * half.x, height)
	var ground := PackedVector2Array([left, top, right, bottom])
	var up := Vector2(0, -HOUSE_HIGH)
	var roof := PackedVector2Array([left + up, top + up, right + up, bottom + up])
	var walls := PackedVector2Array([left + up, left, bottom, right, right + up, bottom + up])
	for y in height:
		for x in width:
			var at := Vector2(x + 0.5, y + 0.5)
			if Geometry2D.is_point_in_polygon(at, ground) or Geometry2D.is_point_in_polygon(at, roof) or Geometry2D.is_point_in_polygon(at, walls):
				image.set_pixel(x, y, HOUSE_COLOUR)
	ResourceSaver.save(ImageTexture.create_from_image(image), HOUSE_PICTURE)
	_house_image = image
	# the middle of the nearest cell: half a diamond above the bottom corner
	return {"size": [width, height], "origin": [int(bottom.x), height - int(half.y)]}

func _actor(parent: Node, at: Vector2) -> Sprite2D:
	# lower than a diamond is high, so that the actor of the next cell down does not cover it
	var image := Image.create_empty(12, ACTOR_HIGH, false, Image.FORMAT_RGBA8)
	image.fill(ACTOR_COLOUR)
	var sprite := Sprite2D.new()
	sprite.texture = ImageTexture.create_from_image(image)
	sprite.centered = false
	sprite.offset = Vector2(-6, 1 - ACTOR_HIGH)  # its origin is its feet
	sprite.position = at
	parent.add_child(sprite)
	return sprite

func _initialize() -> void:
	DisplayServer.window_set_size(Vector2i(1200, 760))
	RenderingServer.set_default_clear_color(BACK)
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": "isometric", "features": {}}
	ctx.catalog = CatalogReader.new(JsonUtil.to_dict(JsonUtil.read(FIXTURE)), "isometric")
	_check("the tile set is built", TilesetRecipe.new().build(ctx).is_empty())
	var geo := MapGeo.new(ctx)
	var tile_set := geo.load_tile_set()
	_map = Node2D.new()
	_map.position = MAP_AT
	_map.scale = Vector2(SCALE, SCALE)
	_map.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	get_root().add_child(_map)
	var nodes := MapUtil.build_layers(_map, MapUtil.DEFAULT_LAYERS, tile_set)
	var ground: TileMapLayer = nodes["Ground"]
	MapUtil.fill(ground, Rect2i(Vector2i.ZERO, SIZE), geo.find_tile("GROUND"))
	var props: TileMapLayer = nodes["Props"]
	MapUtil.put(props, WALL_AT, geo.tile_of_asset(WALL))
	var entities: Node2D = nodes["Entities"]
	# the house, by the recipe
	var picture := _house_picture()
	var entry := {
		"id": "probe.house", "name": "house", "role": "BUILDING", "tags": [],
		"texture_path": HOUSE_PICTURE, "region": [0, 0, picture["size"][0], picture["size"][1]],
		"origin": picture["origin"], "footprint": [], "collision": {"profile": "NONE"}, "door": [],
		"sha256": "", "open_region": [], "iso": [FOOT.x, FOOT.y], "stands_on": [HOUSE_CELLS.x, HOUSE_CELLS.y],
	}
	var err: int = ObjectRecipe.new()._build_scene(entry, HOUSE_SCENE, geo.tile_px)
	_check("the object recipe builds the house (%d)" % err, err == OK)
	var house := (ResourceLoader.load(HOUSE_SCENE, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate() as Node2D
	house.position = geo.building_position(entry, HOUSE_AT)
	entities.add_child(house)
	_house_at = house.position - Vector2(float(picture["origin"][0]), float(picture["origin"][1]))
	_check("it is cut in two halves that the map sorts", house.y_sort_enabled and house.get_node_or_null("SpriteRight") != null)
	# an actor on every cell of the ring around it
	for y in range(HOUSE_AT.y - 1, HOUSE_AT.y + HOUSE_CELLS.y + 1):
		for x in range(HOUSE_AT.x - 1, HOUSE_AT.x + HOUSE_CELLS.x + 1):
			var cell := Vector2i(x, y)
			if Rect2i(HOUSE_AT, HOUSE_CELLS).has_point(cell):
				continue
			_cells.append(cell)
			_actors.append(_actor(entities, geo.center(cell)))
	# and one just behind and one just in front of the wall tile, whose block rises 12 px: 20 px
	# above and below the middle of its cell, which is the line a tile of a Y-sorted layer sorts by
	_wall_actors.append(_actor(entities, geo.center(WALL_AT) + Vector2(0, -20)))
	_wall_actors.append(_actor(entities, geo.center(WALL_AT) + Vector2(0, 20)))

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
	var cells := Rect2i(HOUSE_AT, HOUSE_CELLS)
	var behind := 0
	var before := 0
	for i in _actors.size():
		var cell := _cells[i]
		var feet := _actors[i].position
		var truth := RpgIso.in_front(feet, cells, FOOT)
		# from its feet up to its head, the pixels of the actor that the house's picture covers:
		# who was drawn last there?
		var own := 0
		var hidden := 0
		for h in range(2, ACTOR_HIGH - 2, 2):
			for dx: int in [-4, 0, 4]:
				var at := feet + Vector2(dx, -h)
				var in_picture := Vector2i((at - _house_at).floor())
				if not Rect2i(Vector2i.ZERO, _house_image.get_size()).grow(-2).has_point(in_picture):
					continue
				var covered := true
				for by: Vector2i in [Vector2i(0, 0), Vector2i(1, 1), Vector2i(-1, -1), Vector2i(1, -1), Vector2i(-1, 1)]:
					if _house_image.get_pixelv(in_picture + by).a < 0.5:
						covered = false  # at the edge of the picture a pixel may be either's
				if not covered:
					continue
				var seen := _pixel(img, at)
				if _same(seen, ACTOR_COLOUR):
					own += 1
				elif _same(seen, HOUSE_COLOUR):
					hidden += 1
		if truth > 0:
			if own + hidden > 0:
				before += 1
			_check("the actor on %s, in front of the house, covers it (%d px of it, %d hidden)" % [cell, own, hidden], hidden == 0)
		elif truth < 0:
			if own + hidden > 0:
				behind += 1
			_check("the actor on %s, behind the house, is covered by it (%d px hidden, %d show)" % [cell, hidden, own], own == 0)
	_check("actors that overlap it were asked behind it and in front of it (%d and %d)" % [behind, before], behind >= 4 and before >= 2)
	# the wall tile: its block covers the feet of who stands behind it, and not of who is in front
	var back := _wall_actors[0].position
	var front := _wall_actors[1].position
	_check("the actor in front of the wall tile is drawn whole", _same(_pixel(img, front + Vector2(0, -3)), ACTOR_COLOUR) and _same(_pixel(img, front + Vector2(0, -26)), ACTOR_COLOUR))
	_check("the head of the actor behind the wall tile shows over it", _same(_pixel(img, back + Vector2(0, -27)), ACTOR_COLOUR))
	_check("... and its feet do not: the block of the tile is drawn after it", not _same(_pixel(img, back + Vector2(0, -2)), ACTOR_COLOUR))
	var out := "user://probe_iso_sort.png"
	var args := OS.get_cmdline_user_args()
	if not args.is_empty():
		out = args[0]
	img.save_png(out)
	print("PROBE picture %s (%s)" % [out, img.get_size()])
	for path: String in [HOUSE_PICTURE, HOUSE_SCENE]:
		DirAccess.remove_absolute(path)
	quit(1 if _failed else 0)
	return true
