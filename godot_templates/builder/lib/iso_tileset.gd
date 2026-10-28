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

## What the maps ask a tile: `{asset_id, footstep, tillable, water, lift, stack}`. The surface
## is the asset's `surface:<name>` tag; `tillable` and `water` are said by the catalog (the tags
## of those names, the role WATER), never guessed from the art. `lift` (how high a piece raises
## what stands on it) and `stack` (a block, a storey, a roof, ...) are what a level's height
## layers ask (the tools addon's `height_layers.gd`, 2026-10-26).
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
		"lift": JsonUtil.to_int(eff.get("lift", 0)),
		"stack": stack_data(eff),
	}

## The `stack` of a tile's data: the catalog's, and for a ramp with its facet `ramp` (T18.20)
## "ramp:<low>:<high>:<side>", its two ends (px) and the side of the grid it rises to.
static func stack_data(eff: Dictionary) -> String:
	var stack := JsonUtil.to_str(eff.get("stack", ""))
	var ramp := JsonUtil.to_array(eff.get("ramp", []))
	if stack == "ramp" and ramp.size() == 3:
		return "ramp:%d:%d:%s" % [JsonUtil.to_int(ramp[0]), JsonUtil.to_int(ramp[1]), JsonUtil.to_str(ramp[2])]
	return stack

## Puts a sprite that shows an object (a tree, a house) on the middle of a cell: its picture's
## `origin` (the middle of the diamond it stands on, from the catalog) lies on `at`.
static func stand(sprite: Sprite2D, eff: Dictionary, at: Vector2) -> void:
	sprite.centered = false
	sprite.offset = -Vector2(_vec(eff.get("origin")))
	sprite.position = at

## The cells an object stands on when it is put on `cell`: `stands_on` [columns, rows] of the
## catalog, `cell` being the one of them nearest the camera (the highest x and y): the middle of
## that cell is where `stand` puts the picture's `origin`, and the corner of it that points down
## is where an object of several cells is cut in two for sorting (RpgIso.sort_keys).
static func cells_under(cell: Vector2i, eff: Dictionary) -> Array[Vector2i]:
	var size := stands_on(eff)
	var out: Array[Vector2i] = []
	for dy in size.y:
		for dx in size.x:
			out.append(cell - Vector2i(dx, dy))
	return out

## How many cells an object stands on, [columns, rows]: at least one each way.
static func stands_on(eff: Dictionary) -> Vector2i:
	var size := _vec(eff.get("stands_on"), Vector2i.ONE)
	return Vector2i(maxi(1, size.x), maxi(1, size.y))

## The outline of the cells an object of `size` cells stands on, around the middle of the cell
## nearest the camera: the top, the right, the bottom and the left corner.
static func outline(size: Vector2i, footprint: Vector2i) -> PackedVector2Array:
	var a := maxi(1, size.x)
	var b := maxi(1, size.y)
	return PackedVector2Array([on_diamond(1 - a, 1 - b, footprint), on_diamond(1, 1 - b, footprint), on_diamond(1, 1, footprint), on_diamond(1 - a, 1, footprint)])

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
			var row := [id, asset.get("sha256", ""), eff.get("origin"), eff.get("collision"), eff.get("role"), eff.get("tags", [])]
			if eff.has("iso_terrain"):  # only a piece of a terrain has it (T17.31)
				row.append(eff["iso_terrain"])
			for key: String in ["lift", "stack", "ramp"]:  # only a piece of a stack has them (2026-10-26, T18.20)
				if eff.has(key):
					row.append([key, eff[key]])
			var placed := JsonUtil.to_dict(tiles[id])
			if placed.has("frames"):  # only a tile that moves
				row.append(["frames", placed["frames"], placed.get("fps", 8.0)])
			out.append(row)
	return out

