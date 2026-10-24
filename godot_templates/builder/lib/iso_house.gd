extends RefCounted
## A house of pieces (T17.22). Some isometric packs draw no whole house: they draw the walls,
## the walls with a door or a window and the roofs of one as tiles of their own (*Medieval
## Town*, *Modular Buildings*, the *Miniature* packs). From such a kit a house is put together
## on the footprint a plan gives it:
##
## * on every cell of the footprint's rim the wall that stands along the side that looks out
##   (`IsoTileset.edge_piece`: the side is the piece's `edge`, never its turn);
## * the piece with a door on the south side of the cell above the plan's door cell (the plan's
##   door cell lies one row below the footprint, in front of the side that faces the camera to
##   the left: `MapGeo.building_info`);
## * a piece with a window on some of the other places, by the seed;
## * a roof tile over every cell, one storey up, when the packs have a roof that is a tile.
##
## **A storey's height** is not in the catalog. It is taken to be how far the wall rises above
## its diamond on a far side (`rise` of its member on `n`): there the wall begins at the far
## corner of the diamond and all of its height shows above it.
##
## **Sorting.** The house is one building: nobody stands on its footprint, so it sorts against
## actors by the rule of every isometric object of several cells (`RpgIso.sort_keys`,
## object_scenes_recipe.gd): what of it lies left of its corner nearest the camera sorts by the
## left corner of its footprint, the rest by the right corner. The pieces are children of two
## nodes on those two lines (`Left`, `Right`), in the order they are drawn: the far walls, the
## near walls, the roofs, each from the back to the front. A roof on the diagonal through the
## nearest corner lies on both sides and is cut in two there.
##
## The parts of a house are plain data (`parts`), so that the entry of the village's house
## carries them into the hash of its scene, and a test can ask what stands where.

const JsonUtil := preload("json_util.gd")
const IsoTileset := preload("iso_tileset.gd")
const TextureUtil := preload("texture_util.gd")

## The id of the entry (ObjectEntries) of the village's house of pieces, and of its scene.
const ENTRY_ID := "rpggen.iso_house"
const ENTRY_NAME := "House"
## The footprint of the village's house: two cells each way, the smallest a plan of a farm
## gives a building and what a whole house of a pack usually stands on.
const VILLAGE_CELLS := Vector2i(2, 2)
## Of this many places for a wall one has a window, about.
const WINDOW_EVERY := 2

## The pieces a house is put together from: `{wall, door, window, roof, storey}`, each the first
## turn of a set ("" for the window and the roof when the packs have none), or {} when the
## packs have no kit: a plain wall along all four sides (no fence) and a wall with a door for
## the south side. The wall is the highest of the packs' (a storey, not a parapet); the door,
## the window and the roof are the ones whose names begin most like the wall's (*grey* walls
## get the *grey* door), else the first by id.
static func kit(iso: IsoTileset) -> Dictionary:
	if iso == null or not iso.has_tiles():
		return {}
	# the recipes ask for it again and again in one build (every room, every hash): once a catalog
	var key := iso.catalog_id()
	if not _kits.has(key):
		_kits[key] = _kit(iso)
	return JsonUtil.to_dict(_kits[key]).duplicate(true)

## The kits already worked out in this build, by the catalog they were read from.
static var _kits: Dictionary = {}

static func _kit(iso: IsoTileset) -> Dictionary:
	var wall := ""
	for first in iso.wall_sets(false):
		var higher := iso.edge_rise(first, "n") - iso.edge_rise(wall, "n")
		# of two as high the one with the shorter name: `wall` before `border_wall`
		if wall == "" or higher > 0 or (higher == 0 and first.length() < wall.length()):
			wall = first
	if wall == "":
		return {}
	var doors: Array[String] = []
	for first in iso.edge_sets("door", [IsoTileset.FENCE_TAG]):
		if iso.edge_members(first).has("s"):
			doors.append(first)
	if doors.is_empty():
		return {}
	var windows: Array[String] = []
	for first in iso.edge_sets("window", ["door", IsoTileset.FENCE_TAG]):
		if iso.edge_members(first).size() == IsoTileset.SIDES.size():
			windows.append(first)
	var out := {
		"wall": wall,
		"door": _most_alike(doors, wall),
		"window": _most_alike(windows, wall),
		"roof": _roof(iso),
		"storey": iso.edge_rise(wall, "n"),
	}
	# after T17.22: posts at the corners, of the wall's colour, and a roof of pieces
	var post := iso.post_set_for(wall)
	if post != "":
		out["post"] = post
	var roofs := roof_kit(iso)
	if not roofs.is_empty():
		out["roofs"] = roofs
		out["roof_rise"] = JsonUtil.to_int(iso.facets(JsonUtil.to_str(roofs.values()[0])).get("roof_rise", 0))
	return out

