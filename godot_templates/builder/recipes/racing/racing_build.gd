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
const RACE_SCRIPT := DIR + "race.gd"
const RIVAL_SCRIPT := DIR + "rival.gd"
const PICKUP_SCRIPT := DIR + "pickup.gd"

const SCENES := "res://generated/scenes/racing/"
const CAR_PATH := SCENES + "car.tscn"
const PICKUP_PATH := SCENES + "pickup.tscn"
const MAX_RIVALS := 5
## How good each rival is at driving (RpgRival.skill), the first the best.
const SKILLS: Array[float] = [0.9, 0.75, 0.6, 0.8, 0.5]
## The colours of rivals that have no picture of their own: the player's car, tinted.
const TINTS: Array[Color] = [Color(0.45, 0.6, 1.0), Color(0.5, 0.95, 0.5), Color(1.0, 0.9, 0.4), Color(0.9, 0.5, 1.0), Color(0.5, 0.95, 0.95)]

## The scene of rival `number` (1 for the first): rival_1.tscn, rival_2.tscn, ...
static func rival_path(number: int) -> String:
	return SCENES + "rival_%d.tscn" % number

## How many rivals race against the player (config.starter_map.rivals, 0 to 5).
static func rivals(ctx: BuildContext) -> int:
	return clampi(JsonUtil.to_int(ArcadeBuild.option(ctx, "rivals", 3)), 0, MAX_RIVALS)

static func rubber_band(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ArcadeBuild.option(ctx, "rubber_band", true))

## The pictures of the rivals: the other vehicles of the packs, then their enemies that are
## sprites. Fewer than the rivals there are: the rest drive the player's car in another colour.
static func rival_assets(ctx: BuildContext) -> Array[Dictionary]:
	var mine := JsonUtil.to_str(car_asset(ctx).get("id", ""))
	var out: Array[Dictionary] = []
	for asset in ArcadeBuild.assets(ctx, "VEHICLE"):
		if JsonUtil.to_str(asset.get("id", "")) != mine:
			out.append(asset)
	for asset in ArcadeBuild.assets(ctx, "ENEMY"):
		if JsonUtil.to_str(ctx.catalog.effective(asset).get("usage", "")) == "sprite":
			out.append(asset)
	return out

## Where the car of grid slot `slot` stands (px): two side by side, row behind row, the first
## row just before the line. `start` is the middle of the grid, `heading` the way of the race.
static func grid_slot(start: Vector2, heading: float, slot: int, tile: int) -> Vector2:
	var way := Vector2.from_angle(heading)
	var side := -1.0 if slot % 2 == 0 else 1.0
	@warning_ignore("integer_division")
	var row := slot / 2
	return start + way * (0.7 - 1.4 * row) * tile + way.orthogonal() * side * 1.2 * tile

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

## The sheet the road is painted with: a GROUND sheet of the packs tagged `road`; {} when
## none of their ground is a road, and the road is drawn. The drawn road sheet does not count:
## its tiles are a road one tile wide, and a track's road is five.
static func road_asset(ctx: BuildContext) -> Dictionary:
	for asset in ArcadeBuild.assets(ctx, "GROUND"):
		var tags := JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", []))
		if tags.has("road") and not tags.has("arcade_kit"):
			return asset
	return {}

## The first asset of `role` in use that has the tag `tag`; {} without one.
static func tagged(ctx: BuildContext, role: String, tag: String) -> Dictionary:
	for asset in ArcadeBuild.assets(ctx, role):
		if JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", [])).has(tag):
			return asset
	return {}

## True for a sheet rpggen drew itself (the arcade kit).
static func is_drawn(ctx: BuildContext, asset: Dictionary) -> bool:
	return JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", [])).has("arcade_kit")