## The tiles of the definition that lie in the source `source_id`: [{id, coords, at, frames,
## fps}], by id; `frames` is 1 for a tile that does not move.
static func tiles_of_source(def: Dictionary, source_id: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var tiles := JsonUtil.to_dict(def.get("tiles", {}))
	var ids := tiles.keys()
	ids.sort()
	for id: Variant in ids:
		var entry := JsonUtil.to_dict(tiles[id])
		if JsonUtil.to_int(entry.get("source", -1)) == source_id:
			out.append({"id": JsonUtil.to_str(id), "coords": _vec(entry.get("coords")), "at": _vec(entry.get("at")), "frames": maxi(1, JsonUtil.to_int(entry.get("frames", 1))), "fps": JsonUtil.to_float(entry.get("fps", 8.0))})
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

## Makes a tile that moves play its frames: they lie in the `frames - 1` cells after its own
## in the atlas (rpggen/core/iso_atlas.py), in one row, at `fps`. A tile of one frame is left
## as it is.
static func animate(src: TileSetAtlasSource, coords: Vector2i, frames: int, fps: float) -> void:
	if frames < 2:
		return
	if src.get_tile_animation_columns(coords) != frames:
		src.set_tile_animation_columns(coords, frames)
	if src.get_tile_animation_frames_count(coords) != frames:
		src.set_tile_animation_frames_count(coords, frames)
	if not is_equal_approx(src.get_tile_animation_speed(coords), fps):
		src.set_tile_animation_speed(coords, fps)

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
## asset id -> true for a picture that is in the set only for an imported map that paints it
## (T17.28: an object of a pack, a picture of its samples): no plan paints it
var _maps_only: Dictionary = {}

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
		_tiles[asset_id] = {"source": JsonUtil.to_int(entry.get("source", -1)), "coords": _vec(entry.get("coords")), "of": JsonUtil.to_str(entry.get("of", "")), "at": _vec(entry.get("at"))}
		if JsonUtil.to_bool(entry.get("maps_only", false)):
			_maps_only[asset_id] = true
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

## The instance id of the catalog the set was read from: what a result worked out from the
## whole set is kept by for the rest of a build (`IsoHouse.kit`).
func catalog_id() -> int:
	return _catalog.get_instance_id()

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

## The tiles of the set that are of `what`: a pack id, a tag or a role ("" for all), by id. A
## picture that is in the set only for an imported map is none of them.
func pieces(what: String) -> Array[String]:
	var out: Array[String] = []
	for asset_id in _ids:
		if _matches(asset_id, what) and not _maps_only.has(asset_id):
			out.append(asset_id)
	return out

## True for a picture that is in the set only for an imported map that paints it (T17.28).
func maps_only(asset_id: String) -> bool:
	return _maps_only.has(asset_id)

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

## Every way the pieces of `what` can be laid: [{asset_id, turn, joins}], a picture with its own
## `joins` and, for a tile turned four ways of which one turn says its sides, each other turn
## with the sides the turn brings them to (`piece_for`'s two rules). In the order of the ids.
func laid_pieces(what: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for asset_id in pieces(what):
		var eff := facets(asset_id)
		if not eff.has("joins"):
			continue
		var own_joins := normalized_joins(JsonUtil.to_array(eff["joins"]))
		var own := JsonUtil.to_int(eff.get("turn", 0))
		out.append({"asset_id": asset_id, "turn": own, "joins": own_joins})
		if not _group_of.has(asset_id):
			continue
		var turns: Dictionary = _groups[_group_of[asset_id]]
		if turns.size() != 4:
			continue
		for turn in turns_of(asset_id):
			var other := JsonUtil.to_str(turns[turn])
			if other == asset_id or facets(other).has("joins"):
				continue
			out.append({"asset_id": other, "turn": turn, "joins": turned_joins(own_joins, turn - own)})
	return out

## How many sides differ between two lists of sides.
static func wrong_sides(have: Array, want: Array) -> int:
	var wrong := 0
	for side in SIDES:
		if have.has(side) != want.has(side):
			wrong += 1
	return wrong

## The piece of `what` for the sides `joins` when the packs have no piece for exactly those:
## the one with the fewest wrong sides (the first of them by id), as `{asset_id, turn, wrong}`;
## {} when no piece of `what` says its sides at all. `wrong` is 0 for an exact piece.
func nearest_piece(what: String, joins: Array) -> Dictionary:
	var want := normalized_joins(joins)
	var exact := piece_for(what, want)
	if not exact.is_empty():
		exact["wrong"] = 0
		return exact
	var best := {}
	var best_wrong := SIDES.size() + 1
	for piece in laid_pieces(what):
		var wrong := wrong_sides(JsonUtil.to_array(piece["joins"]), want)
		if wrong < best_wrong:
			best_wrong = wrong
			best = {"asset_id": piece["asset_id"], "turn": piece["turn"], "wrong": wrong}
	return best

## The tiles of `role` a map is filled with, one per tile (the first turn of each), flat ones
## first: a block that rises is ground too, but a floor of blocks hides who stands behind them.
## A piece that says its sides (a road's corner, a shore) is not one of them.
func plain_tiles(role: String) -> Array[String]:
	var flat: Array[String] = []
	var raised: Array[String] = []
	for asset_id in _ids:
		var eff := facets(asset_id)
		if JsonUtil.to_str(eff.get("role", "")) != role or eff.has("joins") or eff.has("edge") or _maps_only.has(asset_id):
			continue
		if eff.has("post") or eff.has("roof"):
			continue  # a piece of a house (after T17.22)
		if _group_of.has(asset_id) and _group_of[asset_id] != asset_id:
			continue  # a turn of a tile that is listed by its first
		if JsonUtil.to_int(eff.get("rise", 0)) > 0:
			raised.append(asset_id)
		else:
			flat.append(asset_id)
	return flat if not flat.is_empty() else raised

## The tile of `role` the maps paint when they need one and no piece is asked for: the first
## plain one, else the first piece that says its sides. "" when the packs have none.
func plain_tile(role: String) -> String:
	var plain := plain_tiles(role)
	if not plain.is_empty():
		return plain[0]
	for asset_id in pieces(role):
		var eff := facets(asset_id)
		if not eff.has("edge") and not eff.has("post") and not eff.has("roof"):
			return asset_id
	return ""

# --------------------------------------------------------------------------- pieces along a side
#
# A wall segment, a wall with a door or a window, a fence (T17.21, T17.22): a tile that fills no
# diamond and stands along one side of its cell, which its facet `edge` names (n, e, s, w: the
# sides of the grid, measured from the picture). Its four turns are four tiles of one set, and
# which turn stands on which side differs from pack to pack, so the side is never taken from
# the turn. Such a tile is no tile a map is filled or bordered with cell by cell
# (`plain_tiles`, `plain_tile` leave it out): it is asked for by the side.

## The tags that make a piece along a side something else than a plain wall.
const EDGE_OPENINGS: Array[String] = ["door", "window"]
const FENCE_TAG := "fence"
const ROOF_TAG := "roof"

## The first turn of the set a tile is one turn of; the tile itself when it is one picture.
func first_of(asset_id: String) -> String:
	return JsonUtil.to_str(_group_of.get(asset_id, asset_id))

## The side of its cell a tile stands along ("n", "e", "s", "w"), or "" for any other tile.
func edge_of(asset_id: String) -> String:
	return JsonUtil.to_str(facets(asset_id).get("edge", ""))

## The members of the set `asset_id` is one turn of, by the side each stands along:
## `{side: asset id}`. A piece that is one picture is a set of one.
func edge_members(asset_id: String) -> Dictionary:
	var out := {}
	if not _tiles.has(asset_id):
		return out
	var ids: Array[String] = [asset_id]
	if _group_of.has(asset_id):
		ids.clear()
		var turns: Dictionary = _groups[_group_of[asset_id]]
		for turn in turns_of(asset_id):
			ids.append(JsonUtil.to_str(turns[turn]))
	for id in ids:
		var side := edge_of(id)
		if side != "" and not out.has(side):
			out[side] = id
	return out

## The sets of pieces along a side that are of `what` (a pack id, a tag or a role; "" for all)
## and have none of the tags `without`: the first turn of each, by id.
func edge_sets(what: String = "", without: Array = []) -> Array[String]:
	var out: Array[String] = []
	for asset_id in _ids:
		if edge_of(asset_id) == "" or not _matches(asset_id, what):
			continue
		var first := JsonUtil.to_str(_group_of.get(asset_id, asset_id))
		if out.has(first):
			continue
		var tags := _tags(facets(asset_id))
		var left_out := false
		for tag: Variant in without:
			if tags.has(tag):
				left_out = true
		if not left_out:
			out.append(first)
	return out

## The piece that stands along `side` (n, e, s, w) of its cell: `{asset_id, turn}` for
## `tile_for` and `paint`, or {} when the packs have none. `what` is a wall's set (the id of any
## of its turns: then the member of that set), or a pack id, a tag or a role (then the first
## set of it, by id, that has a member on that side).
func edge_piece(what: String, side: String) -> Dictionary:
	var sets: Array[String] = []
	if _tiles.has(what):
		sets.append(what)
	else:
		sets = edge_sets(what)
	for first in sets:
		var members := edge_members(first)
		if members.has(side):
			var found := JsonUtil.to_str(members[side])
			return {"asset_id": found, "turn": JsonUtil.to_int(facets(found).get("turn", 0))}
	return {}

## How far the member of a set on `side` rises above its diamond (0 when it has none).
func edge_rise(asset_id: String, side: String) -> int:
	var members := edge_members(asset_id)
	if not members.has(side):
		return 0
	return JsonUtil.to_int(facets(JsonUtil.to_str(members[side])).get("rise", 0))

## The plain walls of the packs that stand along all four sides (no door, no window, no roof):
## the first turn of each set, by id. `fences` says whether the sets tagged `fence` are meant
## or the others.
func wall_sets(fences: bool = false) -> Array[String]:
	var out: Array[String] = []
	var without: Array = [ROOF_TAG]
	without.append_array(EDGE_OPENINGS)
	for first in edge_sets("WALL", without):
		if edge_members(first).size() == SIDES.size() and _tags(facets(first)).has(FENCE_TAG) == fences:
			out.append(first)
	return out

## The set the edge of a map is laid from, or "": the lowest plain wall (who walks along the
## near sides of a map is not hidden by it), a fence first when `fence_first` (a farm, a yard),
## else a fence only when the packs have no other wall. Of two as low the one with the shorter
## name (the plainest), then the first by id.
func border_set(fence_first: bool = false) -> String:
	for fences: bool in [fence_first, not fence_first]:
		var best := ""
		for first in wall_sets(fences):
			var lower := edge_rise(best, "n") - edge_rise(first, "n")
			if best == "" or lower > 0 or (lower == 0 and first.length() < best.length()):
				best = first
		if best != "":
			return best
	return ""

# --------------------------------------------------------------------------- posts and roofs
#
# The pieces of a house that are no walls (after T17.22). A **post** stands on a corner of its
# diamond (its facet `post`: `nw` the top corner, where the sides n and w meet, `ne` the right
# one, `es` the lowest, `sw` the left one): it is put where two sides of a wall meet. A **roof
# piece** covers its diamond a storey up; its facet `roof` says its shape and turn (`slope:n`,
# one slope high along the side n; `hip:es`, the quarter of a hipped roof high at the corner
# es; `ridge:ew`, a gable over one cell whose ridge runs from the side w to the side e;
# `peak`; `valley:nw`, an inner corner low at nw) and `roof_rise` how much its slopes rise over
# a cell. Neither is a tile a map is filled with (`plain_tiles` leaves them out).

const POST_TAG := "post"
## The corners of a diamond, by the two sides that meet there, clockwise from the top one.
const CORNERS: Array[String] = ["nw", "ne", "es", "sw"]

## The corner of its cell a post stands on, or "" for any other tile.
func post_of(asset_id: String) -> String:
	return JsonUtil.to_str(facets(asset_id).get("post", ""))

## The shape and turn of a roof piece (`slope:n`, `hip:es`, ...), or "" for any other tile.
func roof_of(asset_id: String) -> String:
	return JsonUtil.to_str(facets(asset_id).get("roof", ""))

## The members of the set `asset_id` is one turn of, by the value of the facet `facet` of each
## (`post`: the corner; `roof`: the shape): `{value: asset id}`, the first by turn of each value.
func members_by(asset_id: String, facet: String) -> Dictionary:
	var out := {}
	if not _tiles.has(asset_id):
		return out
	var ids: Array[String] = [asset_id]
	if _group_of.has(asset_id):
		ids.clear()
		var turns: Dictionary = _groups[_group_of[asset_id]]
		for turn in turns_of(asset_id):
			ids.append(JsonUtil.to_str(turns[turn]))
	for id in ids:
		var value := JsonUtil.to_str(facets(id).get(facet, ""))
		if value != "" and not out.has(value):
			out[value] = id
	return out

## The sets of posts that stand on all four corners: the first turn of each, by id.
func post_sets() -> Array[String]:
	var out: Array[String] = []
	for asset_id in _ids:
		if post_of(asset_id) == "" or _maps_only.has(asset_id):
			continue
		var first := first_of(asset_id)
		if not out.has(first) and members_by(first, "post").size() == CORNERS.size():
			out.append(first)
	return out

## The post of the set `post_set` that stands on `corner`: `{asset_id, turn}`, or {}.
func post_piece(post_set: String, corner: String) -> Dictionary:
	var members := members_by(post_set, "post")
	if not members.has(corner):
		return {}
	var found := JsonUtil.to_str(members[corner])
	return {"asset_id": found, "turn": JsonUtil.to_int(facets(found).get("turn", 0))}

## The sets of roof pieces that have a shape: the first turn of each, by id.
func roof_sets() -> Array[String]:
	var out: Array[String] = []
	for asset_id in _ids:
		if roof_of(asset_id) == "" or _maps_only.has(asset_id):
			continue
		var first := first_of(asset_id)
		if not out.has(first):
			out.append(first)
	return out

## The pictures already read in this build, by path, for `mean_colour`.
static var _images: Dictionary = {}

## The picture at `path` (an atlas of the tile set), read once a build; null when it cannot be.
static func image_at(path: String) -> Image:
	if not _images.has(path):
		var texture: Texture2D = null
		if path != "" and ResourceLoader.exists(path):
			texture = load(path) as Texture2D
		var image: Image = null
		if texture != null:
			image = texture.get_image()
		if image != null and image.is_compressed():
			image.decompress()
		_images[path] = image
	var found: Image = _images[path]
	return found

## The mean colour of what is painted in a tile's picture, or a colour of alpha 0 when it
## cannot be read: what a post of the colour of a wall is chosen by.
func mean_colour(asset_id: String) -> Color:
	var picture := picture_of(asset_id)
	var region := JsonUtil.to_array(picture.get("region", []))
	if region.size() != 4:
		return Color(0, 0, 0, 0)
	# the recipes ask again and again (every room asks for the village's house): read once
	var key := "%s|%s" % [JsonUtil.to_str(picture.get("texture", "")), str(region)]
	if not _colours.has(key):
		_colours[key] = _mean_colour(JsonUtil.to_str(picture.get("texture", "")), region)
	var found: Color = _colours[key]
	return found

## The mean colours already read in this build, by picture and region.
static var _colours: Dictionary = {}

static func _mean_colour(path: String, region: Array) -> Color:
	var image := image_at(path)
	if image == null or image.is_empty():
		return Color(0, 0, 0, 0)
	var area := Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3]))
	area = area.intersection(Rect2i(Vector2i.ZERO, image.get_size()))
	var sum := Vector3.ZERO
	var count := 0
	# every second pixel each way is enough to tell brick from wood
	for y in range(area.position.y, area.end.y, 2):
		for x in range(area.position.x, area.end.x, 2):
			var pixel := image.get_pixel(x, y)
			if pixel.a >= 0.5:
				sum += Vector3(pixel.r, pixel.g, pixel.b)
				count += 1
	if count == 0:
		return Color(0, 0, 0, 0)
	return Color(sum.x / count, sum.y / count, sum.z / count, 1.0)