## The pieces of one roof (after T17.22): `{shape: asset id}` (`slope:n`, `hip:es`, ...) of the
## packs' roof pieces that have a shape, of one family: the first set with a slope (else the
## first set), and of every other shape the set most like it by name (`_most_alike_both`:
## `roof_corner_green_01` goes with `roof_slant_green_01`, not with `roof_corner_red_01`). {}
## when the packs have no roof piece with a shape.
static func roof_kit(iso: IsoTileset) -> Dictionary:
	var sets := iso.roof_sets()
	if sets.is_empty():
		return {}
	var anchor := sets[0]
	for first in sets:
		if _has_shape(iso, first, "slope"):
			anchor = first
			break
	var out := iso.members_by(anchor, "roof")
	for shape: String in ROOF_SHAPES:
		if _has_shape(iso, anchor, shape):
			continue
		var others: Array[String] = []
		for first in sets:
			if _has_shape(iso, first, shape):
				others.append(first)
		var chosen := _most_alike_both(others, anchor)
		if chosen == "":
			continue
		var members := iso.members_by(chosen, "roof")
		for key: Variant in members:
			if not out.has(key):
				out[key] = members[key]
	return out

const ROOF_SHAPES: Array[String] = ["slope", "hip", "ridge", "peak", "valley"]

static func _has_shape(iso: IsoTileset, first: String, shape: String) -> bool:
	for key: Variant in iso.members_by(first, "roof"):
		if JsonUtil.to_str(key).get_slice(":", 0) == shape:
			return true
	return false

## The one of `ids` whose name begins and ends most like `like` (the first of them when several
## do as much); "" for none.
static func _most_alike_both(ids: Array[String], like: String) -> String:
	var best := ""
	var best_shared := -1
	for id in ids:
		var front := 0
		while front < mini(id.length(), like.length()) and id[front] == like[front]:
			front += 1
		var back := 0
		while back < mini(id.length(), like.length()) - front and id[id.length() - 1 - back] == like[like.length() - 1 - back]:
			back += 1
		if front + back > best_shared:
			best = id
			best_shared = front + back
	return best

## The sides of a cell of a roof of `cells` cells (as a footprint counts them) nearest its
## eaves, and how far in from them it lies: `{sides, level}`. A hipped roof rises one level a
## cell in from its eaves on every side.
static func _roof_ring(cell: Vector2i, cells: Vector2i) -> Dictionary:
	var far := {"n": cell.y, "s": cells.y - 1 - cell.y, "w": cell.x, "e": cells.x - 1 - cell.x}
	var level := mini(mini(cell.y, cells.y - 1 - cell.y), mini(cell.x, cells.x - 1 - cell.x))
	var sides: Array[String] = []
	for side in IsoTileset.SIDES:
		if JsonUtil.to_int(far[side]) == level:
			sides.append(side)
	return {"sides": sides, "level": level}

const OPPOSITE := {"n": "s", "e": "w", "s": "n", "w": "e"}
## The corner high on the quarter of a hipped roof whose eaves are the two sides of a key.
const HIP_APEX := {"nw": "es", "ne": "sw", "es": "nw", "sw": "ne"}

