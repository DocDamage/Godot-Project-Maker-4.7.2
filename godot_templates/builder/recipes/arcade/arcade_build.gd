extends RefCounted
## Node-building helpers of the arcade recipes, shared by the three arcade kinds (the shoot-em-up,
## the run and gun, the racing game): where the framework's scripts are, where a stage's scene
## goes, the combat mode's scene and a drawn stand-in for a thing that has no art.

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const Paths := preload("../../lib/paths.gd")
const TextureUtil := preload("../../lib/texture_util.gd")

const DIR := "res://addons/rpg_runtime/archetypes/arcade/"
const STAGE_SCRIPT := DIR + "stage.gd"
const SCROLLER_SCRIPT := DIR + "scroller.gd"
const BOSS_SCRIPT := DIR + "boss_base.gd"
const MODE_SCRIPT := DIR + "arcade_mode.gd"
const HUD_SCRIPT := DIR + "ui/arcade_hud.gd"
const POOL_SCRIPT := DIR + "bullet_pool.gd"
const EXPLOSION_SCRIPT := DIR + "explosion.gd"
const SPAWN_SCRIPT := "res://addons/rpg_runtime/world/spawn_point.gd"

const STAGES_PATH := "res://game/data/stages.json"
## The stages of the plan as rpggen made them, written on every build (see StageRecipes.save_list).
const PLANNED_STAGES_PATH := "res://generated/data/stages.json"
const STAGES_DIR := "res://generated/scenes/stages/"
const MODE_PATH := "res://generated/scenes/combat/combat_mode.tscn"

## The scene of the stage `index` (0 is the first): stage_01.tscn, stage_02.tscn, ...
static func stage_path(index: int) -> String:
	return STAGES_DIR + "stage_%02d.tscn" % (index + 1)

## The id of the stage `index` as a map: "stage_01".
static func stage_id(index: int) -> String:
	return "stage_%02d" % (index + 1)

