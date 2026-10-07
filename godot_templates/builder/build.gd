extends SceneTree
# Run: godot --headless --path <proj> --script res://generated/builder/build.gd
# During template tests the path is res://builder/build.gd; the builder directory is derived
# from this script's own path.

const Paths := preload("lib/paths.gd")
const BuildContext := preload("lib/build_context.gd")
const Log := preload("lib/log.gd")

const RECIPE_ORDER := [
	"project_settings_recipe",
	"tileset_recipe",
	"sprite_frames_recipe",
	"actor_recipes",
	"data_recipe",
	"object_scenes_recipe",
	"interior_recipe",
	"theme_recipe",
	"ui_recipes",
	"audio_bus_recipe",
	"boot_recipe",
	"starter_map_recipe",
	"translations_recipe",
]

## Recipes of the archetype's folder (builder/recipes/<archetype>/), run before the boot scene is
## built because boot adds the archetype's combat mode.
const ARCHETYPE_RECIPES := {
	"turn_based": ["turn_based/battle_commands_recipe", "turn_based/enemy_recipes", "turn_based/battle_scene_recipe"],
	"arpg": [],
}

func _initialize() -> void:
	var code := _run()
	quit(code)

func _run() -> int:
	var builder_dir: String = get_script().resource_path.get_base_dir()
	var ctx := BuildContext.new(builder_dir, "build")
	if not ctx.load_inputs():
		ctx.results.write(Paths.RESULTS_BUILD)
		return 1
	ctx.load_build_state()
	for recipe_name in _recipe_list(ctx):
		_run_recipe(ctx, builder_dir, recipe_name)
	var save_err := ctx.save_build_state()
	if save_err != OK:
		ctx.results.add_issue("BUILD-004", {"file": Paths.BUILD_STATE, "err": save_err}, Paths.BUILD_STATE)
	ctx.results.write(Paths.RESULTS_BUILD)
	Log.info("build finished ok=%s" % str(ctx.results.ok))
	return 0 if ctx.results.ok else 1

## RECIPE_ORDER with the archetype's recipes inserted before "boot_recipe".
static func _recipe_list(ctx: RefCounted) -> Array:
	var extra: Array = ARCHETYPE_RECIPES.get(String(ctx.config.get("archetype", "")), [])
	var out: Array = []
	for recipe_name in RECIPE_ORDER:
		if recipe_name == "boot_recipe":
			out.append_array(extra)
		out.append(recipe_name)
	return out

func _run_recipe(ctx: RefCounted, builder_dir: String, recipe_name: String) -> void:
	var script_path := "%s/recipes/%s.gd" % [builder_dir, recipe_name]
	var script: Variant = load(script_path)
	if script == null or not (script is GDScript):
		ctx.results.add_issue("BUILD-002", {"recipe": recipe_name, "reason": "recipe script failed to load"}, script_path)
		return
	var recipe: RefCounted = script.new()
	var outs: PackedStringArray = recipe.outputs(ctx)
	var in_hash: String = recipe.input_hash(ctx)
	var all_skipped := outs.size() > 0
	for out in outs:
		if not ctx.should_skip(out, in_hash):
			all_skipped = false
	if all_skipped:
		for out in outs:
			ctx.results.add_item({"recipe": recipe_name, "output": _rel(out), "action": "skipped"})
		return
	Log.info("running %s" % recipe_name)
	var built: Variant = recipe.build(ctx)
	var failed := false
	if built is Array:
		ctx.results.add_issues(built)
		for issue in built:
			if issue.get("severity", "") == "error":
				failed = true
	else:
		# A runtime error inside the recipe aborts build() and returns null.
		ctx.results.add_issue("BUILD-002", {"recipe": recipe_name, "reason": "recipe aborted with an engine error (see log)"}, script_path)
		failed = true
	for out in outs:
		var written := FileAccess.file_exists(out) or ResourceLoader.exists(out)
		if failed or not written:
			ctx.results.add_item({"recipe": recipe_name, "output": _rel(out), "action": "failed"})
		else:
			ctx.record_output(out, in_hash)
			ctx.results.add_item({"recipe": recipe_name, "output": _rel(out), "action": "written"})

static func _rel(res_path: String) -> String:
	return res_path.trim_prefix("res://")
