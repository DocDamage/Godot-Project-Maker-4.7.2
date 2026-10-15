extends RefCounted
## The rock of a farm's cave (after T17.24): the packs' own rock where they have it.
##
## The cave's rock and edge were dark flat shapes, and flat diamonds on the isometric view: no
## rock of a pack was looked for. They are looked for now, in this order, and the drawn shapes
## stay under them (and alone, when nothing is found):
##
## * **Seen from above**, a cell of a picture of rock: of the tile sheets of the project and the
##   other pictures of the packs, those whose name says rock (`rock`, `boulder`; then `cave`,
##   `mine`, `cliff`; then `stone`), then the tile sheets of the role CLIFF or WALL (a fence is
##   none); of each, the cells that are opaque, tile with themselves and are no grass and no
##   water, a textured one before a flat one and a light one (the top of the rock) before a dark
##   one (the floor between). The cell is laid on every cell of rock and of the edge (`rock_cells`).
##   When no picture has such a cell, the packs' boulders (the farm's own `rock` things) stand on
##   the cells of rock instead.
## * **On diamonds**, a flat tile of the isometric tile set whose name says rock, painted on the
##   ground of every cell of rock; else the packs' isometric rock pictures, one on every cell of
##   rock, standing among the actors.

const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const BuildContext := preload("../../lib/build_context.gd")
const CatalogReader := preload("../../lib/catalog_reader.gd")
const TextureUtil := preload("../../lib/texture_util.gd")

## The version of what the cave's rock is made of, for the recipe's hash.
const VERSION := 1
## The words of a picture of rock, the surer first.
const WORD_RANKS: Array = [
	["rock", "rocks", "boulder", "boulders"],
	["cave", "caves", "mine", "mines", "cliff", "cliffs"],
	["stone", "stones"],
]
## The roles a picture of rock may have; the others (an item, a character, a crop) are none.
const ROCK_ROLES: Array[String] = ["GROUND", "WALL", "CLIFF", "DECORATION", "ROAD"]
## The most pictures that are measured (the surest first).
const MOST_PICTURES := 16
const OPAQUE := 0.9
const SEAM_RATIO := 3.0
const MAX_SPREAD := 0.35
const TEXTURED := 0.05  # a cell this uneven has the grain of rock; a flatter one is a flat colour
const LIGHT := 0.3  # the value of a cell of rock that is the top of it, not the floor between

## The words of an asset's own name (the last part of its id).
static func _words(asset_id: String) -> PackedStringArray:
	var name := asset_id.get_slice("#", 0)
	name = name.substr(name.rfind(".") + 1)
	return name.to_lower().replace("-", "_").split("_", false)

## How sure a picture is of rock by its name and role: 0 (its name says rock or boulder), 1 (a
## cave, a mine, a cliff), 2 (stone), 3 (a tile sheet of the role CLIFF or WALL that is no
## fence), -1 (none).
static func rank(asset_id: String, eff: Dictionary, in_tile_set: bool) -> int:
	var words := _words(asset_id)
	for i in WORD_RANKS.size():
		for word: String in WORD_RANKS[i]:
			if words.has(word):
				return i
	var tags: Array = eff.get("tags", [])
	if in_tile_set and JsonUtil.to_str(eff.get("role", "")) in ["CLIFF", "WALL"] and not tags.has("fence"):
		return WORD_RANKS.size()
	return -1

## The grass and the water a cell must not be: the share of its pixels of each.
static func _shares(image: Image, area: Rect2i) -> Vector2:
	var grass := 0
	var water := 0
	for y in range(area.position.y, area.end.y):
		for x in range(area.position.x, area.end.x):
			var c := image.get_pixel(x, y)
			var h := c.h * 360.0
			if c.s >= 0.2 and c.v >= 0.15 and h >= 60.0 and h <= 175.0:
				grass += 1
			elif c.s >= 0.25 and h > 175.0 and h <= 260.0:
				water += 1
	var n := maxf(1.0, float(area.size.x * area.size.y))
	return Vector2(grass / n, water / n)