## A rectangle of one colour, `size` px, its middle on the origin: what stands in for an enemy or
## a boss that has no picture.
static func stand_in(node_name: String, size: Vector2, color: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	var half := size * 0.5
	shape.polygon = PackedVector2Array([Vector2(-half.x, -half.y), Vector2(half.x, -half.y), Vector2(half.x, half.y), Vector2(-half.x, half.y)])
	shape.color = color
	return shape

## The combat mode's scene: a node "Combat" with `script_path` (the mode of the kind, which
## extends RpgArcadeMode; the framework's own by default) and the exported `properties` of the
## kind. Returns the issues.
static func save_mode(ctx: BuildContext, script_path: String = MODE_SCRIPT, properties: Dictionary = {}) -> Array:
	var issues: Array = []
	var root := Node.new()
	root.name = "Combat"
	if not SceneUtil.attach_script(root, script_path):
		issues.append(ctx.make_issue("VAL-002", {"file": script_path}, script_path))
	root.set("stages_path", STAGES_PATH)
	root.set("planned_stages_path", PLANNED_STAGES_PATH)
	for key: Variant in properties:
		root.set(JsonUtil.to_str(key), properties[key])
	var err := SceneUtil.save_scene(root, MODE_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": MODE_PATH, "err": err}, MODE_PATH))
	return issues

# ---------------------------------------------------------------- the options of the project

## One of the kind's options (config.starter_map), or `fallback`.
static func option(ctx: BuildContext, key: String, fallback: Variant) -> Variant:
	return ctx.section("starter_map").get(key, fallback)

## The size of the screen in px (config.resolution).
static func view(ctx: BuildContext) -> Vector2i:
	var raw := JsonUtil.to_array(ctx.config.get("resolution", [640, 360]))
	if raw.size() < 2:
		return Vector2i(640, 360)
	return Vector2i(JsonUtil.to_int(raw[0]), JsonUtil.to_int(raw[1]))

static func tile(ctx: BuildContext) -> int:
	return maxi(8, JsonUtil.to_int(ctx.config.get("base_tile_size", 16)))

# ---------------------------------------------------------------- the pictures of the packs

## The assets of `role` that are in use, by id.
static func assets(ctx: BuildContext, role: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for a in ctx.catalog.assets_by_role(role):
		if not (a.get("status", "") in ["UNUSED", "MISSING"]):
			out.append(a)
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return JsonUtil.to_str(x["id"]) < JsonUtil.to_str(y["id"]))
	return out

## The asset of `role` the game uses: the one chosen on the Mapping page (config.starter[key]),
## else the first of the packs; {} when there is none.
static func chosen(ctx: BuildContext, role: String, key: String) -> Dictionary:
	var found := assets(ctx, role)
	var wanted := JsonUtil.to_str(ctx.section("starter").get(key, ""))
	for a in found:
		if JsonUtil.to_str(a["id"]) == wanted:
			return a
	return found[0] if not found.is_empty() else {}

## The size of one frame of a sprite asset (its whole picture when it has no frame).
static func frame_size(ctx: BuildContext, asset: Dictionary) -> Vector2i:
	var eff: Dictionary = ctx.catalog.effective(asset)
	var raw := JsonUtil.to_array(eff.get("frame", eff.get("size", [16, 16])))
	if raw.size() < 2:
		return Vector2i(16, 16)
	return Vector2i(JsonUtil.to_int(raw[0]), JsonUtil.to_int(raw[1]))

## The first frame of an asset as a texture (the whole picture when it is one frame).
static func first_frame(ctx: BuildContext, asset: Dictionary) -> Texture2D:
	if asset.is_empty():
		return null
	var path := "res://" + JsonUtil.to_str(asset.get("path", ""))
	if not ResourceLoader.exists(path):
		return null
	var whole := load(path) as Texture2D
	if whole == null:
		return null
	var frame := frame_size(ctx, asset)
	if frame.x >= whole.get_width() and frame.y >= whole.get_height():
		return whole
	return TextureUtil.region_texture(path, Rect2i(Vector2i.ZERO, frame))

## The SpriteFrames of a sprite asset: the ones the sprite-frames recipe made, else one
## animation `idle` of its first frame.
static func frames_of(ctx: BuildContext, asset: Dictionary) -> SpriteFrames:
	if asset.is_empty():
		return null
	var made := Paths.SPRITE_FRAMES_DIR + "%s.tres" % JsonUtil.to_str(asset["id"])
	if ResourceLoader.exists(made):
		var loaded := load(made) as SpriteFrames
		if loaded != null:
			return loaded
	var texture := first_frame(ctx, asset)
	if texture == null:
		return null
	var frames := SpriteFrames.new()
	if frames.has_animation(&"default"):
		frames.remove_animation(&"default")
	frames.add_animation(&"idle")
	frames.add_frame(&"idle", texture)
	return frames

## Which picture of the pool a PROJECTILE asset is, by the words of its id.
static func bullet_kind(asset_id: String) -> String:
	var lower := asset_id.to_lower()
	for word: String in ["enemy", "foe"]:
		if lower.contains(word):
			return "enemy"
	if lower.contains("laser") or lower.contains("beam"):
		return "laser"
	if lower.contains("missile") or lower.contains("rocket"):
		return "missile"
	return "bullet"

## The pictures of the bullet pool: kind -> texture, from the PROJECTILE assets (the first of
## each kind). The enemies' bullets use the plain bullet when no picture is theirs.
static func bullet_textures(ctx: BuildContext) -> Dictionary:
	var out := {}
	for a in assets(ctx, "PROJECTILE"):
		var kind := bullet_kind(JsonUtil.to_str(a["id"]))
		if out.has(kind):
			continue
		var texture := first_frame(ctx, a)
		if texture != null:
			out[kind] = texture
	return out
