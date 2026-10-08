extends RefCounted
## Builds one SpriteFrames resource per sprite asset that has animations.

const RECIPE_VERSION := 2

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
	return ctx.stable_hash({"v": RECIPE_VERSION, "sprites": parts})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for a in _sprite_assets(ctx):
		_build_asset(ctx, a, issues)
	return issues

func _build_asset(ctx: BuildContext, asset: Dictionary, issues: Array) -> void:
	var eff: Dictionary = ctx.catalog.effective(asset)
	var out_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % asset["id"]
	var frame: Vector2i = ctx.vec2i(eff.get("frame", [16, 16]))
	var grid: Dictionary = eff.get("grid", {})
	var margin: Vector2i = ctx.vec2i(grid.get("margin", [0, 0]))
	var sep: Vector2i = ctx.vec2i(grid.get("separation", [0, 0]))
	var sf := SpriteFrames.new()
	if sf.has_animation("default"):
		sf.remove_animation("default")
	var anims: Dictionary = eff["animations"]
	var names: Array = anims.keys()
	names.sort()
	for anim_name: String in names:
		var spec: Dictionary = anims[anim_name]
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
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var err := ResourceSaver.save(sf, out_path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": out_path, "err": err}, out_path))
