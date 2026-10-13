extends RefCounted
## Helpers of the racing game's recipes: where its scripts and scenes are and what its options
## say.

const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const WorldPlan := preload("../../lib/world_plan.gd")

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
const HUD_SCRIPT := DIR + "ui/racing_hud.gd"
const VIEW_SCRIPT := DIR + "race_view.gd"

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

## A player who comes in last twice is out of the championship (config.starter_map.elimination).
static func elimination(ctx: BuildContext) -> bool:
	return JsonUtil.to_bool(ArcadeBuild.option(ctx, "elimination", false))

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


# ---------------------------------------------------------------- the isometric view (T17.15)

## The plan of a track (rpggen/core/track_plan.py): a cell of its loop is a block of this many
## tiles, behind a wall this many tiles thick round the field.
const BLOCK := 9
const BORDER := 1
## How many tiles of the plan a diamond is wide when nothing says more (a game without a car's
## picture): a third of a block.
const DRAWN_TILES := 3
## How long the picture of the player's car is to be on the road, in tiles of the plan: the
## scale of an isometric track is chosen for it, since the picture of a car is as large as its
## pack drew it and a diamond as large as its own pack did.
const CAR_TILES := 1.6
## The most a diamond of road pieces is enlarged, and the fewest and most tiles a diamond of a
## drawn road is wide.
const MAX_SCALE := 4
const TILES_RANGE := Vector2i(2, 9)
## What a tile of the plan is to be on the screen, in px, when a car stands: the camera's zoom
## makes it so when the scale leaves it much more or much less.
const TILE_ON_SCREEN := 13.0
const TILE_ON_SCREEN_RANGE := Vector2(9.0, 22.0)
const ZOOM_RANGE := Vector2(0.4, 4.0)
## The body of a car on an isometric track, in tiles: what its picture measures, kept between
## a car that can be seen to touch and one of which two fit side by side on the grid.
const BODY_RANGE := Vector2(0.4, 0.65)

## True for a racing game whose tracks are painted on diamonds.
static func isometric(ctx: BuildContext) -> bool:
	return MapGeo.is_isometric(ctx)

## The tracks rpggen planned and stored (the section `stages` of the world plan), [] without.
static func stored_tracks() -> Array:
	var stages := JsonUtil.to_dict(WorldPlan.read().get("stages", {}))
	if JsonUtil.to_str(stages.get("kind", "")) != "racing":
		return []
	return JsonUtil.to_array(stages.get("list", []))

## True when the road of an isometric track is laid from the road pieces of the packs (their
## `joins`): the packs have such pieces and the tracks have a loop to lay them along. A cell
## of the loop is then one diamond. Else the road is drawn.
static func road_pieces(geo: MapGeo) -> bool:
	if not geo.isometric or geo.iso.laid_pieces("ROAD").is_empty():
		return false
	var tracks := stored_tracks()
	return not tracks.is_empty() and not JsonUtil.to_array(JsonUtil.to_dict(tracks[0]).get("loop", [])).is_empty()

## How long the picture of the player's car is, in px: the longer side of a frame of it. 0 for
## a game without one.
static func car_px(ctx: BuildContext) -> float:
	var asset := car_asset(ctx)
	if asset.is_empty():
		return 0.0
	var frame := ArcadeBuild.frame_size(ctx, asset)
	return float(maxi(frame.x, frame.y))

## The zoom of the camera over a car that stands, for a tile of the plan that is `shown` px on
## the screen: 1 while that is between 9 and 22 px, else what makes it 13.
static func zoom_for(shown: float) -> float:
	if shown <= 0.0 or (shown >= TILE_ON_SCREEN_RANGE.x and shown <= TILE_ON_SCREEN_RANGE.y):
		return 1.0
	return snappedf(clampf(TILE_ON_SCREEN / shown, ZOOM_RANGE.x, ZOOM_RANGE.y), 0.05)

## The scale of an isometric track, for a car whose picture is `car` px long (0: none) on the
## diamonds of `geo`, the road laid from pieces of the packs or drawn (`pieces`):
## `tiles`: how many tiles of the plan a diamond of the track is wide (a whole block with
## pieces: a cell of the loop is one diamond); `scale`: how many times the diamonds of the
## packs are enlarged (1 for a drawn road; with pieces what brings the car nearest to
## CAR_TILES of the road); `shown`: how many px of the screen a tile of the plan then is,
## along the axes of the map; `zoom`: the camera's over a car that stands. The scale is kept
## where the camera needs no zoom while the diamonds allow it: a picture that is not zoomed is
## the sharper one.
static func scale_for(geo: MapGeo, car: float, pieces: bool) -> Dictionary:
	# how many tiles a diamond of the packs would be wide for the car to be CAR_TILES long
	var wanted := float(DRAWN_TILES) if car <= 0.0 else geo.tile_px * CAR_TILES / car
	# ... and the fewest that leave a tile no larger on the screen than the camera shows as it is
	var fewest := geo.tile_px / TILE_ON_SCREEN_RANGE.y
	var scale := 1
	var tiles := BLOCK
	if pieces:
		scale = clampi(mini(roundi(BLOCK / wanted), floori(BLOCK / fewest)), 1, MAX_SCALE)
	else:
		tiles = clampi(maxi(roundi(wanted), ceili(fewest)), TILES_RANGE.x, TILES_RANGE.y)
	var shown := float(geo.tile_px) * scale / tiles
	return {"pieces": pieces, "tiles": tiles, "scale": scale, "shown": shown, "zoom": zoom_for(shown)}

## The scale of the project's isometric tracks (`scale_for` its car and its road pieces).
static func iso_view(ctx: BuildContext, geo: MapGeo) -> Dictionary:
	return scale_for(geo, car_px(ctx), road_pieces(geo))

## The radius of the body of a car on an isometric track, in px of the plan: its picture is
## `frame` px of the screen, of which a tile of the plan is `shown`.
static func body_radius(shown: float, frame: Vector2, tile: int) -> float:
	if shown <= 0.0:
		return tile * BODY_RANGE.x
	return clampf(minf(frame.x, frame.y) * 0.36 / shown, BODY_RANGE.x, BODY_RANGE.y) * tile

## What of the view a car's scene is built with, for the hash of its recipe: {} for a game seen
## from above, so that its hash is what it was.
static func view_facts(ctx: BuildContext) -> Dictionary:
	if not isometric(ctx):
		return {}
	var geo := MapGeo.new(ctx)
	var facts := iso_view(ctx, geo)
	facts["footprint"] = [geo.footprint.x, geo.footprint.y]
	return facts