## Of the sets `sets`, the one whose pictures look most like the tile `like` (the nearest mean
## colour; the first by id of two as near, and the first when no colour can be read); "" for
## none.
func nearest_in_colour(sets: Array[String], like: String) -> String:
	var best := ""
	var best_far := INF
	if sets.size() < 2:
		return sets[0] if sets.size() == 1 else ""
	var want := mean_colour(like)
	for first in sets:
		var have := mean_colour(first)
		var far := INF
		if want.a > 0.0 and have.a > 0.0:
			far = Vector3(want.r - have.r, want.g - have.g, want.b - have.b).length()
		if best == "" or far < best_far:
			best = first
			best_far = far
	return best

## The posts a wall of `wall_set` gets where two of its sides meet (the edge of a map, a house
## of pieces): of the packs' sets of posts no higher than the wall (`POST_TALLER`: a storey's
## pole on a low wall stood out like a mast), the one of the colour of the wall; "" for none.
func post_set_for(wall_set: String) -> String:
	var high := edge_rise(wall_set, "n")
	var fitting: Array[String] = []
	for first in post_sets():
		var members := members_by(first, "post")
		var rise := JsonUtil.to_int(facets(JsonUtil.to_str(members.get("nw", first))).get("rise", 0))
		if rise <= high * POST_TALLER + POST_SLACK:
			fitting.append(first)
	return nearest_in_colour(fitting, wall_set)

