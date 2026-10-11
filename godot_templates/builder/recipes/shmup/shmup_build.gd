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
const ArcadeBuild := preload("../arcade/arcade_build.gd")

const DIR := "res://addons/rpg_runtime/archetypes/shmup/"
const MODE_SCRIPT := DIR + "shmup_mode.gd"
const SHIP_SCRIPT := DIR + "ship.gd"
const INPUT_SCRIPT := DIR + "ship_input.gd"
const WEAPON_SCRIPT := DIR + "weapon.gd"
const BOMB_SCRIPT := DIR + "bomb.gd"
const POOL_SCRIPT := "res://addons/rpg_runtime/archetypes/arcade/bullet_pool.gd"
const EXPLOSION_SCRIPT := "res://addons/rpg_runtime/archetypes/arcade/explosion.gd"
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

## The helpers below are the arcade kinds' own (ArcadeBuild); the names are kept for the recipes
## of this kind.
static func assets(ctx: BuildContext, role: String) -> Array[Dictionary]:
	return ArcadeBuild.assets(ctx, role)

static func chosen(ctx: BuildContext, role: String, key: String) -> Dictionary:
	return ArcadeBuild.chosen(ctx, role, key)

static func frame_size(ctx: BuildContext, asset: Dictionary) -> Vector2i:
	return ArcadeBuild.frame_size(ctx, asset)

static func first_frame(ctx: BuildContext, asset: Dictionary) -> Texture2D:
	return ArcadeBuild.first_frame(ctx, asset)

static func frames_of(ctx: BuildContext, asset: Dictionary) -> SpriteFrames:
	return ArcadeBuild.frames_of(ctx, asset)

static func bullet_kind(asset_id: String) -> String:
	return ArcadeBuild.bullet_kind(asset_id)

static func bullet_textures(ctx: BuildContext) -> Dictionary:
	return ArcadeBuild.bullet_textures(ctx)
