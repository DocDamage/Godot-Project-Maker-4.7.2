extends RefCounted
## The things that become object scenes: catalog SheetObjects and single-frame sprite assets.
## An entry is a Dictionary:
##   id, name, role, tags (Array), texture_path, region [x, y, w, h], origin [x, y],
##   footprint ([x, y, w, h] or []), collision ({profile, polygon?}), door ([x, y] or []), sha256,
##   open_region ([x, y, w, h] of the "open" picture of a chest strip, or [])
## An entry drawn for the isometric view (T17.14) has two more keys, and only such an entry has
## them: iso ([w, h], the diamond of its pack) and stands_on ([columns, rows], the cells it
## stands on). Its origin is the middle of the cell of those nearest the camera.

const JsonUtil := preload("json_util.gd")
const BuildContext := preload("build_context.gd")
const Geometry := preload("geometry.gd")
const IsoTileset := preload("iso_tileset.gd")

const SPRITE_ROLES := ["DECORATION", "BUILDING", "INTERIOR", "ITEM"]

static func _default_origin(region: Array) -> Array:
	return [JsonUtil.to_int(region[2]) / 2, JsonUtil.to_int(region[3]) - 1]

static func entries(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
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
		if eff.get("usage", "") != "sprite" or not SPRITE_ROLES.has(eff.get("role", "")):
			continue
		var anims: Dictionary = eff.get("animations", {})
		# An animated asset is not an object, except a chest strip (its 2 frames are read as an
		# animation by the analyzer) and anything with an `open` animation.
		var eff_tags: Array = eff.get("tags", [])
		var is_chest_strip: bool = eff_tags.has("chest")
		if not eff.has("size") or (not anims.is_empty() and not anims.has("open") and not is_chest_strip):
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
			"collision": JsonUtil.to_dict(eff.get("collision", {"profile": "NONE"})).duplicate(true),
			"door": [],
			"sha256": a.get("sha256", ""),
			"open_region": open_region(eff, region),
		})
		if JsonUtil.to_str(eff.get("projection", "")) == IsoTileset.PROJECTION and JsonUtil.to_array(eff.get("footprint", [])).size() == 2:
			var made: Dictionary = out[out.size() - 1]
			var stands := IsoTileset.stands_on(eff)
			made["iso"] = [JsonUtil.to_int(eff["footprint"][0]), JsonUtil.to_int(eff["footprint"][1])]
			made["stands_on"] = [stands.x, stands.y]
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return JsonUtil.to_str(x["id"]) < JsonUtil.to_str(y["id"]))
	return out

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
