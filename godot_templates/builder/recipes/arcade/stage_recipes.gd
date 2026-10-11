extends RefCounted
## The stages of an arcade game: one scene per stage (generated/scenes/stages/stage_NN.tscn, an
## RpgArcadeStage with its camera, its scroller, a place for the enemies and the spawn point of
## the player) and the list the runtime reads (game/data/stages.json). The kinds call this with
## the stages of their plan and add their own layers (background, tiles) to the scene before it
## is saved.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ArcadeBuild := preload("arcade_build.gd")

## The scene of one stage, not yet saved. `stage` is its entry of the plan (title, axis, speed,
## length, exit, par_time_s; the waves and the boss stay in stages.json), `view` the size of the
## screen in px and `start` where the player appears, relative to the top left of the first screen.
static func build_stage(index: int, stage: Dictionary, view: Vector2i, start: Vector2) -> Node2D:
	var root := Node2D.new()
	root.name = ArcadeBuild.stage_id(index).to_pascal_case()
	SceneUtil.attach_script(root, ArcadeBuild.STAGE_SCRIPT)
	root.set("map_id", StringName(ArcadeBuild.stage_id(index)))
	root.set("stage_index", index)
	root.set("title", JsonUtil.to_str(stage.get("title", "")))
	root.set("exit_condition", JsonUtil.to_str(stage.get("exit", "clear_waves")))
	root.set("par_time_s", JsonUtil.to_float(stage.get("par_time_s", 0.0)))
	root.set("music_asset_id", JsonUtil.to_str(stage.get("music", "")))
	var camera := Camera2D.new()
	camera.position = Vector2(view) * 0.5
	SceneUtil.add(root, camera, root, "Camera")
	var scroller := Node.new()
	SceneUtil.attach_script(scroller, ArcadeBuild.SCROLLER_SCRIPT)
	scroller.set("axis", JsonUtil.to_str(stage.get("axis", "none")))
	scroller.set("speed", JsonUtil.to_float(stage.get("speed", 40.0)))
	scroller.set("length", JsonUtil.to_float(stage.get("length", 0.0)))
	SceneUtil.add(root, scroller, root, "Scroller")
	SceneUtil.add(root, Node2D.new(), root, "Entities")
	var spawn := Marker2D.new()
	SceneUtil.attach_script(spawn, ArcadeBuild.SPAWN_SCRIPT)
	spawn.set("spawn_id", &"default")
	spawn.position = start
	SceneUtil.add(root, spawn, root, "PlayerStart")
	return root

## `stages` as the runtime reads them: each entry with the path of its scene.
static func with_scenes(stages: Array) -> Array:
	var out: Array = []
	for i in stages.size():
		var entry := JsonUtil.to_dict(stages[i]).duplicate(true)
		entry["scene"] = ArcadeBuild.stage_path(i)
		out.append(entry)
	return out

## Writes the two lists of the stages. game/data/stages.json is yours once it exists: it is
## written when it is missing (or when `replace` says so) and never touched again.
## generated/data/stages.json is rpggen's: the stages of the plan, written on every build. The
## game reads yours and takes from the other one the stages yours does not list (a stage that
## was added to the plan later). Returns an Error code.
static func save_list(stages: Array, replace: bool = false) -> int:
	var planned := with_scenes(stages)
	var err := JsonUtil.write(ArcadeBuild.PLANNED_STAGES_PATH, {"stages": planned})
	if err != OK:
		return err
	if FileAccess.file_exists(ArcadeBuild.STAGES_PATH) and not replace:
		return OK
	return JsonUtil.write(ArcadeBuild.STAGES_PATH, {"stages": planned})

## Saves the scene of every stage of `stages` and the list. Returns the issues.
static func save_all(ctx: BuildContext, stages: Array, view: Vector2i, start: Vector2, replace: bool = false) -> Array:
	var issues: Array = []
	for i in stages.size():
		var path := ArcadeBuild.stage_path(i)
		var err := SceneUtil.save_scene(build_stage(i, JsonUtil.to_dict(stages[i]), view, start), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var listed := save_list(stages, replace)
	if listed != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": ArcadeBuild.STAGES_PATH, "err": listed}, ArcadeBuild.STAGES_PATH))
	return issues