## The shapes a cell of a roof of `cells` cells may be laid with, the best first: a cell along
## one side of the eaves the slope that rises away from it, a cell at a corner of the eaves the
## quarter of a hipped roof (else a slope), a cell under the ridge a gable along it, the middle
## of a square roof a pyramid.
static func roof_wanted(cell: Vector2i, cells: Vector2i) -> Array[String]:
	var ring := _roof_ring(cell, cells)
	var sides: Array[String] = []
	for side: Variant in JsonUtil.to_array(ring["sides"]):
		sides.append(JsonUtil.to_str(side))
	var out: Array[String] = []
	if sides.size() == 1:
		out.append("slope:" + JsonUtil.to_str(OPPOSITE[sides[0]]))
	elif sides.size() == 2 and OPPOSITE[sides[0]] != sides[1]:
		# the sides come in the order n, e, s, w: "nw", "ne", "es", "sw" name the corner
		out.append("hip:" + JsonUtil.to_str(HIP_APEX[sides[0] + sides[1]]))
		out.append("slope:" + JsonUtil.to_str(OPPOSITE[sides[0]]))
	elif sides.size() == 4:
		out.append("peak")
		out.append("ridge:" + ("ew" if cells.x >= cells.y else "ns"))
	else:
		# two opposite sides, or three: under the ridge, which runs between the other two
		var along_ew := sides.has("n") and sides.has("s")
		out.append("ridge:" + ("ew" if along_ew else "ns"))
		out.append("peak")
	return out

## The roof of a footprint of `cells` cells laid from the pieces `roofs` ({shape: asset id}):
## `{cell (Vector2i): {asset_id, level}}`. A hipped roof when every cell has a piece of a shape
## it may have; else, when the packs have a gable over one cell (*Medieval Town*: its slopes and
## hips cover half a cell and are no pieces here), a gable along every row of the longer way,
## each one roof along its ridge; else {} (a house then gets a roof tile a cell, as before).
static func roof_plan(cells: Vector2i, roofs: Dictionary) -> Dictionary:
	var out := {}
	if roofs.is_empty():
		return out
	for y in cells.y:
		for x in cells.x:
			var cell := Vector2i(x, y)
			var chosen := ""
			for shape in roof_wanted(cell, cells):
				if roofs.has(shape):
					chosen = JsonUtil.to_str(roofs[shape])
					break
			if chosen == "":
				return _gables(cells, roofs)
			out[cell] = {"asset_id": chosen, "level": JsonUtil.to_int(_roof_ring(cell, cells)["level"])}
	return out

## A gable over every row of a footprint along its longer way (the ridge of each row from one
## end to the other), or {} when the packs have no gable over one cell.
static func _gables(cells: Vector2i, roofs: Dictionary) -> Dictionary:
	var out := {}
	var along := "ridge:ew" if cells.x >= cells.y else "ridge:ns"
	if not roofs.has(along):
		return out
	for y in cells.y:
		for x in cells.x:
			out[Vector2i(x, y)] = {"asset_id": JsonUtil.to_str(roofs[along]), "level": 0}
	return out

## The one of `ids` whose name begins most like `like` (the first of them when several do as
## much); "" for none.
static func _most_alike(ids: Array[String], like: String) -> String:
	# the names, not the packs': a door of another pack than the walls' is chosen by its name
	# (`thick_wood_doorway_01` goes with `thick_wood_01`, after T17.30)
	var best := ""
	var best_shared := -1
	var own := _name_of(like)
	for id in ids:
		var name := _name_of(id)
		var shared := 0
		while shared < mini(name.length(), own.length()) and name[shared] == own[shared]:
			shared += 1
		if shared > best_shared:
			best = id
			best_shared = shared
	return best

## The name of a picture in its id: after the pack's and the folders' parts, before the cell.
static func _name_of(asset_id: String) -> String:
	return asset_id.get_slice("#", 0).get_slice(".", asset_id.get_slice("#", 0).get_slice_count(".") - 1)

## The roof of the packs that is laid a cell: a tile tagged `roof` that stands along no side,
## one whose four turns rise alike first (a roof with one peak looks the same on every cell; a
## slanted one has a ridge whose direction by its turn nobody measured). "" when the packs have
## no roof that is a tile.
static func _roof(iso: IsoTileset) -> String:
	var any := ""
	for asset_id in iso.pieces(IsoTileset.ROOF_TAG):
		if iso.edge_of(asset_id) != "" or iso.first_of(asset_id) != asset_id:
			continue  # a turn of a roof that is listed by its first
		var rises := {}
		for turn in iso.turns_of(asset_id):
			rises[JsonUtil.to_int(iso.facets(iso.turned(asset_id, turn)).get("rise", 0))] = true
		if rises.size() == 1 and iso.turns_of(asset_id).size() > 1:
			return asset_id
		if any == "":
			any = asset_id
	return any

