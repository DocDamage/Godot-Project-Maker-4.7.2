extends RefCounted
## The things that become object scenes: catalog SheetObjects and single-frame sprite assets.
## An entry is a Dictionary:
##   id, name, role, tags (Array), texture_path, region [x, y, w, h], origin [x, y],
##   footprint ([x, y, w, h] or []), collision ({profile, polygon?}), door ([x, y] or []), sha256,
##   open_region ([x, y, w, h] of the "open" picture of a chest strip, or [])

const SPRITE_ROLES := ["DECORATION", "BUILDING", "INTERIOR", "ITEM"]

static func _default_origin(region: Array) -> Array:
	return [int(region[2]) / 2, int(region[3]) - 1]

static func entries(ctx) -> Array:
	var out: Array = []
	for o in ctx.catalog.objects():
		if o.get("status", "") == "UNUSED" or o.get("role", "NONE") == "NONE":
			continue
		var sheet: Dictionary = ctx.catalog.asset(o["sheet"])
		if sheet.is_empty():
			continue
		var region: Array = o["region"]
		out.append({
			"id": o["id"],
			"name": o["name"],
			"role": o["role"],
			"tags": o.get("tags", []).duplicate(),
			"texture_path": "res://" + str(sheet["path"]),
			"region": region.duplicate(),
			"origin": o.get("origin", _default_origin(region)).duplicate(),
			"footprint": o.get("footprint", []).duplicate(),
			"collision": o.get("collision", {"profile": "NONE"}).duplicate(true),
			"door": o.get("door", []).duplicate(),
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
		var is_chest_strip: bool = (eff.get("tags", []) as Array).has("chest")
		if not eff.has("size") or (not anims.is_empty() and not anims.has("open") and not is_chest_strip):
			continue
		var size: Array = eff.get("frame", eff["size"])
		var region := [0, 0, int(size[0]), int(size[1])]
		var id_text := String(a["id"])
		out.append({
			"id": a["id"],
			"name": id_text.get_slice(".", id_text.get_slice_count(".") - 1),
			"role": eff["role"],
			"tags": eff.get("tags", []).duplicate(),
			"texture_path": "res://" + str(a["path"]),
			"region": region,
			"origin": eff.get("origin", _default_origin(region)).duplicate(),
			"footprint": [],
			"collision": eff.get("collision", {"profile": "NONE"}).duplicate(true),
			"door": [],
			"sha256": a.get("sha256", ""),
			"open_region": open_region(eff, region),
		})
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return String(x["id"]) < String(y["id"]))
	return out

## The second picture of a strip or sheet (frame 1 = "open"), or the last frame of an animation
## named `open`; [] for a single picture. `region` is the first frame's [x, y, w, h].
static func open_region(eff: Dictionary, region: Array) -> Array:
	var fw := int(region[2])
	var fh := int(region[3])
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
			return [int(last[0]), int(last[1]), int(last[2]), int(last[3])]
		var frames: Array = spec.get("frames", [])
		if frames.size() >= 1:
			var cell: Array = frames[frames.size() - 1]
			return [int(margin[0]) + int(cell[0]) * (fw + int(sep[0])), int(margin[1]) + int(cell[1]) * (fh + int(sep[1])), fw, fh]
		return []
	var size: Array = eff.get("size", [fw, fh])
	var cols := floori(float(int(size[0]) - int(margin[0]) + int(sep[0])) / float(fw + int(sep[0])))
	var rows := floori(float(int(size[1]) - int(margin[1]) + int(sep[1])) / float(fh + int(sep[1])))
	if cols >= 2:
		return [int(margin[0]) + fw + int(sep[0]), int(margin[1]), fw, fh]
	if rows >= 2:
		return [int(margin[0]), int(margin[1]) + fh + int(sep[1]), fw, fh]
	return []

static func find(ctx, id: String) -> Dictionary:
	for e in entries(ctx):
		if e["id"] == id:
			return e
	return {}

## Collision/footprint polygon of an entry in region pixel space (before subtracting the origin).
static func footprint_polygon(e: Dictionary, geometry: Script) -> PackedVector2Array:
	var region: Array = e["region"]
	var w := int(region[2])
	var h := int(region[3])
	var coll: Dictionary = e["collision"]
	var profile: String = coll.get("profile", "NONE")
	if profile == "CUSTOM" and coll.get("polygon", []).size() >= 3:
		return geometry.profile_polygon("CUSTOM", Vector2i(w, h), coll["polygon"])
	if ["FULL", "BOTTOM_HALF", "BOTTOM_EDGE", "TOP_EDGE", "LEFT_EDGE", "RIGHT_EDGE"].has(profile):
		return geometry.profile_polygon(profile, Vector2i(w, h))
	var fp: Array = e["footprint"]
	if fp.size() == 4:
		return geometry.rect_poly(float(fp[0]), float(fp[1]), float(fp[2]), float(fp[3]))
	var fh := maxi(1, roundi(h * 0.3))
	return geometry.rect_poly(1.0, float(h - fh), float(w - 2), float(fh))

static func footprint_area(e: Dictionary, geometry: Script) -> float:
	var pts := footprint_polygon(e, geometry)
	var area := 0.0
	for i in pts.size():
		var a := pts[i]
		var b := pts[(i + 1) % pts.size()]
		area += a.x * b.y - b.x * a.y
	return absf(area) / 2.0

## The building the demo uses: `config.starter.building`, else the first BUILDING entry, or {}.
static func starter_building(ctx) -> Dictionary:
	var starter: Dictionary = ctx.config.get("starter", {})
	var wanted := String(starter.get("building", ""))
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
static func chest_entry(ctx) -> Dictionary:
	var all := entries(ctx)
	var wanted := String(ctx.config.get("starter", {}).get("chest", ""))
	if wanted != "":
		for e in all:
			if e["id"] == wanted:
				return _with_fallback(e, not e["tags"].has("chest") and not String(e["id"]).contains("chest"))
	for e in all:
		if e["tags"].has("chest"):
			return _with_fallback(e, false)
	for e in all:
		if e["role"] == "ITEM" and String(e["id"]).contains("chest"):
			return _with_fallback(e, false)
	for e in all:
		if e["role"] == "ITEM":
			return _with_fallback(e, true)
	return {}

static func _with_fallback(e: Dictionary, fallback: bool) -> Dictionary:
	var copy: Dictionary = e.duplicate(true)
	copy["fallback"] = fallback
	return copy
