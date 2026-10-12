extends RefCounted
## The isometric tile set (T17.13), built only for a tile set definition whose `projection` is
## `isometric`: the catalog has one only when the project's config says `projection: isometric`.
## Every other tile set is built by `tileset_recipe.gd` exactly as before.
##
## **The grid.** Godot's isometric tile shape with the layout `TILE_LAYOUT_DIAMOND_DOWN`: a cell
## (x, y) of the planner's grid, x east and y south, has its middle at
## `((x - y + 1) * w / 2, (x + y + 1) * h / 2)` of the layer, where (w, h) is the footprint (the
## diamond of the pack, whatever its ratio). So east is down and to the right on the screen and
## south down and to the left, and the cell (0, 0) is the top corner of the map. The four sides
## of a diamond are, by the grid: `n` the upper right, `e` the lower right, `s` the lower left,
## `w` the upper left. The offset axis says nothing for a diamond layout and is left alone.
##
## **The tiles** are single pictures of a pack (`usage: iso_tile`) that rpggen packed into atlas
## pictures (`rpggen/core/iso_atlas.py`). The definition's `tiles` says where each is:
## `{asset id: {source, coords: [column, row], at: [x, y]}}`, `at` being where the picture lies in
## its atlas cell. A tile's `texture_origin` is the middle of its diamond (the catalog's
## `origin`, in the picture) measured from the middle of the atlas cell: Godot draws the cell of
## the atlas with its middle on the middle of the map's cell and then moves it back by the
## origin. The catalog says where the diamond is; a tile does not always rest on the bottom of
## its picture.
##
## **Turns.** An alternative tile of Godot is the same region of the atlas flipped or
## transposed: it cannot show another picture. A tile turned four ways is four pictures, so
## every turn is a tile of its own in the atlas, and `tile_for(asset_id, turn)` finds it.
##
## A map recipe makes one of these from the catalog and asks it:
##     var iso := IsoTileset.new(ctx.catalog)
##     iso.paint(layer, Vector2i(3, 2), "pack.grass_0")          # a tile
##     var piece := iso.piece_for("road", ["e", "s"])            # the corner that joins east and south
##     iso.paint(layer, cell, piece["asset_id"], piece["turn"])  # ... turned as it must be
##     IsoTileset.stand(sprite, facets, layer.map_to_local(cell))  # an object on a cell

const JsonUtil := preload("json_util.gd")
const Geometry := preload("geometry.gd")
const Paths := preload("paths.gd")
const CatalogReader := preload("catalog_reader.gd")

const PROJECTION := "isometric"
const TILE_USAGE := "iso_tile"
## The sides of a diamond in the order a quarter turn clockwise moves them on.
const SIDES: Array[String] = ["n", "e", "s", "w"]
const TURN_TAG := "turn:"
const SURFACE_TAG := "surface:"
## The size of the square a collision profile is laid out in before it is put on the diamond.
const PROFILE_SQUARE := 64

## True for the tile set definition of an isometric project.
static func wanted(def: Dictionary) -> bool:
	return JsonUtil.to_str(def.get("projection", "")) == PROJECTION

## True for a project whose config asks for the isometric view.
static func project_wanted(config: Dictionary) -> bool:
	return JsonUtil.to_str(config.get("projection", "")) == PROJECTION

static func _vec(value: Variant, fallback: Vector2i = Vector2i.ZERO) -> Vector2i:
	var pair := JsonUtil.to_array(value)
	if pair.size() != 2:
		return fallback
	return Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1]))

## Gives a new TileSet the shape of the grid: diamonds of `footprint`.
static func shape(ts: TileSet, footprint: Vector2i) -> void:
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	ts.tile_size = footprint

## True when `ts` is laid out as `shape` lays one out (its size apart).
static func has_shape(ts: TileSet) -> bool:
	return ts.tile_shape == TileSet.TILE_SHAPE_ISOMETRIC and ts.tile_layout == TileSet.TILE_LAYOUT_DIAMOND_DOWN