## The parts of a house of `cells` cells whose door is before the column `door_column`, in the
## order they are drawn: [{asset_id, texture, origin: [x, y], cell: [x, y], lift, kind, side}].
## `cell` is counted from the footprint's first cell (its north-west one), `lift` is how far
## the part is raised (a roof: a storey), `kind` is wall, door, window or roof, and `side` the
## side a wall stands along ("" for a roof). Which walls have a window is drawn from `house_seed`.
static func parts(iso: IsoTileset, pieces: Dictionary, cells: Vector2i, door_column: int, house_seed: int) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if pieces.is_empty():
		return out
	var rng := RandomNumberGenerator.new()
	rng.seed = absi(house_seed) * 31 + cells.x * 7 + cells.y * 13 + door_column
	var order := _back_to_front(cells)
	var door_cell := Vector2i(clampi(door_column, 0, cells.x - 1), cells.y - 1)
	var window := JsonUtil.to_str(pieces.get("window", ""))
	var post := JsonUtil.to_str(pieces.get("post", ""))
	# the posts where two walls meet (after T17.22): the far one after the far walls, the
	# others after the near walls, each covering the ends of the two walls it stands between
	var post_cells := {
		"nw": Vector2i(0, 0),
		"ne": Vector2i(cells.x - 1, 0),
		"sw": Vector2i(0, cells.y - 1),
		"es": Vector2i(cells.x - 1, cells.y - 1),
	}
	for far: bool in [true, false]:
		if not far and post != "":
			var far_corner: Vector2i = post_cells["nw"]
			_add_post(out, iso, post, "nw", far_corner)
		for cell in order:
			for side in _rim_sides(cell, cells):
				if (side == "n" or side == "w") != far:
					continue
				var kind := "wall"
				if side == "s" and cell == door_cell:
					kind = "door"
				elif window != "" and rng.randi() % WINDOW_EVERY == 0:
					kind = "window"
				var found := iso.edge_piece(JsonUtil.to_str(pieces[kind]), side)
				if found.is_empty():  # a window drawn for three sides: the plain wall
					kind = "wall"
					found = iso.edge_piece(JsonUtil.to_str(pieces["wall"]), side)
				if not found.is_empty():
					out.append(_part(iso, JsonUtil.to_str(found["asset_id"]), cell, 0, kind, side))
	if post != "":
		for corner: String in ["ne", "sw", "es"]:
			var at: Vector2i = post_cells[corner]
			_add_post(out, iso, post, corner, at)
	var storey := JsonUtil.to_int(pieces.get("storey", 0))
	# one roof of pieces where the packs have them: slopes up to a ridge, hips at its ends,
	# each ring of cells a slope's rise higher than the one outside it
	var roofs := JsonUtil.to_dict(pieces.get("roofs", {}))
	var plan := roof_plan(cells, roofs)
	var along := "ridge:ew" if cells.x >= cells.y else "ridge:ns"
	if not plan.is_empty() and mini(cells.x, cells.y) > 1 and _only_gables(plan, roofs, along):
		# T17.33: the pack's slopes and hips cover half a cell (*Medieval Town*) and its gables
		# laid a row each are as many roofs as rows: one hipped roof is drawn over the whole
		# house in the colour of its gable (the audit card says why, on the roof pieces)
		var gable := JsonUtil.to_str(roofs[along])
		out.append({
			"asset_id": gable,
			"texture": "",
			"region": [],
			"origin": [0, 0],
			"cell": [0, 0],
			"lift": storey,
			"kind": DRAWN_ROOF,
			"side": "",
			"colour": iso.mean_colour(gable).to_html(false),
			"rise": maxi(JsonUtil.to_int(pieces.get("roof_rise", 0)), 1),
		})
		return out
	if not plan.is_empty():
		var rise := JsonUtil.to_int(pieces.get("roof_rise", 0))
		for cell in order:
			var laid := JsonUtil.to_dict(plan[cell])
			var lift := storey + JsonUtil.to_int(laid["level"]) * rise
			out.append(_part(iso, JsonUtil.to_str(laid["asset_id"]), cell, lift, "roof", ""))
		return out
	var roof := JsonUtil.to_str(pieces.get("roof", ""))
	if roof != "":
		for cell in order:
			out.append(_part(iso, roof, cell, storey, "roof", ""))
	return out

