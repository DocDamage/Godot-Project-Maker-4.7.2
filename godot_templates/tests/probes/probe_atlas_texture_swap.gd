extends SceneTree
# Probe (T17.11): the texture of a TileSetAtlasSource that a TileMapLayer already shows is
# replaced at run time by another of the same size. The painted cell keeps its source, its
# atlas coords and its custom data, and the layer is drawn with the new texture without the
# map being rebuilt. The same for the `atlas` of an AtlasTexture a Sprite2D shows.
# Needs a renderer (run without --headless): it reads the pixels of the viewport.

var _frames: int = 0
var _layer: TileMapLayer
var _sprite: Sprite2D
var _source: TileSetAtlasSource
var _red: ImageTexture
var _blue: ImageTexture
var _swapped := false

func _texture(color: Color) -> ImageTexture:
	var img := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	img.fill(color)
	return ImageTexture.create_from_image(img)

func _initialize() -> void:
	_red = _texture(Color(1, 0, 0, 1))
	_blue = _texture(Color(0, 0, 1, 1))
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(0, "tillable")
	ts.set_custom_data_layer_type(0, TYPE_BOOL)
	_source = TileSetAtlasSource.new()
	ts.add_source(_source, 0)
	_source.texture = _red
	_source.texture_region_size = Vector2i(16, 16)
	_source.create_tile(Vector2i(0, 0))
	_source.get_tile_data(Vector2i(0, 0), 0).set_custom_data("tillable", true)
	_layer = TileMapLayer.new()
	_layer.tile_set = ts
	_layer.set_cell(Vector2i(1, 1), 0, Vector2i(0, 0), 0)
	root.add_child(_layer)
	var part := AtlasTexture.new()
	part.atlas = _red
	part.region = Rect2(0, 0, 16, 16)
	_sprite = Sprite2D.new()
	_sprite.texture = part
	_sprite.centered = false
	_sprite.position = Vector2(64, 16)
	root.add_child(_sprite)

func _pixel(at: Vector2i) -> Color:
	return root.get_texture().get_image().get_pixelv(at)

func _process(_delta: float) -> bool:
	_frames += 1
	if _frames < 10:
		return false
	if not _swapped:
		print("PROBE atlas_texture_swap: before tile=", _pixel(Vector2i(24, 24)), " sprite=", _pixel(Vector2i(72, 24)))
		_source.texture = _blue
		(_sprite.texture as AtlasTexture).atlas = _blue
		_swapped = true
		_frames = 0
		return false
	var data := _source.get_tile_data(Vector2i(0, 0), 0)
	print("PROBE atlas_texture_swap: after tile=", _pixel(Vector2i(24, 24)), " sprite=", _pixel(Vector2i(72, 24)),
		" source=", _layer.get_cell_source_id(Vector2i(1, 1)), " coords=", _layer.get_cell_atlas_coords(Vector2i(1, 1)),
		" has_tile=", _source.has_tile(Vector2i(0, 0)), " tillable=", data.get_custom_data("tillable"))
	quit(0)
	return true
