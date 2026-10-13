extends RefCounted
## The rivals of a racing game (generated/scenes/racing/rival_N.tscn) and what lies on its
## tracks (pickup.tscn). A rival is a car like the player's, driven by RpgRival: it has the
## picture of another vehicle (or of an enemy sprite) of the packs, or, when the packs have
## one car only, the player's in another colour.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const RaceBuild := preload("racing_build.gd")
const CarRecipe := preload("car_recipe.gd")
const MapGeo := preload("../../lib/map_geo.gd")

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([RaceBuild.PICKUP_PATH])
	for i in RaceBuild.rivals(ctx):
		out.append(RaceBuild.rival_path(i + 1))
	return out

func input_hash(ctx: BuildContext) -> String:
	var inputs := {
		"v": RECIPE_VERSION,
		"rivals": RaceBuild.rivals(ctx),
		"cars": RaceBuild.rival_assets(ctx).map(func(a: Dictionary) -> Variant: return a.get("id", "")),
		"mine": RaceBuild.car_asset(ctx).get("id", ""),
		"pickup": ArcadeBuild.chosen(ctx, "POWERUP", "powerup").get("id", ""),
		"tile": ArcadeBuild.tile(ctx),
	}
	var view := RaceBuild.view_facts(ctx)
	if not view.is_empty():  # a game seen from above has no such key: its hash is what it was
		inputs["view"] = view
	return ctx.stable_hash(inputs)

## A rival's car: `number` is 1 for the first. `tint` colours a picture that is the player's.
static func build_rival(number: int, texture: Texture2D, frame: Vector2i, headings: int, tile: int, tint: Color = Color.WHITE, body: float = 0.0) -> CharacterBody2D:
	var root := CarRecipe.build_car(texture, frame, headings, tile, false, body)
	root.name = "Rival%d" % number
	root.set("boosts", 0)
	var visual := root.get_node_or_null("Visual") as CanvasItem
	if visual != null and tint != Color.WHITE:
		visual.modulate = tint
	var driver := Node.new()
	SceneUtil.attach_script(driver, RaceBuild.RIVAL_SCRIPT)
	driver.set("skill", RaceBuild.SKILLS[(number - 1) % RaceBuild.SKILLS.size()])
	SceneUtil.add(root, driver, root, "Input")
	return root

## What lies on a track: one scene for every kind (the track sets `kind`).
static func build_pickup(tile: int, texture: Texture2D = null) -> Node2D:
	var root := Node2D.new()
	root.name = "Pickup"
	SceneUtil.attach_script(root, RaceBuild.PICKUP_SCRIPT)
	root.set("tile", float(tile))
	root.set("texture", texture)
	root.z_index = 2
	return root

func _texture(asset: Dictionary) -> Texture2D:
	var path := "res://" + JsonUtil.to_str(asset.get("path", ""))
	return load(path) as Texture2D if not asset.is_empty() and ResourceLoader.exists(path) else null

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var tile := ArcadeBuild.tile(ctx)
	var pickup := build_pickup(tile, ArcadeBuild.first_frame(ctx, ArcadeBuild.chosen(ctx, "POWERUP", "powerup")))
	var err := SceneUtil.save_scene(pickup, RaceBuild.PICKUP_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": RaceBuild.PICKUP_PATH, "err": err}, RaceBuild.PICKUP_PATH))
	var own := RaceBuild.rival_assets(ctx)
	var mine := RaceBuild.car_asset(ctx)
	# on a track seen at an angle the body is measured in the plan (CarRecipe): by how many px
	# of the screen a tile of the plan is there; 0 from above
	var shown := JsonUtil.to_float(RaceBuild.iso_view(ctx, MapGeo.new(ctx))["shown"]) if RaceBuild.isometric(ctx) else 0.0
	for i in RaceBuild.rivals(ctx):
		var asset := own[i] if i < own.size() else mine
		var tint: Color = Color.WHITE if i < own.size() else RaceBuild.TINTS[i % RaceBuild.TINTS.size()]
		var frame := Vector2i(tile, tile)
		var headings := 1
		if not asset.is_empty():
			frame = ArcadeBuild.frame_size(ctx, asset)
			headings = maxi(1, JsonUtil.to_int(ctx.catalog.effective(asset).get("headings", 1)))
		var path := RaceBuild.rival_path(i + 1)
		var body := RaceBuild.body_radius(shown, Vector2(frame), tile) if shown > 0.0 else 0.0
		err = SceneUtil.save_scene(build_rival(i + 1, _texture(asset), frame, headings, tile, tint, body), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues
