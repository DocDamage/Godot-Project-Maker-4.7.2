extends RefCounted
## The things that become object scenes: catalog SheetObjects and single-frame sprite assets.
## An entry is a Dictionary:
##   id, name, role, tags (Array), texture_path, region [x, y, w, h], origin [x, y],
##   footprint ([x, y, w, h] or []), collision ({profile, polygon?}), door ([x, y] or []), sha256,
##   open_region ([x, y, w, h] of the "open" picture of a chest strip, or [])
## An entry drawn for the isometric view (T17.14) has two more keys, and only such an entry has
## them: iso ([w, h], the diamond of its pack) and stands_on ([columns, rows], the cells it
## stands on). Its origin is the middle of the cell of those nearest the camera.
## An entry of a thing that moves (an assets-only project, 2026-10-26: a fountain, a campfire, a
## lantern, an arrow, an impact) has `frames_path` (its SpriteFrames) and `animation` (the one it
## plays), and only such an entry has them; one whose pack draws its shadow has `shadow`.

const JsonUtil := preload("json_util.gd")
const BuildContext := preload("build_context.gd")
const Geometry := preload("geometry.gd")
const IsoTileset := preload("iso_tileset.gd")
const IsoHouse := preload("iso_house.gd")

const SPRITE_ROLES := ["DECORATION", "BUILDING", "INTERIOR", "ITEM"]
## What else the dock places in an assets-only project: what flies and what bursts (2026-10-26).
const ASSETS_ONLY_ROLES := ["PROJECTILE", "EFFECT"]
const SPRITE_FRAMES_DIR := "res://generated/sprite_frames/"
## The pieces of a stack that are painted on a height layer and never placed alone: what hangs on
## a storey's face or a wall, and what lies over another tile (2026-10-26). A thing for a roof is
## placed, and stands on the roof under it (the dock's placement).
const PAINTED_ONLY := ["on_storey", "on_wall", "overlay"]

## The tags of a thing cut from a sheet that the farm and the maps know what to do with.
const NAMED_THINGS := ["tree", "bush", "rock", "flowers", "grass", "stump", "fence", "well"]

## A thing cut from a sheet that is an entry too (T17.33): a building, or a tree, a bush, a
## rock, flowers, grass, a stump, a fence or a well by its tags.
static func _named_thing(eff: Dictionary) -> bool:
	if JsonUtil.to_str(eff.get("role", "")) == "BUILDING":
		return true
	for tag: Variant in JsonUtil.to_array(eff.get("tags", [])):
		if NAMED_THINGS.has(JsonUtil.to_str(tag)):
			return true
	return false

## The collision of a thing cut from a sheet that says none: the lowest quarter of its picture,
## half as wide, where it stands (T17.33).
const NO_COLLISION := {"profile": "NONE"}

static func _foot(region: Array) -> Dictionary:
	var w := JsonUtil.to_int(region[2])
	var h := JsonUtil.to_int(region[3])
	var fw := maxi(2, w / 2)
	var fh := maxi(2, h / 4)
	var fx := (w - fw) / 2
	var fy := h - fh
	return {"profile": "CUSTOM", "polygon": [[fx, fy], [fx + fw, fy], [fx + fw, h], [fx, h]]}

static func _default_origin(region: Array) -> Array:
	return [JsonUtil.to_int(region[2]) / 2, JsonUtil.to_int(region[3]) - 1]