## The kind of the one roof drawn over a house whose pieces make none (T17.33).
const DRAWN_ROOF := "roof_drawn"

static func _only_gables(plan: Dictionary, roofs: Dictionary, along: String) -> bool:
	if not roofs.has(along):
		return false
	var gable := JsonUtil.to_str(roofs[along])
	for key: Variant in plan.keys():
		if JsonUtil.to_str(JsonUtil.to_dict(plan[key]).get("asset_id", "")) != gable:
			return false
	return true

## A point of the footprint's grid of corners (`gx` from 0 to cells.x, `gy` to cells.y) where
## the house's node stands (the middle of the cell nearest the camera), raised by `up`.
static func corner_position(gx: float, gy: float, cells: Vector2i, footprint: Vector2i, up: float) -> Vector2:
	var dx := gx - 0.5 - (cells.x - 1)
	var dy := gy - 0.5 - (cells.y - 1)
	return Vector2((dx - dy) * footprint.x / 2.0, (dx + dy) * footprint.y / 2.0 - up)

## The faces of a hipped roof over a footprint of `cells` with its eaves `lift` px up and its
## ridge along the longer way, `rise` px higher for every cell from the eaves:
## [{points, shade}] from the back to the front (shade 0 the faces away from the light).
static func hipped_roof(cells: Vector2i, footprint: Vector2i, lift: float, rise: float) -> Array[Dictionary]:
	var half := minf(cells.x, cells.y) / 2.0
	var top := lift + rise * half
	var a: Vector2
	var b: Vector2
	if cells.x >= cells.y:
		a = corner_position(half, cells.y / 2.0, cells, footprint, top)
		b = corner_position(cells.x - half, cells.y / 2.0, cells, footprint, top)
	else:
		a = corner_position(cells.x / 2.0, half, cells, footprint, top)
		b = corner_position(cells.x / 2.0, cells.y - half, cells, footprint, top)
	var nw := corner_position(0, 0, cells, footprint, lift)
	var ne := corner_position(cells.x, 0, cells, footprint, lift)
	var se := corner_position(cells.x, cells.y, cells, footprint, lift)
	var sw := corner_position(0, cells.y, cells, footprint, lift)
	var faces: Array[Dictionary] = []
	if cells.x >= cells.y:
		faces.append({"points": PackedVector2Array([nw, ne, b, a]), "shade": 0})  # north
		faces.append({"points": PackedVector2Array([nw, a, sw]), "shade": 0})  # west
		faces.append({"points": PackedVector2Array([ne, se, b]), "shade": 1})  # east
		faces.append({"points": PackedVector2Array([sw, a, b, se]), "shade": 1})  # south
	else:
		faces.append({"points": PackedVector2Array([nw, ne, a]), "shade": 0})  # north
		faces.append({"points": PackedVector2Array([nw, a, b, sw]), "shade": 0})  # west
		faces.append({"points": PackedVector2Array([ne, se, b, a]), "shade": 1})  # east
		faces.append({"points": PackedVector2Array([sw, b, se]), "shade": 1})  # south
	return faces

## The drawn roof of a house (`DRAWN_ROOF` part) under `root`, in front of its walls.
static func _add_drawn_roof(root: Node2D, part: Dictionary, cells: Vector2i, footprint: Vector2i) -> void:
	var colour := Color.from_string(JsonUtil.to_str(part.get("colour", "#8a5a3c")), Color(0.54, 0.35, 0.24))
	var lift := JsonUtil.to_float(part.get("lift", 0))
	var rise := maxf(JsonUtil.to_float(part.get("rise", 1)), footprint.y * 0.5)
	var roof := Node2D.new()
	roof.name = "Roof"
	# in front of both halves of the walls (the Y-sort of the house)
	roof.position = Vector2(0.0, footprint.y / 2.0)
	roof.set_meta(&"asset_id", JsonUtil.to_str(part.get("asset_id", "")))
	roof.set_meta(&"kind", DRAWN_ROOF)
	root.add_child(roof)
	var i := 0
	for face: Dictionary in hipped_roof(cells, footprint, lift, rise):
		var polygon := Polygon2D.new()
		polygon.name = "Face_%d" % i
		var points: PackedVector2Array = face["points"]
		var shifted := PackedVector2Array()
		for p in points:
			shifted.append(p - roof.position)
		polygon.polygon = shifted
		polygon.color = colour.darkened(0.25) if JsonUtil.to_int(face["shade"]) == 0 else colour
		roof.add_child(polygon)
		var edge := Line2D.new()
		edge.name = "Edge_%d" % i
		edge.points = shifted
		edge.closed = true
		edge.width = 1.0
		edge.default_color = colour.darkened(0.55)
		roof.add_child(edge)
		i += 1