## The middle of the cell `cell` in the layer: what `TileMapLayer.map_to_local` answers.
static func cell_to_local(cell: Vector2i, footprint: Vector2i) -> Vector2:
	return Vector2((cell.x - cell.y + 1) * footprint.x / 2.0, (cell.x + cell.y + 1) * footprint.y / 2.0)

## A point of the unit square of a cell (u east, v south, each 0 to 1) on the diamond, measured
## from the middle of the cell.
static func on_diamond(u: float, v: float, footprint: Vector2i) -> Vector2:
	return Vector2((u - v) * footprint.x / 2.0, (u + v - 1.0) * footprint.y / 2.0)

## The diamond of a cell around its middle: the top, the right, the bottom and the left corner.
static func diamond(footprint: Vector2i) -> PackedVector2Array:
	return PackedVector2Array([on_diamond(0, 0, footprint), on_diamond(1, 0, footprint), on_diamond(1, 1, footprint), on_diamond(0, 1, footprint)])

## The `texture_origin` of a tile: the middle of its diamond (`origin`, in its picture, which
## lies at `at` in an atlas cell of `cell`) from the middle of the atlas cell.
static func texture_origin(origin: Vector2i, at: Vector2i, cell: Vector2i) -> Vector2i:
	return origin + at - cell / 2

## The collision of a tile that names none: a wall blocks its diamond, everything else nothing.
static func default_collision(eff: Dictionary) -> Dictionary:
	var given: Variant = eff.get("collision")
	if given is Dictionary:
		var spec: Dictionary = given
		return spec
	return {"profile": "FULL" if JsonUtil.to_str(eff.get("role", "")) == "WALL" else "NONE"}

## The collision polygons of a tile around the middle of its cell. `FULL` is the diamond; the
## halves and edges that exist for square tiles are laid out in the square of the cell (its top
## the north side) and put on the diamond, so `BOTTOM_HALF` is the half towards the south and
## `LEFT_EDGE` a band along the west side. `CUSTOM` is given in the px of the picture and is
## moved to the tile's `origin`. `ALPHA_POLYGON` is the diamond: the outline of a picture drawn
## at an angle is not what stands on the ground.
static func collision_polygons(collision: Dictionary, footprint: Vector2i, origin: Vector2i) -> Array:
	var profile := JsonUtil.to_str(collision.get("profile", "NONE"))
	var polys: Array = []
	if profile == "NONE" or profile == "ONE_WAY" or profile == "LADDER":
		return polys
	if profile == "CUSTOM":
		var pts := PackedVector2Array()
		for p: Variant in JsonUtil.to_array(collision.get("polygon", [])):
			var pair := JsonUtil.to_array(p)
			if pair.size() == 2:
				pts.append(Vector2(JsonUtil.to_float(pair[0]), JsonUtil.to_float(pair[1])) - Vector2(origin))
		if pts.size() >= 3:
			polys.append(pts)
		return polys
	if profile == "ALPHA_POLYGON":
		profile = "FULL"
	var square := Vector2i(PROFILE_SQUARE, PROFILE_SQUARE)
	var flat := Geometry.profile_polygon(profile, square)
	if flat.size() < 3:
		return polys
	var out := PackedVector2Array()
	for p in flat:
		out.append(on_diamond(p.x / PROFILE_SQUARE, p.y / PROFILE_SQUARE, footprint))
	polys.append(out)
	return polys

static func _tags(eff: Dictionary) -> Array:
	return JsonUtil.to_array(eff.get("tags", []))

