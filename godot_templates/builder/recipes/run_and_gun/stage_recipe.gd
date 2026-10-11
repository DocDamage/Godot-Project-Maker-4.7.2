extends RefCounted
## The first stage of a run and gun (generated/scenes/stages/stage_01.tscn) and the lists of
## the stages. The stage is the arcade stage of StageRecipes seen from the side: the parallax
## pictures of the packs behind it, a flat floor of the ground tiles of the packs (the layer
## "Ground"), the bullet pool (bullets stop at the ground) and the soldier. Its scroller does
## not move by itself: the soldier leads the camera to the right. The stage ends at the end of
## its length. Its waves are a fixed set for now (runners, a sniper, jumpers, a trap of turrets
## that stops the camera, a wall cannon, and three weapons on their carriers); platforms, pits
## and a boss are the work of the stage planner.

const RECIPE_VERSION := 2

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const Paths := preload("../../lib/paths.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const StageRecipes := preload("../arcade/stage_recipes.gd")
const SideKit := preload("../metroidvania/side_kit.gd")
const Parallax := preload("../metroidvania/parallax_recipe.gd")
const RngBuild := preload("run_and_gun_build.gd")
const EnemyRecipes := preload("enemy_recipes.gd")

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([ArcadeBuild.stage_path(0), ArcadeBuild.PLANNED_STAGES_PATH])
	if not FileAccess.file_exists(ArcadeBuild.STAGES_PATH):
		out.append(ArcadeBuild.STAGES_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	var def := tileset_def(ctx)
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"stages": plan(ctx),
		"tileset": def.get("name", ""),
		"sources": def.get("sources", []),
		"layers": Parallax.layers(ctx),
		"bullets": ArcadeBuild.bullet_textures(ctx).keys(),
	})

## The stages of the game as stages.json has them (without their scenes).
static func plan(ctx: BuildContext) -> Array:
	var view := ArcadeBuild.view(ctx)
	var length := float(view.x * RngBuild.STAGE_SCREENS)
	return [{
		"title": "",
		"axis": "right",
		"speed": 0.0,  # the soldier leads the camera
		"length": length,
		"exit": "reach_end",
		"par_time_s": ceilf(length / (ArcadeBuild.tile(ctx) * 5.0)) + 40.0,
		"waves": waves(view, ArcadeBuild.tile(ctx)),
	}]

## How far beyond the right edge of the screen a wave appears, in px.
const AHEAD := 24.0
## The waves of the first stage: [what comes, how many, where along the stage (in screens), how
## high above the floor (in tiles), what else its entry says].
const FIRST_STAGE := [
	["runner", 3, 0.5, 0.0, {}],
	["sniper", 1, 1.2, 0.0, {}],
	["pickup", 1, 1.6, 5.0, {"weapon": "spread"}],
	["jumper", 2, 2.2, 0.0, {}],
	["turret", 2, 3.0, 0.0, {"blocking": true}],
	["wall_cannon", 1, 3.8, 3.0, {}],
	["pickup", 1, 4.2, 5.0, {"weapon": "laser"}],
	["runner", 4, 4.6, 0.0, {}],
	["pickup", 1, 5.0, 5.0, {"weapon": "flame"}],
]

## The waves of the first stage on a screen of `view` px. What comes stands on the floor (or
## hangs above it) just beyond the right edge of the screen at the moment its wave comes; a
## wave that stops the camera stands on the screen, in its right third, or it would never be
## seen.
static func waves(view: Vector2i, tile: int) -> Array:
	var out: Array = []
	var cells := stage_cells(float(view.x * RngBuild.STAGE_SCREENS), view, tile)
	var floor_y := float(floor_row(cells.y) * tile)
	for row: Array in FIRST_STAGE:
		var what := JsonUtil.to_str(row[0])
		var count := JsonUtil.to_int(row[1])
		var at := JsonUtil.to_float(row[2]) * view.x
		var gap := tile * (3.0 if what == "turret" else 2.0)
		var blocking := JsonUtil.to_bool(JsonUtil.to_dict(row[4]).get("blocking", false))
		var first_x := at + view.x * 0.7 if blocking else at + view.x + AHEAD
		var entry := {
			"id": "w%02d" % (out.size() + 1),
			"enemy": what,
			"scene": RngBuild.PICKUP_PATH if what == "pickup" else EnemyRecipes.scene_path(what),
			"formation": "line",
			"count": count,
			"gap": gap,
			"trigger": "progress",
			"at": at,
			"anchor": "stage",
			# the middle of the line, from where its first one stands
			"position": [first_x + (count - 1) * gap * 0.5, floor_y - JsonUtil.to_float(row[3]) * tile],
		}
		entry.merge(JsonUtil.to_dict(row[4]))
		out.append(entry)
	return out

