extends RefCounted
## The first stage of a shoot-em-up (generated/scenes/stages/stage_01.tscn) and the list of the
## stages (game/data/stages.json). The stage is the arcade stage of StageRecipes with a
## background that loops along the way it scrolls (the BACKGROUND pictures of the packs, the
## farthest slowest; a field of stars when the packs have none), the bullet pool and the ship.
## Its waves are the work of the next card: until then the stage ends where its scrolling ends.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const StageRecipes := preload("../arcade/stage_recipes.gd")
const ShmupBuild := preload("shmup_build.gd")

const PARALLAX_TAG := "parallax:"
## How fast a layer scrolls against the camera: the farthest first.
const FACTORS: Array[float] = [0.2, 0.45, 0.7, 0.85]
const BACKDROP := Color(0.03, 0.03, 0.08)

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([ArcadeBuild.stage_path(0)])
	if not FileAccess.file_exists(ArcadeBuild.STAGES_PATH):
		out.append(ArcadeBuild.STAGES_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	var layers: Array = []
	for entry in background_layers(ctx):
		layers.append(entry["asset"])
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"stages": plan(ctx),
		"layers": layers,
		"bullets": ShmupBuild.bullet_textures(ctx).keys(),
		"view": ShmupBuild.view(ctx),
	})

## The stages of the game as stages.json has them (without their scenes).
static func plan(ctx: BuildContext) -> Array:
	var way := ShmupBuild.orientation(ctx)
	var view := ShmupBuild.view(ctx)
	var along := float(view.x if way == "horizontal" else view.y)
	var speed := ShmupBuild.tile(ctx) * ShmupBuild.SCROLL_TILES_PER_S
	var length := along * ShmupBuild.STAGE_SCREENS
	return [{
		"title": "",
		"axis": RpgShmupMath.axis_of(way),
		"speed": speed,
		"length": length,
		"exit": "reach_end",
		"par_time_s": ceilf(length / speed) + 10.0,
		"waves": [],
	}]

## The background pictures: [{asset, depth, path}], the farthest first. A picture tagged
## `parallax:<n>` has that depth; the others follow in the order of their ids.
static func background_layers(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var next := 1
	for a in ShmupBuild.assets(ctx, "BACKGROUND"):
		var depth := 0
		for tag: Variant in JsonUtil.to_array(ctx.catalog.effective(a).get("tags", [])):
			var text := JsonUtil.to_str(tag)
			if text.begins_with(PARALLAX_TAG) and text.trim_prefix(PARALLAX_TAG).is_valid_int():
				depth = text.trim_prefix(PARALLAX_TAG).to_int()
		if depth <= 0:
			depth = next
		next = maxi(next, depth) + 1
		out.append({"asset": a["id"], "depth": depth, "path": "res://" + JsonUtil.to_str(a["path"])})
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool:
		return JsonUtil.to_int(x["depth"]) < JsonUtil.to_int(y["depth"]) or (x["depth"] == y["depth"] and JsonUtil.to_str(x["asset"]) < JsonUtil.to_str(y["asset"])))
	return out

static func factor(index: int) -> float:
	return FACTORS[clampi(index, 0, FACTORS.size() - 1)]

## A layer that scrolls at `speed` of the camera along the way of the game and repeats every
## `period` px along it.
static func _layer(layer_name: String, speed: float, period: float, way: String, view: Vector2) -> Parallax2D:
	var layer := Parallax2D.new()
	layer.name = layer_name
	var along := view.x if way == "horizontal" else view.y
	if way == "horizontal":
		layer.scroll_scale = Vector2(speed, 1.0)
		layer.repeat_size = Vector2(period, 0.0)
	else:
		layer.scroll_scale = Vector2(1.0, speed)
		layer.repeat_size = Vector2(0.0, period)
	layer.repeat_times = maxi(3, ceili(along / maxf(1.0, period)) + 2)
	return layer

## The "Background" node of a stage: a dark backdrop that stays on the screen, then the layers.
static func build_background(ctx: BuildContext, way: String, view: Vector2) -> Node2D:
	var holder := Node2D.new()
	holder.name = "Background"
	holder.z_index = -20
	var still := Parallax2D.new()
	still.name = "Backdrop"
	still.scroll_scale = Vector2.ZERO
	var fill := ArcadeBuild.stand_in("Fill", view, BACKDROP)
	fill.position = view * 0.5
	still.add_child(fill)
	holder.add_child(still)
	var found := background_layers(ctx)
	for i in found.size():
		var texture := load(JsonUtil.to_str(found[i]["path"])) as Texture2D
		if texture == null:
			continue
		var size := texture.get_size()
		# scaled by a whole number so that it covers the screen across the way of the game
		var across := view.y if way == "horizontal" else view.x
		var own := size.y if way == "horizontal" else size.x
		var zoom := maxf(1.0, ceilf(across / maxf(1.0, own)))
		var period := (size.x if way == "horizontal" else size.y) * zoom
		var layer := _layer("Layer%d" % (i + 1), factor(i), period, way, view)
		var sprite := Sprite2D.new()
		sprite.name = "Sprite"
		sprite.texture = texture
		sprite.centered = false
		sprite.scale = Vector2(zoom, zoom)
		layer.add_child(sprite)
		holder.add_child(layer)
	if found.is_empty():
		for i in 2:
			var layer := _layer("Stars%d" % (i + 1), factor(i * 2), view.x if way == "horizontal" else view.y, way, view)
			var stars := Node2D.new()
			stars.name = "Stars"
			SceneUtil.attach_script(stars, ShmupBuild.STARFIELD_SCRIPT)
			stars.set("area", view)
			stars.set("count", 40 + 30 * i)
			stars.set("star_seed", JsonUtil.to_int(ctx.config.get("seed", 12345)) + i)
			layer.add_child(stars)
			holder.add_child(layer)
	return holder

## The scene of the stage `index`: the arcade stage with its background, its bullets and its ship.
static func build_stage(ctx: BuildContext, index: int, stage: Dictionary) -> Node2D:
	var way := ShmupBuild.orientation(ctx)
	var view := Vector2(ShmupBuild.view(ctx))
	var start := view * 0.5 + RpgShmupMath.start_offset(view, way)
	var root := StageRecipes.build_stage(index, stage, Vector2i(view), start)
	var background := build_background(ctx, way, view)
	root.add_child(background)
	root.move_child(background, 0)
	SceneUtil.set_owner_recursive(background, root)
	var pool := Node2D.new()
	SceneUtil.attach_script(pool, ShmupBuild.POOL_SCRIPT)
	pool.set("textures", ShmupBuild.bullet_textures(ctx))
	pool.z_index = 4
	SceneUtil.add(root, pool, root, "Bullets")
	var ship := SceneUtil.instance(ShmupBuild.SHIP_PATH)
	if ship is Node2D:
		(ship as Node2D).position = start
		SceneUtil.add(root, ship, root, "Ship")
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var stages := plan(ctx)
	for i in stages.size():
		var path := ArcadeBuild.stage_path(i)
		var err := SceneUtil.save_scene(build_stage(ctx, i, JsonUtil.to_dict(stages[i])), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var listed := StageRecipes.save_list(stages)
	if listed != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeBuild.STAGES_PATH, "err": listed}, ArcadeBuild.STAGES_PATH))
	return issues