## What the maps ask a tile: `{asset_id, footstep, tillable, water}`. The surface is the
## asset's `surface:<name>` tag; `tillable` and `water` are said by the catalog (the tags of
## those names, the role WATER), never guessed from the art.
static func custom_data(asset: Dictionary, eff: Dictionary) -> Dictionary:
	var tags := _tags(eff)
	var surface := ""
	for tag: Variant in tags:
		var text := JsonUtil.to_str(tag)
		if text.begins_with(SURFACE_TAG):
			surface = text.substr(SURFACE_TAG.length())
	return {
		"asset_id": JsonUtil.to_str(asset.get("id", "")),
		"footstep": surface,
		"tillable": tags.has("tillable"),
		"water": tags.has("water") or JsonUtil.to_str(eff.get("role", "")) == "WATER",
	}

## Puts a sprite that shows an object (a tree, a house) on the middle of a cell: its picture's
## `origin` (the middle of the diamond it stands on, from the catalog) lies on `at`.
static func stand(sprite: Sprite2D, eff: Dictionary, at: Vector2) -> void:
	sprite.centered = false
	sprite.offset = -Vector2(_vec(eff.get("origin")))
	sprite.position = at

## The cells an object stands on when it is put on `cell`: `stands_on` [columns, rows] of the
## catalog, `cell` being the one of them nearest the camera (the highest x and y), which is the
## cell an actor in front of the object is compared with.
static func cells_under(cell: Vector2i, eff: Dictionary) -> Array[Vector2i]:
	var size := _vec(eff.get("stands_on"), Vector2i.ONE)
	var out: Array[Vector2i] = []
	for dy in maxi(1, size.y):
		for dx in maxi(1, size.x):
			out.append(cell - Vector2i(dx, dy))
	return out

# --------------------------------------------------------------------------- the recipe's part

## What the tile set is built from beside its definition: the facets of every tile that say
## where it lies and what it is.
static func inputs(catalog: CatalogReader) -> Array:
	var out: Array = []
	for def in catalog.tileset_defs():
		if not wanted(def):
			continue
		var tiles := JsonUtil.to_dict(def.get("tiles", {}))
		var ids := tiles.keys()
		ids.sort()
		for id: Variant in ids:
			var asset := catalog.asset(JsonUtil.to_str(id))
			var eff := CatalogReader.effective(asset)
			out.append([id, asset.get("sha256", ""), eff.get("origin"), eff.get("collision"), eff.get("role"), eff.get("tags", [])])
	return out