static func _add_post(out: Array[Dictionary], iso: IsoTileset, post_set: String, corner: String, cell: Vector2i) -> void:
	var piece := iso.post_piece(post_set, corner)
	if not piece.is_empty():
		out.append(_part(iso, JsonUtil.to_str(piece["asset_id"]), cell, 0, "post", corner))

static func _part(iso: IsoTileset, asset_id: String, cell: Vector2i, lift: int, kind: String, side: String) -> Dictionary:
	var eff := iso.facets(asset_id)
	var origin := JsonUtil.to_array(eff.get("origin", [0, 0]))
	var picture := iso.picture_of(asset_id)
	return {
		"asset_id": asset_id,
		"texture": JsonUtil.to_str(picture.get("texture", "")),
		"region": JsonUtil.to_array(picture.get("region", [0, 0, 0, 0])),
		"origin": [JsonUtil.to_int(origin[0]), JsonUtil.to_int(origin[1])],
		"cell": [cell.x, cell.y],
		"lift": lift,
		"kind": kind,
		"side": side,
	}

## The cells of a footprint from the back to the front: by the depth of their diamonds, and of
## two as deep the western one first.
static func _back_to_front(cells: Vector2i) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for depth in cells.x + cells.y - 1:
		for y in range(cells.y - 1, -1, -1):
			var x := depth - y
			if x >= 0 and x < cells.x:
				out.append(Vector2i(x, y))
	return out

## The sides of a cell of a footprint that look out of it, in the order n, w, e, s.
static func _rim_sides(cell: Vector2i, cells: Vector2i) -> Array[String]:
	var out: Array[String] = []
	if cell.y == 0:
		out.append("n")
	if cell.x == 0:
		out.append("w")
	if cell.x == cells.x - 1:
		out.append("e")
	if cell.y == cells.y - 1:
		out.append("s")
	return out

## The entry (ObjectEntries) of the village's house of pieces, or {} when the packs have no
## kit: a BUILDING drawn for the isometric view that stands on `VILLAGE_CELLS`, with its parts.
## It has no picture of its own (`region` is empty): the object recipe builds its scene from
## the parts.
static func entry(iso: IsoTileset, house_seed: int) -> Dictionary:
	var pieces := kit(iso)
	if pieces.is_empty():
		return {}
	var cells := VILLAGE_CELLS
	@warning_ignore("integer_division")
	var door_column := (cells.x - 1) / 2
	var footprint := iso.footprint()
	return {
		"id": ENTRY_ID,
		"name": ENTRY_NAME,
		"role": "BUILDING",
		"tags": ["kit"],
		"texture_path": "",
		"region": [0, 0, 0, 0],
		"origin": [0, 0],
		"footprint": [],
		"collision": {"profile": "NONE"},
		"door": [],
		"sha256": "",
		"open_region": [],
		"iso": [footprint.x, footprint.y],
		"stands_on": [cells.x, cells.y],
		"kit": pieces,
		"parts": parts(iso, pieces, cells, door_column, house_seed),
	}

## True for the entry of a house of pieces.
static func is_kit(e: Dictionary) -> bool:
	return e.has("parts")

## Where a part is drawn from the middle of the footprint's cell nearest the camera (where the
## building's node stands): the middle of its own cell, raised by its lift.
static func part_position(part: Dictionary, cells: Vector2i, footprint: Vector2i) -> Vector2:
	var cell := JsonUtil.to_array(part["cell"])
	var dx := JsonUtil.to_int(cell[0]) - (cells.x - 1)
	var dy := JsonUtil.to_int(cell[1]) - (cells.y - 1)
	return Vector2((dx - dy) * footprint.x / 2.0, (dx + dy) * footprint.y / 2.0 - JsonUtil.to_float(part.get("lift", 0)))

