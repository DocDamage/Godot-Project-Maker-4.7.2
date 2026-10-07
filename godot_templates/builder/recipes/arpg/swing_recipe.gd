extends RefCounted
## The generic swing effect (T9.05): the attack effect of characters without attack animations.
## generated/effects/swing_frames.tres is a SpriteFrames with one animation, "swing". It is a pack's
## EFFECT asset named or tagged slash / swing when there is one, else 4 frames of an arc drawn in
## code into an Image (no anti-aliasing, white arc with a 1 px dark outline, tile x 1.5 in size).

const RECIPE_VERSION := 1

const Paths := preload("../../lib/paths.gd")

const OUT_PATH := "res://generated/effects/swing_frames.tres"
const ANIMATION := "swing"
const FRAME_COUNT := 4
const FPS := 20.0
const WORDS := ["slash", "swing"]
const OUTLINE := Color(0.08, 0.08, 0.12, 1.0)
## The arc is a ring segment around a point near the left edge, opening toward +x (facing right).
const SWEEP_START := -1.0471976  # -60 degrees
const SWEEP_END := 1.0471976  # 60 degrees

func _tile(ctx) -> int:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return int(def["tile_size"][0]) if not def.is_empty() else int(ctx.config.get("base_tile_size", 16))

## The pack's slash / swing EFFECT asset with animations, or {}.
func pack_effect(ctx) -> Dictionary:
	for a in ctx.catalog.assets_by_role("EFFECT"):
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var eff: Dictionary = ctx.catalog.effective(a)
		if eff.get("usage", "") != "sprite" or eff.get("animations", {}).is_empty():
			continue
		var text := String(a["id"]).to_lower() + " " + " ".join(PackedStringArray(eff.get("tags", [])))
		for word in WORDS:
			if text.contains(word):
				return a
	return {}

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([OUT_PATH])

func input_hash(ctx) -> String:
	var effect := pack_effect(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION, "tile": _tile(ctx),
		"effect": effect.get("id", ""), "sha256": effect.get("sha256", ""),
		"eff": ctx.catalog.effective(effect) if not effect.is_empty() else {},
	})

func build(ctx) -> Array:
	var issues: Array = []
	var frames: SpriteFrames = null
	var effect := pack_effect(ctx)
	if not effect.is_empty():
		frames = _from_pack(effect)
	if frames == null:
		frames = drawn_frames(_tile(ctx))
	DirAccess.make_dir_recursive_absolute(OUT_PATH.get_base_dir())
	var err := ResourceSaver.save(frames, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues

## A one-animation copy of the first animation of the pack effect's SpriteFrames.
func _from_pack(effect: Dictionary) -> SpriteFrames:
	var source := load(Paths.SPRITE_FRAMES_DIR + "%s.tres" % effect["id"]) as SpriteFrames
	if source == null:
		return null
	var names := Array(source.get_animation_names())
	names.sort()
	if names.is_empty():
		return null
	var anim: String = names[0]
	var out := SpriteFrames.new()
	out.remove_animation("default")
	out.add_animation(ANIMATION)
	out.set_animation_speed(ANIMATION, source.get_animation_speed(anim))
	out.set_animation_loop(ANIMATION, false)
	for i in source.get_frame_count(anim):
		out.add_frame(ANIMATION, source.get_frame_texture(anim, i), source.get_frame_duration(anim, i))
	return out

## 4 frames of the arc, growing from a short stroke to the full sweep.
static func drawn_frames(tile: int) -> SpriteFrames:
	var size := maxi(12, int(round(tile * 1.5)))
	var out := SpriteFrames.new()
	out.remove_animation("default")
	out.add_animation(ANIMATION)
	out.set_animation_speed(ANIMATION, FPS)
	out.set_animation_loop(ANIMATION, false)
	for k in FRAME_COUNT:
		var sweep_to := lerpf(SWEEP_START + (SWEEP_END - SWEEP_START) * 0.25, SWEEP_END, float(k) / float(FRAME_COUNT - 1))
		out.add_frame(ANIMATION, ImageTexture.create_from_image(draw_arc(size, SWEEP_START, sweep_to)))
	return out

## One arc: a ring segment (centered near the left edge, middle height) from angle `from` to `to`.
static func draw_arc(size: int, from: float, to: float) -> Image:
	var mask: Array = []
	var center := Vector2(size * 0.1, (size - 1) * 0.5)
	var radius := size * 0.62
	var thickness := maxf(2.0, size * 0.16)
	for y in size:
		var row: Array = []
		for x in size:
			var p := Vector2(x + 0.5, y + 0.5) - center
			var d := p.length()
			var angle := p.angle()
			row.append(absf(d - radius) <= thickness * 0.5 and angle >= from and angle <= to)
		mask.append(row)
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	for y in size:
		for x in size:
			if mask[y][x]:
				img.set_pixel(x, y, Color.WHITE)
				continue
			for dy in range(-1, 2):
				for dx in range(-1, 2):
					var nx := x + dx
					var ny := y + dy
					if nx >= 0 and ny >= 0 and nx < size and ny < size and mask[ny][nx]:
						img.set_pixel(x, y, OUTLINE)
	return img
