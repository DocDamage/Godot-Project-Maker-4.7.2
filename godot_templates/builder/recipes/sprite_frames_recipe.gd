extends RefCounted
## Builds one SpriteFrames resource per sprite asset that has animations.
##
## **A character using a tool** (T18.10): a strip the catalog tags `use_anim:<tool>` and
## `of:<owner>` (`farmer_hoe_down_16x16_3frames` beside the farmer's walk, T17.10) is added to the
## owner's SpriteFrames as `<tool>_<direction>` (`hoe_down`, `water_left`), which the farm's tools
## play (RpgFarmTool.animation). In a game of another kind the player's strip is its
## `attack_<direction>` when it has no attack. The hash has the key `use_strips` only when the
## packs have such strips, so a pack without them builds the frames it built.

const RECIPE_VERSION := 2
const USE_ANIM_TAG := "use_anim:"
const USE_ANIM_OF_TAG := "of:"
## The directions an animation's name may end with, the diagonals first.
const DIRECTIONS: Array[String] = ["down_left", "down_right", "up_left", "up_right", "down", "left", "right", "up"]

const Paths := preload("../lib/paths.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

func _sprite_assets(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for a in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(a)
		var animations: Dictionary = eff.get("animations", {})
		if eff.get("usage", "") == "sprite" and not animations.is_empty():
			out.append(a)
	return out

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for a in _sprite_assets(ctx):
		out.append(Paths.SPRITE_FRAMES_DIR + "%s.tres" % a["id"])
	return out

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for a in _sprite_assets(ctx):
		parts.append({"id": a["id"], "sha256": a.get("sha256", ""), "eff": ctx.catalog.effective(a)})
	var hashed := {"v": RECIPE_VERSION, "sprites": parts}
	var uses := use_strips(ctx)
	if not uses.is_empty():  # only packs with a character using a tool have the key (T18.10)
		var ids := {}
		for owner_id: Variant in uses:
			var rows: Array = uses[owner_id]
			ids[owner_id] = rows.map(func(row: Array) -> String: return "%s:%s" % [row[0], JsonUtil.to_dict(row[1]).get("id", "")])
		hashed["use_strips"] = {"strips": ids, "farm": _farm(ctx)}
	return ctx.stable_hash(hashed)

static func _farm(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ctx.config.get("archetype", "")) == "farm"

## {owner id: [[tool, strip asset], ...]} of the strips of a character using a tool (the tags
## `use_anim:<tool>` and `of:<owner>`), each list by the strip's id.
func use_strips(ctx: BuildContext) -> Dictionary:
	var out := {}
	for a in _sprite_assets(ctx):
		var eff: Dictionary = ctx.catalog.effective(a)
		var tool := ""
		var owner_id := ""
		for tag: Variant in eff.get("tags", []):
			var text := JsonUtil.to_str(tag)
			if text.begins_with(USE_ANIM_TAG):
				tool = text.substr(USE_ANIM_TAG.length())
			elif text.begins_with(USE_ANIM_OF_TAG):
				owner_id = text.substr(USE_ANIM_OF_TAG.length())
		if tool == "" or owner_id == "":
			continue
		if not out.has(owner_id):
			out[owner_id] = []
		var rows: Array = out[owner_id]
		rows.append([tool, a])
	for owner_id: Variant in out:
		var rows: Array = out[owner_id]
		rows.sort_custom(func(x: Array, y: Array) -> bool: return str(JsonUtil.to_dict(x[1]).get("id", "")) < str(JsonUtil.to_dict(y[1]).get("id", "")))
	return out

## The direction an animation's name ends with (`idle_down` -> down), else down.
static func direction_of(anim_name: String) -> String:
	for dir in DIRECTIONS:
		if anim_name == dir or anim_name.ends_with("_" + dir):
			return dir
	return "down"

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var uses := use_strips(ctx)
	for a in _sprite_assets(ctx):
		var strips: Array = uses.get(a["id"], [])
		_build_asset(ctx, a, issues, strips)
	return issues

func _build_asset(ctx: BuildContext, asset: Dictionary, issues: Array, strips: Array = []) -> void:
	var eff: Dictionary = ctx.catalog.effective(asset)
	var out_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % asset["id"]
	var frame: Vector2i = ctx.vec2i(eff.get("frame", [16, 16]))
	var sf := SpriteFrames.new()
	if sf.has_animation("default"):
		sf.remove_animation("default")
	_add_animations(ctx, sf, asset, {}, frame, issues, out_path)
	# the strips of this character using a tool (T18.10)
	var attack := not _farm(ctx) and JsonUtil.to_str(eff.get("role", "")) == "PLAYER" and not Array(sf.get_animation_names()).any(func(n: String) -> bool: return n.begins_with("attack"))
	for row: Array in strips:
		if not _farm(ctx) and not attack:
			break
		var strip := JsonUtil.to_dict(row[1])
		var renamed := {}
		var strip_anims: Dictionary = ctx.catalog.effective(strip).get("animations", {})
		for anim_name: Variant in strip_anims:
			var wanted := "%s_%s" % ["attack" if not _farm(ctx) else JsonUtil.to_str(row[0]), direction_of(str(anim_name))]
			if not sf.has_animation(wanted):
				renamed[anim_name] = wanted
		_add_animations(ctx, sf, strip, renamed, frame, issues, out_path)
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var err := ResourceSaver.save(sf, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))

## Adds the animations of `asset` to `sf`: all of them under their own names when `renamed` is
## empty, else those it names under its names. A frame smaller than `owner_frame` (a strip of
## a tool beside a larger walk) is padded to it, standing on the same feet.
func _add_animations(ctx: BuildContext, sf: SpriteFrames, asset: Dictionary, renamed: Dictionary, owner_frame: Vector2i, issues: Array, out_path: String) -> void:
	var eff: Dictionary = ctx.catalog.effective(asset)
	var frame: Vector2i = ctx.vec2i(eff.get("frame", [16, 16]))
	var grid: Dictionary = eff.get("grid", {})
	var margin: Vector2i = ctx.vec2i(grid.get("margin", [0, 0]))
	var sep: Vector2i = ctx.vec2i(grid.get("separation", [0, 0]))
	var pad := Vector2i(maxi(0, owner_frame.x - frame.x), maxi(0, owner_frame.y - frame.y)) if not renamed.is_empty() else Vector2i.ZERO
	var anims: Dictionary = eff["animations"]
	var names: Array = anims.keys()
	names.sort()
	for source_name: String in names:
		if not renamed.is_empty() and not renamed.has(source_name):
			continue
		var anim_name: String = renamed.get(source_name, source_name)
		var spec: Dictionary = anims[source_name]
		var frames: Array = spec.get("frames", [])
		var rects: Array = spec.get("rects", [])
		var offsets: Array = spec.get("offsets", [])
		var frame_count: int = rects.size() if not rects.is_empty() else frames.size()
		if frame_count == 0:
			issues.append(ctx.make_issue("ANIM-001", {"anim": anim_name, "asset": asset["id"]}, out_path))
			continue
		var tex_path: String = "res://" + str(spec.get("source", asset["path"]))
		var tex := load(tex_path) as Texture2D
		if tex == null:
			issues.append(ctx.make_issue("VAL-002", {"file": tex_path}, tex_path))
			continue
		sf.add_animation(anim_name)
		sf.set_animation_speed(anim_name, JsonUtil.to_float(spec.get("fps", 8.0)))
		sf.set_animation_loop(anim_name, JsonUtil.to_bool(spec.get("loop", true)))
		var durations: Array = spec.get("durations", [])
		for i in frame_count:
			var at := AtlasTexture.new()
			at.atlas = tex
			if not rects.is_empty():
				# Explicit rects (non-grid sheets). Offsets restore the trimmed margin so frames
				# keep their untrimmed size and stay aligned.
				var r: Array = rects[i]
				at.region = Rect2(JsonUtil.to_float(r[0]), JsonUtil.to_float(r[1]), JsonUtil.to_float(r[2]), JsonUtil.to_float(r[3]))
				if i < offsets.size():
					var o: Array = offsets[i]
					at.margin = Rect2(JsonUtil.to_float(o[0]), JsonUtil.to_float(o[1]), JsonUtil.to_float(frame.x - JsonUtil.to_int(r[2])), JsonUtil.to_float(frame.y - JsonUtil.to_int(r[3])))
			else:
				var col := JsonUtil.to_int(frames[i][0])
				var row := JsonUtil.to_int(frames[i][1])
				at.region = Rect2(Vector2(margin) + Vector2(col, row) * Vector2(frame + sep), Vector2(frame))
				if pad != Vector2i.ZERO:  # centred over the feet of the owner's frame
					at.margin = Rect2(float(pad.x / 2), float(pad.y), float(pad.x), float(pad.y))
			var duration := JsonUtil.to_float(durations[i]) if i < durations.size() else 1.0
			sf.add_frame(anim_name, at, duration)
		if spec.get("flip_h", false):
			sf.set_meta("flip_h_" + anim_name, true)
		if spec.has("active_frames"):
			# Frame indices in which an attack hitbox is live (the action RPG reads them).
			var active := PackedInt32Array()
			var active_list: Array = spec["active_frames"]
			for index: Variant in active_list:
				active.append(JsonUtil.to_int(index))
			sf.set_meta("active_frames_" + anim_name, active)
