extends RefCounted
## Helpers of the racing game's recipes: where its scripts and scenes are and what its options
## say.

const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")

const DIR := "res://addons/rpg_runtime/archetypes/racing/"
const MODE_SCRIPT := DIR + "racing_mode.gd"
const CAR_SCRIPT := DIR + "car.gd"
const INPUT_SCRIPT := DIR + "car_input.gd"
const SPRITE_SCRIPT := DIR + "heading_sprite.gd"
const CAMERA_SCRIPT := DIR + "race_camera.gd"
const SURFACES_SCRIPT := DIR + "track_surfaces.gd"

const SCENES := "res://generated/scenes/racing/"
const CAR_PATH := SCENES + "car.tscn"

const PLAYER_LAYER := 2
const WORLD_LAYER := 1

## The test track (T16.12), in tiles: a ring of road on a field of grass.
const TRACK_CELLS := Vector2i(48, 30)
const TRACK_MARGIN := 4
const ROAD_WIDTH := 5

## `absolute`: the stick is the heading of the car; `relative` (the default): it turns it.
static func absolute_steering(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ArcadeBuild.option(ctx, "steering", "relative")) == "absolute"

## `fixed`: the camera stays over the whole track; `follow` (the default): it follows the car.
static func fixed_camera(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ArcadeBuild.option(ctx, "camera", "follow")) == "fixed"

## The car the player drives: the VEHICLE chosen on the Mapping page, else the first.
static func car_asset(ctx: BuildContext) -> Dictionary:
	return ArcadeBuild.chosen(ctx, "VEHICLE", "vehicle")

## The sheet the road is painted with: a GROUND sheet tagged `road` (the drawn road sheet is
## one); {} when the packs have ground and none of it is a road, and the road is drawn.
static func road_asset(ctx: BuildContext) -> Dictionary:
	for asset in ArcadeBuild.assets(ctx, "GROUND"):
		if JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", [])).has("road"):
			return asset
	return {}