static func entries(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var assets_only := JsonUtil.to_str(ctx.config.get("archetype", "")) == "assets"
	for o in ctx.catalog.objects():
		if o.get("status", "") == "UNUSED" or o.get("role", "NONE") == "NONE":
			continue
		var sheet_id: String = o["sheet"]
		var sheet: Dictionary = ctx.catalog.asset(sheet_id)
		if sheet.is_empty():
			continue
		var region: Array = o["region"]
		out.append({
			"id": o["id"],
			"name": o["name"],
			"role": o["role"],
			"tags": JsonUtil.to_array(o.get("tags", [])).duplicate(),
			"texture_path": "res://" + str(sheet["path"]),
			"region": region.duplicate(),
			"origin": JsonUtil.to_array(o.get("origin", _default_origin(region))).duplicate(),
			"footprint": JsonUtil.to_array(o.get("footprint", [])).duplicate(),
			"collision": JsonUtil.to_dict(o.get("collision", {"profile": "NONE"})).duplicate(true),
			"door": JsonUtil.to_array(o.get("door", [])).duplicate(),
			"sha256": sheet.get("sha256", ""),
			"open_region": [],
		})
	for a in ctx.catalog.assets():
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var eff: Dictionary = ctx.catalog.effective(a)
		# a thing cut from a sheet (usage `object`, its own picture) is one too (T17.33): a named
		# one in a game, every one in an assets-only project, where the levels are made by hand
		var usage := JsonUtil.to_str(eff.get("usage", ""))
		var cut: bool = usage == "object" and (_named_thing(eff) or assets_only)
		# an isometric piece of a thing (a crate, a statue, a house: a role the dock places, not
		# ground or wall) is placed from the dock in an assets-only project as well as painted
		# (T17.33); the cut cells of a sheet have no rise to tell them by
		var standing: bool = assets_only and usage == "iso_tile" and not PAINTED_ONLY.has(JsonUtil.to_str(eff.get("stack", "")))
		var role := JsonUtil.to_str(eff.get("role", ""))
		var placed_role := SPRITE_ROLES.has(role) or (assets_only and ASSETS_ONLY_ROLES.has(role))
		if not placed_role or not (usage == "sprite" or cut or standing):
			continue
		var anims: Dictionary = eff.get("animations", {})
		# An animated asset is not an object in a game, except a chest strip (its 2 frames are
		# read as an animation by the analyzer) and anything with an `open` animation; in an
		# assets-only project it is one that plays (2026-10-26).
		var eff_tags: Array = eff.get("tags", [])
		var is_chest_strip: bool = eff_tags.has("chest")
		var plays: bool = assets_only and not anims.is_empty() and not anims.has("open") and not is_chest_strip and usage == "sprite"
		if not eff.has("size") or (not anims.is_empty() and not anims.has("open") and not is_chest_strip and not plays):
			continue
		var size: Array = eff.get("frame", eff["size"])
		var region := [0, 0, JsonUtil.to_int(size[0]), JsonUtil.to_int(size[1])]
		var id_text := JsonUtil.to_str(a["id"])
		out.append({
			"id": a["id"],
			"name": id_text.get_slice(".", id_text.get_slice_count(".") - 1),
			"role": eff["role"],
			"tags": eff_tags.duplicate(),
			"texture_path": "res://" + str(a["path"]),
			"region": region,
			"origin": JsonUtil.to_array(eff.get("origin", _default_origin(region))).duplicate(),
			"footprint": [],
			"collision": JsonUtil.to_dict(eff.get("collision", _foot(region) if cut else NO_COLLISION)).duplicate(true),
			"door": [],
			"sha256": a.get("sha256", ""),
			"open_region": open_region(eff, region),
		})
		if plays:
			var made_plays: Dictionary = out[out.size() - 1]
			made_plays["frames_path"] = SPRITE_FRAMES_DIR + "%s.tres" % a["id"]
			made_plays["animation"] = "idle_down" if anims.has("idle_down") else JsonUtil.to_str(_sorted_keys(anims)[0])
		if eff.has("shadow"):
			out[out.size() - 1]["shadow"] = JsonUtil.to_str(eff["shadow"])
		if JsonUtil.to_str(eff.get("projection", "")) == IsoTileset.PROJECTION and JsonUtil.to_array(eff.get("footprint", [])).size() == 2:
			var made: Dictionary = out[out.size() - 1]
			var stands := IsoTileset.stands_on(eff)
			made["iso"] = [JsonUtil.to_int(eff["footprint"][0]), JsonUtil.to_int(eff["footprint"][1])]
			made["stands_on"] = [stands.x, stands.y]
	var house := kit_house(ctx, out)
	if not house.is_empty():
		out.append(house)
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return JsonUtil.to_str(x["id"]) < JsonUtil.to_str(y["id"]))
	return out

