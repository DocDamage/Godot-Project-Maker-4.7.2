extends RefCounted
## Helpers of the shoot-em-up's recipes: where its scripts and scenes are, what the options say
## (the orientation, the size of the screen) and which pictures of the packs are the ship, the
## bullets and the explosion. What a pack lacks was drawn by rpggen before the build
## (the pack `rpggen_arcade_kit`), so every role asked for here has an asset.

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const Paths := preload("../../lib/paths.gd")
const TextureUtil := preload("../../lib/texture_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const DIR := "res://addons/rpg_runtime/archetypes/shmup/"
const MODE_SCRIPT := DIR + "shmup_mode.gd"
const SHIP_SCRIPT := DIR + "ship.gd"
const INPUT_SCRIPT := DIR + "ship_input.gd"
const WEAPON_SCRIPT := DIR + "weapon.gd"
const BOMB_SCRIPT := DIR + "bomb.gd"
const POOL_SCRIPT := DIR + "bullet_pool.gd"
const EXPLOSION_SCRIPT := DIR + "explosion.gd"
const STARFIELD_SCRIPT := DIR + "starfield.gd"

const SHIP_PATH := "res://generated/scenes/shmup/ship.tscn"
const EXPLOSION_PATH := "res://generated/scenes/shmup/explosion.tscn"

const PLAYER_LAYER := 2
## The ship flies this many tiles a second, and the stage scrolls this many.
const SHIP_TILES_PER_S := 7.5
const SCROLL_TILES_PER_S := 2.5
## How long the first stage is, in screens along the way it scrolls.
const STAGE_SCREENS := 6

## "vertical" or "horizontal" (config.starter_map.orientation).
static func orientation(ctx: BuildContext) -> String:
	var way := JsonUtil.to_str(ctx.section("starter_map").get("orientation", "vertical"))
	return way if way == "horizontal" else "vertical"

## The size of the screen in px (config.resolution).
static func view(ctx: BuildContext) -> Vector2i:
	var raw := JsonUtil.to_array(ctx.config.get("resolution", [640, 360]))
	if raw.size() < 2:
		return Vector2i(640, 360)
	return Vector2i(JsonUtil.to_int(raw[0]), JsonUtil.to_int(raw[1]))

static func tile(ctx: BuildContext) -> int:
	return maxi(8, JsonUtil.to_int(ctx.config.get("base_tile_size", 16)))

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
