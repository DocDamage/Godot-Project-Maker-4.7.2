extends RefCounted
## The parallax background of a room: one Parallax2D per BACKGROUND asset tagged `parallax:<n>`
## (T14.02), the farthest (1) first. Not a recipe of its own: the rooms recipe asks it for the
## "Background" node of every room it builds.
##
## A layer scrolls at `factor(depth)` of the camera's speed (the far wall hardly moves, the near
## rubble almost with the room), repeats sideways, and is scaled by a whole number so that it is
## at least as tall as the view.

const JsonUtil := preload("../../lib/json_util.gd")
const TextureUtil := preload("../../lib/texture_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const TAG := "parallax:"
const SET_TAG := "parallax_set:"
const NODE_NAME := "Background"
## How fast a layer scrolls: depth 1, 2, 3, then nearer ones.
const FACTORS: Array[float] = [0.15, 0.4, 0.7, 0.85]

static func factor(depth: int) -> float:
	return FACTORS[clampi(depth - 1, 0, FACTORS.size() - 1)]

## The depth of an asset's `parallax:<n>` tag, or 0.
static func depth_of(eff: Dictionary) -> int:
	for tag: Variant in JsonUtil.to_array(eff.get("tags", [])):
		var text := JsonUtil.to_str(tag)
		if text.begins_with(TAG) and text.trim_prefix(TAG).is_valid_int():
			return text.trim_prefix(TAG).to_int()
	return 0

## The parallax set an asset's `parallax_set:<folder>` tag names (T17.32), or "".
static func set_of(eff: Dictionary) -> String:
	for tag: Variant in JsonUtil.to_array(eff.get("tags", [])):
		var text := JsonUtil.to_str(tag)
		if text.begins_with(SET_TAG):
			return text.trim_prefix(SET_TAG)
	return ""

## The background layers of the project: [{asset, depth, path}], the farthest first. Layers of a
## parallax set (T17.32: a folder of a pack's background layers) are one scene: of several sets,
## the one whose folder lies nearest the ground's sheet is used (the most folders in common, in
## the ground's pack first; else the first by name). Layers of no set are used as they were.
static func layers(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var by_set := {}
	for a in ctx.catalog.assets_by_role("BACKGROUND"):
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var eff := ctx.catalog.effective(a)
		var depth := depth_of(eff)
		if depth <= 0:
			continue
		var entry := {"asset": a["id"], "depth": depth, "path": "res://" + JsonUtil.to_str(a["path"])}
		var set_name := set_of(eff)
		if set_name == "":
			out.append(entry)
			continue
		var key := JsonUtil.to_str(a.get("pack_id", "")) + "/" + set_name
		if not by_set.has(key):
			by_set[key] = []
		(by_set[key] as Array).append(entry)
	if not by_set.is_empty():
		var chosen := _nearest_set(ctx, by_set.keys())
		for entry: Variant in by_set[chosen]:
			out.append(JsonUtil.to_dict(entry))
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool:
		return JsonUtil.to_int(x["depth"]) < JsonUtil.to_int(y["depth"]) or (x["depth"] == y["depth"] and JsonUtil.to_str(x["asset"]) < JsonUtil.to_str(y["asset"])))
	return out

## Of the sets `keys` ("<pack>/<folder>"), the one nearest the ground's sheet.
static func _nearest_set(ctx: BuildContext, keys: Array) -> String:
	var sorted_keys: Array = keys.duplicate()
	sorted_keys.sort()
	var ground_id := JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	var ground := ctx.catalog.asset(ground_id) if ground_id != "" else {}
	if ground.is_empty():
		return JsonUtil.to_str(sorted_keys[0])
	var pack := JsonUtil.to_str(ground.get("pack_id", ""))
	var parts := JsonUtil.to_str(ground.get("path", "")).split("/")
	var best := JsonUtil.to_str(sorted_keys[0])
	var best_score := -1
	for key: Variant in sorted_keys:
		var text := JsonUtil.to_str(key)
		var set_pack := text.get_slice("/", 0)
		var folder := text.substr(set_pack.length() + 1).split("/")
		var score := 1000 if set_pack == pack else 0
		# the ground's path is assets/packs/<pack>/<folders>/<file>
		var i := 0
		while i < folder.size() and i + 3 < parts.size() and folder[i] == parts[i + 3]:
			i += 1
		score += i
		if score > best_score:
			best = text
			best_score = score
	return best

## The "Background" node of a room `room_px` large for a view of `view` px, or null when the
## packs have no parallax layer.
static func build(ctx: BuildContext, room_px: Vector2, view: Vector2) -> Node2D:
	var found := layers(ctx)
	if found.is_empty():
		return null
	var holder := Node2D.new()
	holder.name = NODE_NAME
	holder.z_index = -20
	for entry in found:
		var texture := load(JsonUtil.to_str(entry["path"])) as Texture2D
		if texture == null:
			continue
		var depth := JsonUtil.to_int(entry["depth"])
		var size := texture.get_size()
		var zoom := maxf(1.0, ceilf(view.y / maxf(1.0, size.y)))
		var layer := Parallax2D.new()
		layer.name = "Layer%d" % depth if holder.get_node_or_null("Layer%d" % depth) == null else "Layer%d_%d" % [depth, holder.get_child_count()]
		layer.scroll_scale = Vector2(factor(depth), 1.0)
		layer.repeat_size = Vector2(size.x * zoom, 0.0)
		layer.repeat_times = maxi(3, ceili(room_px.x / maxf(1.0, size.x * zoom)) + 2)
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = texture
		sprite.centered = false
		sprite.scale = Vector2(zoom, zoom)
		sprite.position = Vector2(0.0, room_px.y - size.y * zoom)  # stands on the bottom of the room
		layer.add_child(sprite)
		holder.add_child(layer)
	return holder