static func _sorted_keys(d: Dictionary) -> Array:
	var keys := d.keys()
	keys.sort()
	return keys

## The house of pieces of an isometric project (T17.22, IsoHouse): the entry of a building that
## is put together from the packs' wall, door and roof tiles, when the project is isometric,
## its packs drew no whole building for that view (`found`: one that did is placed as it
## always was) and they have the pieces. {} otherwise, which is every project seen from above
## and every isometric pack with a house or without walls along a side. Such an entry has two
## more keys, and only it has them: `kit` (the sets it is made of) and `parts`.
static func kit_house(ctx: BuildContext, found: Array[Dictionary]) -> Dictionary:
	if not IsoTileset.project_wanted(ctx.config):
		return {}
	for e in found:
		if e["role"] == "BUILDING" and is_iso(e):
			return {}
	var iso := IsoTileset.new(ctx.catalog)
	if not iso.has_tiles():
		return {}
	return IsoHouse.entry(iso, JsonUtil.to_int(ctx.config.get("seed", 12345)))

## The second picture of a strip or sheet (frame 1 = "open"), or the last frame of an animation
## named `open`; [] for a single picture. `region` is the first frame's [x, y, w, h].
static func open_region(eff: Dictionary, region: Array) -> Array:
	var fw := JsonUtil.to_int(region[2])
	var fh := JsonUtil.to_int(region[3])
	if fw <= 0 or fh <= 0:
		return []
	var grid: Dictionary = eff.get("grid", {})
	var margin: Array = grid.get("margin", [0, 0])
	var sep: Array = grid.get("separation", [0, 0])
	var anims: Dictionary = eff.get("animations", {})
	if anims.has("open"):
		var spec: Dictionary = anims["open"]
		var rects: Array = spec.get("rects", [])
		if not rects.is_empty():
			var last: Array = rects[rects.size() - 1]
			return [JsonUtil.to_int(last[0]), JsonUtil.to_int(last[1]), JsonUtil.to_int(last[2]), JsonUtil.to_int(last[3])]
		var frames: Array = spec.get("frames", [])
		if frames.size() >= 1:
			var cell: Array = frames[frames.size() - 1]
			return [JsonUtil.to_int(margin[0]) + JsonUtil.to_int(cell[0]) * (fw + JsonUtil.to_int(sep[0])), JsonUtil.to_int(margin[1]) + JsonUtil.to_int(cell[1]) * (fh + JsonUtil.to_int(sep[1])), fw, fh]
		return []
	var size: Array = eff.get("size", [fw, fh])
	var cols := floori(float(JsonUtil.to_int(size[0]) - JsonUtil.to_int(margin[0]) + JsonUtil.to_int(sep[0])) / float(fw + JsonUtil.to_int(sep[0])))
	var rows := floori(float(JsonUtil.to_int(size[1]) - JsonUtil.to_int(margin[1]) + JsonUtil.to_int(sep[1])) / float(fh + JsonUtil.to_int(sep[1])))
	if cols >= 2:
		return [JsonUtil.to_int(margin[0]) + fw + JsonUtil.to_int(sep[0]), JsonUtil.to_int(margin[1]), fw, fh]
	if rows >= 2:
		return [JsonUtil.to_int(margin[0]), JsonUtil.to_int(margin[1]) + fh + JsonUtil.to_int(sep[1]), fw, fh]
	return []

static func find(ctx: BuildContext, id: String) -> Dictionary:
	for e in entries(ctx):
		if e["id"] == id:
			return e
	return {}