## A post may be this many times as high as the wall it stands at, and a few px more (both
## measured over the diamond's top corner: the wall along `n` and the post on `nw`).
const POST_TALLER := 1.5
const POST_SLACK := 4

## Where the picture of a tile of the set is: `{texture: path of its atlas picture, region:
## [x, y, w, h] of the tile's own picture in it}`, or {} for anything else. A piece of a house or
## of a yard's fence is shown by a sprite, not painted into a layer; the sprite shows the same
## pixels the tile set does.
func picture_of(asset_id: String) -> Dictionary:
	if not _tiles.has(asset_id):
		return {}
	var placed: Dictionary = _tiles[asset_id]
	var atlas := {}
	for raw: Variant in JsonUtil.to_array(_def.get("sources", [])):
		var source := JsonUtil.to_dict(raw)
		if JsonUtil.to_int(source.get("source_id", -1)) == JsonUtil.to_int(placed["source"]):
			atlas = _catalog.asset(JsonUtil.to_str(source.get("asset", "")))
	if atlas.is_empty():
		return {}
	var grid := JsonUtil.to_dict(CatalogReader.effective(atlas).get("grid", {}))
	var cell := _vec(grid.get("cell"), footprint())
	var coords: Vector2i = placed["coords"]
	var at: Vector2i = placed["at"]
	var size := _vec(facets(asset_id).get("canvas"), cell)
	return {
		"texture": "res://" + JsonUtil.to_str(atlas.get("path", "")),
		"region": [coords.x * cell.x + at.x, coords.y * cell.y + at.y, size.x, size.y],
	}