## The tiles of the definition that lie in the source `source_id`: [{id, coords, at}], by id.
static func tiles_of_source(def: Dictionary, source_id: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var tiles := JsonUtil.to_dict(def.get("tiles", {}))
	var ids := tiles.keys()
	ids.sort()
	for id: Variant in ids:
		var entry := JsonUtil.to_dict(tiles[id])
		if JsonUtil.to_int(entry.get("source", -1)) == source_id:
			out.append({"id": JsonUtil.to_str(id), "coords": _vec(entry.get("coords")), "at": _vec(entry.get("at"))})
	return out

## Sets the layer `layer_name` of a tile when the tile set has it and the value differs.
static func _set_data(ts: TileSet, td: TileData, layer_name: String, value: Variant) -> void:
	if ts.get_custom_data_layer_by_name(layer_name) == -1:
		return
	if td.get_custom_data(layer_name) != value:
		td.set_custom_data(layer_name, value)

## Makes the tile of `asset` at `coords` of `src` what the catalog says: its origin and its
## custom data. Returns true when the tile was created by this call.
static func configure_tile(ts: TileSet, src: TileSetAtlasSource, coords: Vector2i, at: Vector2i, cell: Vector2i, asset: Dictionary, eff: Dictionary) -> bool:
	var is_new := not src.has_tile(coords)
	if is_new:
		src.create_tile(coords)
	var td := src.get_tile_data(coords, 0)
	var origin := texture_origin(_vec(eff.get("origin"), cell / 2), at, cell)
	if td.texture_origin != origin:
		td.texture_origin = origin
	var data := custom_data(asset, eff)
	for layer_name: String in data.keys():
		_set_data(ts, td, layer_name, data[layer_name])
	return is_new

## A navigation polygon over the diamond, for a ground tile nobody blocks (T9.06).
static func navigation_polygon(footprint: Vector2i) -> NavigationPolygon:
	var poly := NavigationPolygon.new()
	poly.vertices = diamond(footprint)
	poly.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	return poly

# --------------------------------------------------------------------------- the maps' part

var _catalog: CatalogReader
var _def: Dictionary = {}
## asset id -> {source, coords}
var _tiles: Dictionary = {}
## id of a group's first turn -> {turn number: asset id}
var _groups: Dictionary = {}
## asset id -> id of its group's first turn
var _group_of: Dictionary = {}
## asset id -> effective facets, for the tiles of the set
var _facets: Dictionary = {}
var _ids: Array[String] = []

func _init(catalog: CatalogReader) -> void:
	_catalog = catalog
	for def in catalog.tileset_defs():
		if wanted(def):
			_def = def
			break
	var tiles := JsonUtil.to_dict(_def.get("tiles", {}))
	for id: Variant in tiles.keys():
		var asset_id := JsonUtil.to_str(id)
		var entry := JsonUtil.to_dict(tiles[id])
		_tiles[asset_id] = {"source": JsonUtil.to_int(entry.get("source", -1)), "coords": _vec(entry.get("coords")), "of": JsonUtil.to_str(entry.get("of", ""))}
		_ids.append(asset_id)
	_ids.sort()
	for asset_id in _ids:
		var eff := CatalogReader.effective(catalog.asset(asset_id))
		_facets[asset_id] = eff
		# `of` names the first turn of the tile's own set (a tile in two colours is two sets)
		var placed: Dictionary = _tiles[asset_id]
		var first: String = placed["of"]
		if first == "" or not eff.has("turn"):
			continue
		_group_of[asset_id] = first
		if not _groups.has(first):
			_groups[first] = {}
		var turns: Dictionary = _groups[first]
		turns[JsonUtil.to_int(eff.get("turn", 0))] = asset_id

## True when the catalog describes an isometric tile set with a tile in it.
func has_tiles() -> bool:
	return not _tiles.is_empty()

## The name of the tile set ("iso") and the file the tile set recipe saves it to.
func tileset_name() -> String:
	return JsonUtil.to_str(_def.get("name", ""))

func tileset_path() -> String:
	return Paths.TILESETS_DIR + "%s.tres" % tileset_name()

## The diamond of the project, in px.
func footprint() -> Vector2i:
	return _vec(_def.get("tile_size"))

## The ids of the tiles of the set, sorted.
func tile_ids() -> Array[String]:
	return _ids.duplicate()

## The effective facets of a tile of the set ({} for anything else).
func facets(asset_id: String) -> Dictionary:
	return JsonUtil.to_dict(_facets.get(asset_id, {}))

## The turns a tile has, in order: [0, 1, 2, 3] for one drawn four ways, [0] for one picture.
func turns_of(asset_id: String) -> Array[int]:
	var out: Array[int] = []
	if not _group_of.has(asset_id):
		if _tiles.has(asset_id):
			out.append(0)
		return out
	var turns: Dictionary = _groups[_group_of[asset_id]]
	for turn: int in turns.keys():
		out.append(turn)
	out.sort()
	return out

## The id of the picture that is `asset_id` turned to `turn` ("" when the tile is not in the
## set). `asset_id` is any turn of the tile; a tile that is one picture is itself at every turn,
## and a turn the pack did not draw is the tile's first.
func turned(asset_id: String, turn: int = 0) -> String:
	if not _tiles.has(asset_id):
		return ""
	if not _group_of.has(asset_id):
		return asset_id
	var first: String = _group_of[asset_id]
	var turns: Dictionary = _groups[first]
	if turns.has(turn):
		return JsonUtil.to_str(turns[turn])
	var known := turns_of(asset_id)
	return JsonUtil.to_str(turns[known[0]])

## Where a tile is in the tile set: `{source, coords, asset_id, turn}` to give to
## `TileMapLayer.set_cell(cell, source, coords)`, or {} when the tile is not in the set.
func tile_for(asset_id: String, turn: int = 0) -> Dictionary:
	var found := turned(asset_id, turn)
	if found == "":
		return {}
	var entry: Dictionary = _tiles[found]
	return {"source": entry["source"], "coords": entry["coords"], "asset_id": found, "turn": JsonUtil.to_int(facets(found).get("turn", 0))}

## Paints a tile into a cell of a layer that shows the tile set. False when the tile is not in
## the set (nothing is painted).
func paint(layer: TileMapLayer, cell: Vector2i, asset_id: String, turn: int = 0) -> bool:
	var tile := tile_for(asset_id, turn)
	if tile.is_empty():
		return false
	var source: int = tile["source"]
	var coords: Vector2i = tile["coords"]
	layer.set_cell(cell, source, coords)
	return true

## `sides` as a sorted list of the sides it names (n, e, s, w), each once.
static func normalized_joins(sides: Array) -> Array[String]:
	var out: Array[String] = []
	for side in SIDES:
		if sides.has(side):
			out.append(side)
	return out

## `sides` after `quarters` quarter turns clockwise (n becomes e, e becomes s, ...).
static func turned_joins(sides: Array, quarters: int) -> Array[String]:
	var moved: Array = []
	for side: Variant in sides:
		var index := SIDES.find(JsonUtil.to_str(side))
		if index >= 0:
			moved.append(SIDES[posmod(index + quarters, 4)])
	return normalized_joins(moved)

func _matches(asset_id: String, what: String) -> bool:
	if what == "":
		return true
	var eff := facets(asset_id)
	var asset := _catalog.asset(asset_id)
	return JsonUtil.to_str(asset.get("pack_id", "")) == what or _tags(eff).has(what) or JsonUtil.to_str(eff.get("role", "")) == what

## The tiles of the set that are of `what`: a pack id, a tag or a role ("" for all), by id.
func pieces(what: String) -> Array[String]:
	var out: Array[String] = []
	for asset_id in _ids:
		if _matches(asset_id, what):
			out.append(asset_id)
	return out

## The piece of `what` (a pack id, a tag or a role) that joins on exactly the sides `joins`
## (of n, e, s, w): `{asset_id, turn}` for `tile_for` and `paint`, or {} when the packs have
## none. First a picture whose own `joins` are those sides. Then, for a tile turned four ways
## of which one turn says its sides (set in the audit: the names of such packs say none), the
## turn that brings them there: a turn is a quarter turn clockwise, as `_N`, `_E`, `_S`, `_W`
## and `_0` to `_3` are counted.
func piece_for(what: String, joins: Array) -> Dictionary:
	var want := normalized_joins(joins)
	if want.is_empty():
		return {}
	var candidates := pieces(what)
	for asset_id in candidates:
		var eff := facets(asset_id)
		if eff.has("joins") and normalized_joins(JsonUtil.to_array(eff["joins"])) == want:
			return {"asset_id": asset_id, "turn": JsonUtil.to_int(eff.get("turn", 0))}
	for asset_id in candidates:
		var eff := facets(asset_id)
		if not eff.has("joins") or not _group_of.has(asset_id):
			continue
		var turns: Dictionary = _groups[_group_of[asset_id]]
		if turns.size() != 4:
			continue  # eight turns are eighths: a side does not land on a side
		var own := JsonUtil.to_int(eff.get("turn", 0))
		for turn in turns_of(asset_id):
			var other := JsonUtil.to_str(turns[turn])
			if other == asset_id or facets(other).has("joins"):
				continue
			if turned_joins(JsonUtil.to_array(eff["joins"]), turn - own) == want:
				return {"asset_id": other, "turn": turn}
	return {}