## Collision/footprint polygon of an entry in region pixel space (before subtracting the origin).
static func footprint_polygon(e: Dictionary) -> PackedVector2Array:
	var region: Array = e["region"]
	var w := JsonUtil.to_int(region[2])
	var h := JsonUtil.to_int(region[3])
	var coll: Dictionary = e["collision"]
	var profile: String = coll.get("profile", "NONE")
	var polygon: Array = coll.get("polygon", [])
	if profile == "CUSTOM" and polygon.size() >= 3:
		return Geometry.profile_polygon("CUSTOM", Vector2i(w, h), polygon)
	if is_iso(e):
		# what stands on diamonds blocks its diamonds: the outline of its cells around its origin
		var around := Vector2(JsonUtil.to_float(e["origin"][0]), JsonUtil.to_float(e["origin"][1]))
		var outline := PackedVector2Array()
		for corner in IsoTileset.outline(iso_cells(e), iso_footprint(e)):
			outline.append(corner + around)
		return outline
	if ["FULL", "BOTTOM_HALF", "BOTTOM_EDGE", "TOP_EDGE", "LEFT_EDGE", "RIGHT_EDGE"].has(profile):
		return Geometry.profile_polygon(profile, Vector2i(w, h))
	var fp: Array = e["footprint"]
	if fp.size() == 4:
		return Geometry.rect_poly(JsonUtil.to_float(fp[0]), JsonUtil.to_float(fp[1]), JsonUtil.to_float(fp[2]), JsonUtil.to_float(fp[3]))
	var fh := maxi(1, roundi(h * 0.3))
	return Geometry.rect_poly(1.0, float(h - fh), float(w - 2), float(fh))

## True for an entry that was drawn for the isometric view.
static func is_iso(e: Dictionary) -> bool:
	return JsonUtil.to_array(e.get("iso", [])).size() == 2

## The diamond of an isometric entry's pack.
static func iso_footprint(e: Dictionary) -> Vector2i:
	var pair := JsonUtil.to_array(e.get("iso", []))
	return Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])) if pair.size() == 2 else Vector2i.ZERO

## The cells an isometric entry stands on, [columns, rows].
static func iso_cells(e: Dictionary) -> Vector2i:
	var pair := JsonUtil.to_array(e.get("stands_on", []))
	if pair.size() != 2:
		return Vector2i.ONE
	return Vector2i(maxi(1, JsonUtil.to_int(pair[0])), maxi(1, JsonUtil.to_int(pair[1])))

static func footprint_area(e: Dictionary) -> float:
	var pts := footprint_polygon(e)
	var area := 0.0
	for i in pts.size():
		var a := pts[i]
		var b := pts[(i + 1) % pts.size()]
		area += a.x * b.y - b.x * a.y
	return absf(area) / 2.0

## The building the demo uses: `config.starter.building`, else the first BUILDING entry, or {}.
static func starter_building(ctx: BuildContext) -> Dictionary:
	var starter: Dictionary = ctx.config.get("starter", {})
	var wanted := JsonUtil.to_str(starter.get("building", ""))
	var all := entries(ctx)
	if wanted != "":
		for e in all:
			if e["id"] == wanted:
				return e
	for e in all:
		if e["role"] == "BUILDING":
			return e
	return {}

## The entry that becomes the demo chest: `config.starter.chest`, else an entry tagged `chest`,
## else an ITEM entry (named chest first). The result carries `fallback: true` when it is only an
## item icon standing in for a chest. {} when there is nothing to use.
static func chest_entry(ctx: BuildContext) -> Dictionary:
	var all := entries(ctx)
	var wanted := JsonUtil.to_str(ctx.section("starter").get("chest", ""))
	if wanted != "":
		for e in all:
			if e["id"] == wanted:
				var tags: Array = e["tags"]
				return _with_fallback(e, not tags.has("chest") and not JsonUtil.to_str(e["id"]).contains("chest"))
	for e in all:
		var tags: Array = e["tags"]
		if tags.has("chest"):
			return _with_fallback(e, false)
	for e in all:
		if e["role"] == "ITEM" and JsonUtil.to_str(e["id"]).contains("chest"):
			return _with_fallback(e, false)
	for e in all:
		if e["role"] == "ITEM":
			return _with_fallback(e, true)
	return {}

static func _with_fallback(e: Dictionary, fallback: bool) -> Dictionary:
	var copy: Dictionary = e.duplicate(true)
	copy["fallback"] = fallback
	return copy
