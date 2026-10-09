extends RefCounted
## One minimap per map of res://game/maps (T12.64): a pixel per cell, the average colour of the
## cell's tile computed here from the tile set's pictures, saved with ResourceSaver as an
## ImageTexture in res://generated/minimaps/<key>.tres (no second import pass). The input hash
## covers the map files and the tile sets, so a map you painted gets a new minimap on the next
## build (also "Regenerate affected resources" in the editor).

const RECIPE_VERSION := 1

const BuildContext := preload("../lib/build_context.gd")

const MAPS_DIR := "res://game/maps"
const TILESETS_DIR := "res://generated/tilesets"
const SAMPLE_STEP := 4  # a tile's colour is the average of every 4th pixel each way

## Every map scene under res://game/maps, sorted.
static func map_files(folder: String = MAPS_DIR) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(folder)
	if dir == null:
		return found
	for file_name in dir.get_files():
		var clean := file_name.trim_suffix(".remap")
		if clean.ends_with(".tscn") and not found.has(folder.path_join(clean)):
			found.append(folder.path_join(clean))
	for sub in dir.get_directories():
		found.append_array(map_files(folder.path_join(sub)))
	found.sort()
	return found

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for map_path in map_files():
		out.append(RpgMinimapData.path_for(RpgMinimapData.key_for(map_path)))
	return out

func input_hash(ctx: BuildContext) -> String:
	var files := {}
	for map_path in map_files():
		files[map_path] = FileAccess.get_md5(map_path)
	var sets := DirAccess.open(TILESETS_DIR)
	if sets != null:
		for file_name in sets.get_files():
			if file_name.ends_with(".tres"):
				files[TILESETS_DIR.path_join(file_name)] = FileAccess.get_md5(TILESETS_DIR.path_join(file_name))
	return ctx.stable_hash({"v": RECIPE_VERSION, "files": files})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	DirAccess.make_dir_recursive_absolute(RpgMinimapData.DIR)
	for map_path in map_files():
		var out := RpgMinimapData.path_for(RpgMinimapData.key_for(map_path))
		var texture := render(map_path)
		if texture == null:
			continue  # a map without painted cells has no minimap
		var err := ResourceSaver.save(texture, out)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": out, "err": err}, out))
	return issues

## The minimap of one map scene, or null when it has no painted cells.
static func render(map_path: String) -> ImageTexture:
	var packed := ResourceLoader.load(map_path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	if packed == null:
		return null
	var root := packed.instantiate()
	var layers: Array[TileMapLayer] = []
	_collect_layers(root, layers)
	var texture := render_layers(layers)
	root.free()
	return texture

static func _collect_layers(node: Node, out: Array[TileMapLayer]) -> void:
	for child in node.get_children():
		if child is TileMapLayer:
			out.append(child)
		_collect_layers(child, out)

## Draws `layers` (in tree order: a later layer covers an earlier one) one pixel per cell.
static func render_layers(layers: Array[TileMapLayer]) -> ImageTexture:
	var used := Rect2i()
	var first := true
	var tile := Vector2i(16, 16)
	for layer in layers:
		if layer.tile_set == null:
			continue
		var rect := layer.get_used_rect()
		if rect.size == Vector2i.ZERO:
			continue
		used = rect if first else used.merge(rect)
		if first:
			tile = layer.tile_set.tile_size
		first = false
	if first:
		return null
	var image := Image.create(used.size.x, used.size.y, false, Image.FORMAT_RGBA8)
	image.fill(Color(0, 0, 0, 0))
	var colours := {}
	var pictures := {}
	for layer in layers:
		if layer.tile_set == null:
			continue
		for cell in layer.get_used_cells():
			var colour := tile_colour(layer.tile_set, layer.get_cell_source_id(cell), layer.get_cell_atlas_coords(cell), colours, pictures)
			if colour.a > 0.05:
				image.set_pixelv(cell - used.position, Color(colour.r, colour.g, colour.b, 1.0))
	var texture := ImageTexture.create_from_image(image)
	texture.set_meta("origin_cell", used.position)
	texture.set_meta("tile_size", tile)
	return texture

## The average colour of one tile (its transparent pixels left out), cached by source and atlas.
static func tile_colour(tile_set: TileSet, source_id: int, atlas: Vector2i, colours: Dictionary, pictures: Dictionary) -> Color:
	var key := "%d:%d:%d:%d" % [tile_set.get_instance_id(), source_id, atlas.x, atlas.y]
	if colours.has(key):
		var known: Color = colours[key]
		return known
	var colour := Color(0.5, 0.5, 0.5, 1.0)
	var source := tile_set.get_source(source_id) as TileSetAtlasSource if tile_set.has_source(source_id) else null
	if source != null and source.texture != null:
		var picture_key := "%d:%d" % [tile_set.get_instance_id(), source_id]
		if not pictures.has(picture_key):
			var image := source.texture.get_image()
			if image != null and image.is_compressed():
				image.decompress()
			pictures[picture_key] = image
		var picture: Image = pictures[picture_key]
		if picture != null:
			colour = average(picture, source.get_tile_texture_region(atlas))
	colours[key] = colour
	return colour

## Alpha-weighted average of a region (every SAMPLE_STEP-th pixel); transparent when it is empty.
static func average(image: Image, region: Rect2i) -> Color:
	var r := 0.0
	var g := 0.0
	var b := 0.0
	var weight := 0.0
	var area := region.intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	for y in range(area.position.y, area.end.y, SAMPLE_STEP):
		for x in range(area.position.x, area.end.x, SAMPLE_STEP):
			var c := image.get_pixel(x, y)
			r += c.r * c.a
			g += c.g * c.a
			b += c.b * c.a
			weight += c.a
	if weight <= 0.0:
		return Color(0, 0, 0, 0)
	return Color(r / weight, g / weight, b / weight, 1.0)