## What a cell is as rock: {spread, value} or {} when it is not opaque, does not tile with itself,
## is too uneven, or is grass or water.
static func cell_facts(image: Image, area: Rect2i) -> Dictionary:
	var sum := Vector3.ZERO
	var sq := Vector3.ZERO
	var near := 0.0
	var near_n := 0
	for y in range(area.position.y, area.end.y):
		for x in range(area.position.x, area.end.x):
			var c := image.get_pixel(x, y)
			if c.a < OPAQUE:
				return {}
			var v := Vector3(c.r, c.g, c.b)
			sum += v
			sq += v * v
			if x + 1 < area.end.x:
				var r := image.get_pixel(x + 1, y)
				near += (absf(r.r - c.r) + absf(r.g - c.g) + absf(r.b - c.b)) / 3.0
				near_n += 1
			if y + 1 < area.end.y:
				var d := image.get_pixel(x, y + 1)
				near += (absf(d.r - c.r) + absf(d.g - c.g) + absf(d.b - c.b)) / 3.0
				near_n += 1
	var n := float(area.size.x * area.size.y)
	var mean := sum / n
	var variance := sq / n - mean * mean
	var spread := sqrt(maxf(variance.x, 0.0)) + sqrt(maxf(variance.y, 0.0)) + sqrt(maxf(variance.z, 0.0))
	if spread > MAX_SPREAD:
		return {}
	near = near / maxf(1.0, float(near_n))
	var seam_x := 0.0
	for y in range(area.position.y, area.end.y):
		var a := image.get_pixel(area.position.x, y)
		var b := image.get_pixel(area.end.x - 1, y)
		seam_x += (absf(a.r - b.r) + absf(a.g - b.g) + absf(a.b - b.b)) / 3.0
	var seam_y := 0.0
	for x in range(area.position.x, area.end.x):
		var a := image.get_pixel(x, area.position.y)
		var b := image.get_pixel(x, area.end.y - 1)
		seam_y += (absf(a.r - b.r) + absf(a.g - b.g) + absf(a.b - b.b)) / 3.0
	var seam := maxf(seam_x / area.size.y, seam_y / area.size.x)
	if seam > SEAM_RATIO * maxf(near, 1.0 / 255.0):
		return {}
	var shares := _shares(image, area)
	if shares.x > 0.3 or shares.y > 0.3:
		return {}
	return {"spread": spread, "value": maxf(mean.x, maxf(mean.y, mean.z))}

## How good a cell of rock is, the higher the better: a textured light cell, a light one, any.
static func score(facts: Dictionary) -> float:
	var value := JsonUtil.to_float(facts["value"])
	var spread := JsonUtil.to_float(facts["spread"])
	var group := 0.0
	if value >= LIGHT:
		group = 2.0 if spread >= TEXTURED else 1.0
	return group * 10.0 + value

## The cells of `size` px of an image laid out by `grid` (cell, margin, separation), or by
## squares of `size` from its corner.
static func cells_of(image_size: Vector2i, size: int, grid: Dictionary) -> Array[Rect2i]:
	var cell := Vector2i(size, size)
	var margin := Vector2i.ZERO
	var sep := Vector2i.ZERO
	var raw := JsonUtil.to_array(grid.get("cell", []))
	if raw.size() == 2 and JsonUtil.to_int(raw[0]) == size and JsonUtil.to_int(raw[1]) == size:
		var m := JsonUtil.to_array(grid.get("margin", [0, 0]))
		var s := JsonUtil.to_array(grid.get("separation", [0, 0]))
		margin = Vector2i(JsonUtil.to_int(m[0]), JsonUtil.to_int(m[1])) if m.size() == 2 else Vector2i.ZERO
		sep = Vector2i(JsonUtil.to_int(s[0]), JsonUtil.to_int(s[1])) if s.size() == 2 else Vector2i.ZERO
	var out: Array[Rect2i] = []
	var y := margin.y
	while y + cell.y <= image_size.y:
		var x := margin.x
		while x + cell.x <= image_size.x:
			out.append(Rect2i(Vector2i(x, y), cell))
			x += cell.x + sep.x
		y += cell.y + sep.y
	return out