## The pictures already read in this build, by path: an atlas is asked once a part.
static var _images: Dictionary = {}

## True when something is painted in `area` of the picture at `path` (true as well when the
## picture cannot be read: the part is then shown whole).
static func _painted(path: String, area: Rect2i) -> bool:
	if not _images.has(path):
		var texture := load(path) as Texture2D
		var image: Image = null
		if texture != null:
			image = texture.get_image()
		if image != null and image.is_compressed():
			image.decompress()
		_images[path] = image
	var read: Image = _images[path]
	if read == null or read.is_empty():
		return true
	var inside := area.intersection(Rect2i(Vector2i.ZERO, read.get_size()))
	if inside.size.x <= 0 or inside.size.y <= 0:
		return false
	return not read.get_region(inside).is_invisible()

## Puts the parts of a house under `root`, which stands on the middle of the cell of its
## footprint nearest the camera: two nodes `Left` and `Right` on the lines the two halves sort
## by, and under them a sprite a part (`<Kind>_<x>_<y>[_<side>]`), in the order of `parts`.
## Returns {left, right}.
static func assemble(root: Node2D, house_parts: Array, cells: Vector2i, footprint: Vector2i) -> Dictionary:
	root.y_sort_enabled = true
	var halves := {}
	var lines := {"left": (1 - cells.x) * footprint.y / 2.0, "right": (1 - cells.y) * footprint.y / 2.0}
	for half_name: String in ["left", "right"]:
		var half := Node2D.new()
		half.name = half_name.capitalize()
		half.position = Vector2(0.0, JsonUtil.to_float(lines[half_name]))
		root.add_child(half)
		halves[half_name] = half
	for raw: Variant in house_parts:
		var part: Dictionary = raw
		if JsonUtil.to_str(part.get("kind", "")) == DRAWN_ROOF:
			_add_drawn_roof(root, part, cells, footprint)
			continue
		var texture_path := JsonUtil.to_str(part.get("texture", ""))
		var region := JsonUtil.to_array(part.get("region", []))
		if region.size() != 4 or not ResourceLoader.exists(texture_path):
			continue
		# the part's own picture in its atlas: the pixels the tile set shows for the tile
		var own := Rect2i(JsonUtil.to_int(region[0]), JsonUtil.to_int(region[1]), JsonUtil.to_int(region[2]), JsonUtil.to_int(region[3]))
		var origin := Vector2(JsonUtil.to_float(part["origin"][0]), JsonUtil.to_float(part["origin"][1]))
		var at := part_position(part, cells, footprint)
		var cell := JsonUtil.to_array(part["cell"])
		var node_name := "%s_%d_%d" % [JsonUtil.to_str(part["kind"]).capitalize(), JsonUtil.to_int(cell[0]), JsonUtil.to_int(cell[1])]
		if JsonUtil.to_str(part.get("side", "")) != "":
			node_name += "_" + JsonUtil.to_str(part["side"])
		var size := own.size
		var cut := clampi(roundi(origin.x - at.x), 0, size.x)  # the column of the picture at the corner's x
		for half_name: String in ["left", "right"]:
			# what of the picture lies left of the corner nearest the camera is drawn with the
			# left half, the rest with the right one: a part across that line is cut in two
			var area := Rect2i(0, 0, cut, size.y) if half_name == "left" else Rect2i(cut, 0, size.x - cut, size.y)
			if area.size.x <= 0 or not _painted(texture_path, Rect2i(own.position + area.position, area.size)):
				continue
			var half: Node2D = halves[half_name]
			var sprite := Sprite2D.new()
			sprite.centered = false
			sprite.name = node_name
			sprite.texture = TextureUtil.region_texture(texture_path, Rect2i(own.position + area.position, area.size))
			var shift := Vector2(area.position)
			sprite.offset = at - origin + shift - half.position
			sprite.set_meta(&"asset_id", JsonUtil.to_str(part["asset_id"]))
			sprite.set_meta(&"kind", JsonUtil.to_str(part["kind"]))
			sprite.set_meta(&"cell", Vector2i(JsonUtil.to_int(cell[0]), JsonUtil.to_int(cell[1])))
			sprite.set_meta(&"side", JsonUtil.to_str(part.get("side", "")))
			half.add_child(sprite)
	return halves