static func tileset_def(ctx: BuildContext) -> Dictionary:
	var def: Dictionary = ctx.catalog.tileset_def("overworld")
	if def.is_empty() and not ctx.catalog.tileset_defs().is_empty():
		def = ctx.catalog.tileset_defs()[0]
	return def

## The size of a stage `length` px long on a screen of `view` px, in tiles: as wide as its
## length and one more screen, as high as the screen.
static func stage_cells(length: float, view: Vector2i, tile: int) -> Vector2i:
	return Vector2i(ceili((length + view.x) / tile), ceili(view.y / float(tile)))

## The row of the top of the floor of a stage `rows` tiles high.
static func floor_row(rows: int) -> int:
	return rows - RngBuild.GROUND_ROWS

## Paints a flat floor over the whole width of `layer`: the top tile of the kit, its fill below.
static func paint_floor(layer: TileMapLayer, cells: Vector2i, kit: Dictionary) -> void:
	var top := JsonUtil.to_dict(kit["top"])
	var fill := JsonUtil.to_dict(kit["fill"])
	if fill.is_empty():
		fill = top
	var first := floor_row(cells.y)
	for x in cells.x:
		MapUtil.put(layer, Vector2i(x, first), top)
		for y in range(first + 1, cells.y):
			MapUtil.put(layer, Vector2i(x, y), fill)

## The scene of the stage `index`.
static func build_stage(ctx: BuildContext, index: int, stage: Dictionary, tile_set: TileSet, kit: Dictionary) -> Node2D:
	var view := ArcadeBuild.view(ctx)
	var tile := tile_set.tile_size.x
	var cells := stage_cells(JsonUtil.to_float(stage.get("length", 0.0)), view, tile)
	var start := Vector2(tile * 3.5, floor_row(cells.y) * tile)
	var root := StageRecipes.build_stage(index, stage, view, start)
	root.get_node("PlayerStart").set("side_view", true)
	root.get_node("PlayerStart").set("facing", "right")
	var background := Parallax.build(ctx, Vector2(cells * tile), Vector2(view))
	if background != null:
		root.add_child(background)
		root.move_child(background, 0)
		SceneUtil.set_owner_recursive(background, root)
	var ground := TileMapLayer.new()
	ground.tile_set = tile_set
	ground.collision_enabled = true
	paint_floor(ground, cells, kit)
	SceneUtil.add(root, ground, root, "Ground")
	root.move_child(ground, 1 if background != null else 0)
	var pool := Node2D.new()
	SceneUtil.attach_script(pool, ArcadeBuild.POOL_SCRIPT)
	pool.set("textures", ArcadeBuild.bullet_textures(ctx))
	pool.set("wall_mask", 1)
	pool.z_index = 4
	SceneUtil.add(root, pool, root, "Bullets")
	var soldier := SceneUtil.instance(RngBuild.SOLDIER_PATH)
	if soldier is Node2D:
		(soldier as Node2D).position = start
		SceneUtil.add(root, soldier, root, "Soldier")
	return root

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var stages := plan(ctx)
	var def := tileset_def(ctx)
	var path := ArcadeBuild.stage_path(0)
	if def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, path))
		return issues
	var tileset_path: String = Paths.TILESETS_DIR + "%s.tres" % def["name"]
	var tile_set := load(tileset_path) as TileSet
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": tileset_path}, tileset_path))
		return issues
	var kit := SideKit.find(ctx, def, tile_set)
	if JsonUtil.to_dict(kit["top"]).is_empty():
		issues.append(ctx.make_issue("BUILD-002", {"recipe": "stage_recipe", "reason": "the tile set has no solid tile to build a floor from"}, tileset_path))
		return issues
	for i in stages.size():
		path = ArcadeBuild.stage_path(i)
		var err := SceneUtil.save_scene(build_stage(ctx, i, JsonUtil.to_dict(stages[i]), tile_set, kit), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var listed := StageRecipes.save_list(stages)
	if listed != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeBuild.STAGES_PATH, "err": listed}, ArcadeBuild.STAGES_PATH))
	return issues
