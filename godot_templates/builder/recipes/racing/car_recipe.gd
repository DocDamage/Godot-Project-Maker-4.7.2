extends RefCounted
## The car of a racing game (generated/scenes/racing/car.tscn) from the VEHICLE sprite: a sheet
## of headings shows the frame nearest the way the car points, a single picture is rotated.
## On a track seen at an angle (T17.15) the car is the same scene: it drives on the flat plan
## and its picture is put where that is on the screen by the car itself (RpgRaceView). Only its
## body is measured differently there, since its picture is in px of the screen and the plan
## has other px.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const RaceBuild := preload("racing_build.gd")
const MapGeo := preload("../../lib/map_geo.gd")

const DRAWN := Color(0.85, 0.2, 0.2)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([RaceBuild.CAR_PATH])

func input_hash(ctx: BuildContext) -> String:
	var asset := RaceBuild.car_asset(ctx)
	var inputs := {
		"v": RECIPE_VERSION,
		"car": asset.get("id", ""),
		"facets": ctx.catalog.effective(asset) if not asset.is_empty() else {},
		"tile": ArcadeBuild.tile(ctx),
		"absolute": RaceBuild.absolute_steering(ctx),
	}
	var view := RaceBuild.view_facts(ctx)
	if not view.is_empty():  # a game seen from above has no such key: its hash is what it was
		inputs["view"] = view
	return ctx.stable_hash(inputs)

## The car scene. `texture` is the whole sheet, `frame` the size of one picture of it and
## `headings` how many headings it has (1: the picture is rotated). `body` is the radius of
## its body in px of the plan when the picture does not say it (an isometric track); 0: the
## picture's own size.
static func build_car(texture: Texture2D, frame: Vector2i, headings: int, tile: int, player: bool = true, body: float = 0.0) -> CharacterBody2D:
	var root := CharacterBody2D.new()
	root.name = "Car"
	root.motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	SceneUtil.attach_script(root, RaceBuild.CAR_SCRIPT)
	root.set("tile_size", float(tile))
	root.set("is_player", player)
	root.collision_layer = 1 << (RaceBuild.PLAYER_LAYER - 1)
	root.collision_mask = (1 << (RaceBuild.WORLD_LAYER - 1)) | (1 << (RaceBuild.PLAYER_LAYER - 1))
	root.z_index = 5
	var size := Vector2(maxi(1, frame.x), maxi(1, frame.y))
	if texture != null:
		var visual := Sprite2D.new()
		SceneUtil.attach_script(visual, RaceBuild.SPRITE_SCRIPT)
		visual.texture = texture
		visual.hframes = maxi(1, int(texture.get_width() / size.x))
		visual.vframes = maxi(1, int(texture.get_height() / size.y))
		visual.set("headings", clampi(headings, 1, visual.hframes * visual.vframes))
		SceneUtil.add(root, visual, root, "Visual")
	else:
		size = Vector2(tile, tile * 1.5)
		SceneUtil.add(root, ArcadeBuild.stand_in("Visual", size, DRAWN), root, "Visual")
	var shape := CollisionShape2D.new()
	var circle := CircleShape2D.new()
	circle.radius = body if body > 0.0 else maxf(3.0, minf(size.x, size.y) * 0.36)
	shape.shape = circle
	SceneUtil.add(root, shape, root, "Body")
	if player:
		var input := Node.new()
		SceneUtil.attach_script(input, RaceBuild.INPUT_SCRIPT)
		SceneUtil.add(root, input, root, "Input")
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var asset := RaceBuild.car_asset(ctx)
	var texture: Texture2D = null
	var frame := Vector2i(ArcadeBuild.tile(ctx), ArcadeBuild.tile(ctx))
	var headings := 1
	if not asset.is_empty():
		var path := "res://" + JsonUtil.to_str(asset.get("path", ""))
		if ResourceLoader.exists(path):
			texture = load(path) as Texture2D
		frame = ArcadeBuild.frame_size(ctx, asset)
		headings = maxi(1, JsonUtil.to_int(ctx.catalog.effective(asset).get("headings", 1)))
	var body := 0.0
	if RaceBuild.isometric(ctx):
		var seen := RaceBuild.iso_view(ctx, MapGeo.new(ctx))
		body = RaceBuild.body_radius(JsonUtil.to_float(seen["shown"]), Vector2(frame), ArcadeBuild.tile(ctx))
	var car := build_car(texture, frame, headings, ArcadeBuild.tile(ctx), true, body)
	car.set("absolute_steering", RaceBuild.absolute_steering(ctx))
	car.set("boosts", 1)  # one to start with; the rest lie on the track
	var err := SceneUtil.save_scene(car, RaceBuild.CAR_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": RaceBuild.CAR_PATH, "err": err}, RaceBuild.CAR_PATH))
	return issues
