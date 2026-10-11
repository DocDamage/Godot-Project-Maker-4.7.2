extends RefCounted
## Helpers of the run and gun's recipes: where its scripts and scenes are and what its options
## say. The soldier is a side-view character, so its body comes from the metroidvania's helper
## (MvBuild.body), and the ground of its stages from the side-view tiles of the packs.

const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")

const DIR := "res://addons/rpg_runtime/archetypes/run_and_gun/"
const MODE_SCRIPT := DIR + "run_and_gun_mode.gd"
const SOLDIER_SCRIPT := DIR + "soldier.gd"
const INPUT_SCRIPT := DIR + "soldier_input.gd"
const GUN_SCRIPT := DIR + "weapons/machine_gun.gd"
const PICKUP_SCRIPT := DIR + "weapon_pickup.gd"
const BOSS_SCRIPT := DIR + "boss.gd"
const ENEMY_DIR := DIR + "enemies/"
const GRENADE_SCRIPT := DIR + "grenade.gd"

const SCENES := "res://generated/scenes/run_and_gun/"
const SOLDIER_PATH := SCENES + "soldier.tscn"
const GRENADE_PATH := SCENES + "grenade.tscn"
const EXPLOSION_PATH := SCENES + "explosion.tscn"
const PICKUP_PATH := SCENES + "weapon_pickup.tscn"
const ENEMIES := SCENES + "enemies/"
const ENEMY_LAYER := 3
const BOSS_KINDS: Array[String] = ["wall", "walker", "flyer"]

## The scene of the boss of a kind: boss_wall.tscn, boss_walker.tscn, boss_flyer.tscn.
static func boss_path(kind: String) -> String:
	return SCENES + "boss_%s.tscn" % (kind if BOSS_KINDS.has(kind) else "wall")

const PLAYER_LAYER := 2
const WORLD_LAYER := 1
const ONE_WAY_LAYER := 11
## How long the first stage is, in screens.
const STAGE_SCREENS := 6
## How many rows of ground a flat stage has under the feet of the soldier.
const GROUND_ROWS := 3

## The hits a soldier takes (config.starter_map.health, 1 to 5).
static func health(ctx: BuildContext) -> int:
	return clampi(JsonUtil.to_int(ArcadeBuild.option(ctx, "health", 1)), 1, 5)

static func lives(ctx: BuildContext) -> int:
	return clampi(JsonUtil.to_int(ArcadeBuild.option(ctx, "lives", 3)), 1, 9)

static func keep_weapon(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ArcadeBuild.option(ctx, "keep_weapon", false))

static func left_edge_kills(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ArcadeBuild.option(ctx, "left_edge_kills", true))