## The pictures that may be rock, the surest first: [{id, path, grid, rank}].
static func candidates(ctx: BuildContext, geo: MapGeo) -> Array[Dictionary]:
	var in_set := {}
	for raw: Variant in JsonUtil.to_array(geo.def.get("sources", [])):
		in_set[JsonUtil.to_str(JsonUtil.to_dict(raw).get("asset", ""))] = true
	var out: Array[Dictionary] = []
	for asset in ctx.catalog.assets():
		var asset_id := JsonUtil.to_str(asset.get("id", ""))
		if JsonUtil.to_str(asset.get("status", "")) in ["UNUSED", "MISSING"] or JsonUtil.to_str(asset.get("kind", "image")) != "image":
			continue
		var eff := CatalogReader.effective(asset)
		if not JsonUtil.to_str(eff.get("role", "")) in ROCK_ROLES:
			continue
		var r := rank(asset_id, eff, in_set.has(asset_id))
		if r < 0 or "#" in asset_id:
			continue
		out.append({"id": asset_id, "path": "res://" + JsonUtil.to_str(asset.get("path", "")), "grid": JsonUtil.to_dict(eff.get("grid", {})), "rank": r})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ra := JsonUtil.to_int(a["rank"])
		var rb := JsonUtil.to_int(b["rank"])
		return ra < rb or (ra == rb and JsonUtil.to_str(a["id"]) < JsonUtil.to_str(b["id"])))
	return out.slice(0, MOST_PICTURES)

## The cell of rock of the packs for a cave seen from above: {texture (AtlasTexture of the
## cell), asset, region}, or {} when no picture has one. Of the pictures of the surest rank that
## has a cell, the best cell (`score`); the first picture and cell when two are as good.
static func picture_cell(ctx: BuildContext, geo: MapGeo) -> Dictionary:
	var best := {}
	var best_score := -1.0
	var best_rank := -1
	for found in candidates(ctx, geo):
		var r := JsonUtil.to_int(found["rank"])
		if best_rank >= 0 and r > best_rank:
			break
		var path := JsonUtil.to_str(found["path"])
		if not ResourceLoader.exists(path):
			continue
		var texture := load(path) as Texture2D
		var image: Image = null
		if texture != null:
			image = texture.get_image()
		if image == null:
			continue
		if image.is_compressed():
			image.decompress()
		for area in cells_of(Vector2i(image.get_width(), image.get_height()), geo.tile_px, JsonUtil.to_dict(found["grid"])):
			var facts := cell_facts(image, area)
			if facts.is_empty():
				continue
			var s := score(facts)
			if s > best_score + 0.0001:
				best_score = s
				best_rank = r
				best = {"asset": found["id"], "path": path, "region": area}
	if best.is_empty():
		return {}
	var region: Rect2i = best["region"]
	best["texture"] = TextureUtil.region_texture(JsonUtil.to_str(best["path"]), region)
	return best

## The isometric tile of rock: the first flat tile of the isometric tile set whose name says rock
## (then stone), as {source_id, coords, asset_id}, or {}.
static func iso_tile(geo: MapGeo) -> Dictionary:
	if geo.iso == null:
		return {}
	var found := ""
	var found_rank := 9
	var ids := geo.iso.tile_ids()
	ids.sort()
	for asset_id in ids:
		var eff := geo.iso.facets(asset_id)
		if JsonUtil.to_str(eff.get("role", "")) in ["ROAD", "WATER"] or eff.has("joins") or eff.has("edge"):
			continue
		var r := rank(asset_id, eff, false)
		if r >= 0 and r < found_rank:
			found = asset_id
			found_rank = r
	return geo.tile_of_asset(geo.iso.first_of(found)) if found != "" else {}

## Lays the cell of rock of the packs on every one of `cells` under `holder` (squares), or the
## isometric tile of rock on the ground of every cell (diamonds). Returns what was used: the id
## of the picture or tile, or "" when the packs have none (the drawn shapes alone).
static func lay(ctx: BuildContext, geo: MapGeo, holder: Node2D, ground: TileMapLayer, cells: Array[Vector2i]) -> String:
	if geo.isometric:
		var tile := iso_tile(geo)
		if tile.is_empty():
			return ""
		for cell in cells:
			MapUtil.put(ground, cell, tile)
		return JsonUtil.to_str(tile.get("asset_id", ""))
	var found := picture_cell(ctx, geo)
	if found.is_empty() or found["texture"] == null:
		return ""
	var texture: Texture2D = found["texture"]
	for cell in cells:
		var sprite := Sprite2D.new()
		sprite.name = "Cell_%d_%d" % [cell.x, cell.y]
		sprite.texture = texture
		sprite.centered = false
		sprite.position = Vector2(cell * geo.tile_px)
		holder.add_child(sprite)
	return JsonUtil.to_str(found["asset"])
