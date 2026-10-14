extends SceneTree
# Run: godot --headless --path <proj> --script res://generated/builder/build.gd [-- --update-ledger]
# --update-ledger (used by the editor's "Regenerate", T8.05) refreshes the ownership ledger's
# hashes of the files this run wrote. It does not run promotion.
# During template tests the path is res://builder/build.gd; the builder directory is derived
# from this script's own path.

const Paths := preload("lib/paths.gd")
const BuildContext := preload("lib/build_context.gd")
const Log := preload("lib/log.gd")
const JsonUtil := preload("lib/json_util.gd")
const RecipeContext := preload("lib/recipe_context.gd")

const UPDATE_LEDGER_FLAG := "--update-ledger"
const FILE_HASH := "res://addons/rpg_project_tools/tools/file_hash.gd"
# Files every build run maintains besides its recipes' outputs.
const STATE_FILES: Array[String] = ["rpggen/build_state.json", "rpggen/tileset_apply_state.json"]

const RECIPE_ORDER: Array[String] = [
	"project_settings_recipe",
	"tileset_recipe",
	"sprite_frames_recipe",
	"actor_recipes",
	"data_recipe",
	"credits_recipe",
	"lighting_recipe",
	"object_scenes_recipe",
	"interior_recipe",
	"theme_recipe",
	"ui_recipes",
	"audio_bus_recipe",
	"boot_recipe",
	"starter_map_recipe",
	"second_map_recipe",
	"imported_maps_recipe",
	"minimap_recipe",
	"translations_recipe",
]

## The user's own recipes (T12.60): every *.gd here runs after rpggen's recipes, in name order.
const CUSTOM_RECIPES_DIR := "res://game/builder_recipes"
const EXAMPLE_RECIPE := "res://game/builder_recipes/example_recipe.gd"
const EXAMPLE_UID := 3412840461729335137  # the example recipe's uid (see _seed_example_recipe)

## Counts the script errors Godot logs while a custom recipe runs: an error inside build() only
## ends that function, so the count is how a failed recipe is noticed.
class ScriptErrors extends Logger:
	var count := 0
	var last := ""
	var _mutex := Mutex.new()

	func _log_error(_function: String, _file: String, _line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
		if error_type != ERROR_TYPE_SCRIPT:
			return
		_mutex.lock()
		count += 1
		last = rationale if rationale != "" else code
		_mutex.unlock()

	func _log_message(_message: String, _error: bool) -> void:
		pass

## Recipes of the archetype's folder (builder/recipes/<archetype>/), run before the boot scene is
## built because boot adds the archetype's combat mode.
const ARCHETYPE_RECIPES := {
	"turn_based": ["turn_based/battle_commands_recipe", "turn_based/enemy_recipes", "turn_based/battle_scene_recipe"],
	"arpg": ["arpg/swing_recipe", "arpg/enemy_recipes", "arpg/hud_recipe", "arpg/mode_recipe"],
	"metroidvania": ["metroidvania/enemy_recipes", "metroidvania/objects_recipe", "metroidvania/hud_recipe", "metroidvania/mode_recipe"],
	"shmup": ["shmup/ship_recipe", "shmup/enemy_recipes", "shmup/hud_recipe", "shmup/mode_recipe"],
	"run_and_gun": ["run_and_gun/soldier_recipe", "run_and_gun/enemy_recipes", "arcade/hud_recipe", "run_and_gun/mode_recipe"],
	"racing": ["racing/car_recipe", "racing/rival_recipes", "racing/hud_recipe", "racing/mode_recipe"],
	# a farm (T17.04) is a top-down game: it skips nothing and adds its tools, crops, soil and mode,
	# its own map with the farmhouse (T17.06), the people of the village (T17.09) and the animals
	# of its coop and its barn (T17.07: nothing in a farm without either)
	# the maps added to it and the farm's side of their doors (T17.23), before the farm's map,
	# which instances that side; the festivals of its year (T17.25: nothing in a farm without them)
	"farm": ["farm/farmer_recipe", "farm/crop_recipes", "farm/forage_recipe", "farm/field_recipe", "farm/room_recipe", "farm/home_recipe", "farm/added_maps_recipe", "farm/farm_map_recipe", "farm/people_recipes", "farm/events_recipe", "farm/animal_recipes", "farm/hud_recipe", "farm/mode_recipe"],
}
## The shared recipes an archetype does without, and what it runs in the place of the first of
## them: a metroidvania has rooms (T14.06), not a starter map with houses and a field.
const ARCHETYPE_SKIPS := {
	"metroidvania": ["interior_recipe", "starter_map_recipe", "second_map_recipe"],
	# an arcade game has stages (T16.04), not a village, and a ship, not a walking character
	"shmup": ["actor_recipes", "interior_recipe", "starter_map_recipe", "second_map_recipe"],
	"run_and_gun": ["actor_recipes", "interior_recipe", "starter_map_recipe", "second_map_recipe"],
	"racing": ["actor_recipes", "interior_recipe", "starter_map_recipe", "second_map_recipe"],
}
const ARCHETYPE_MAPS := {
	"metroidvania": ["metroidvania/rooms_recipe"],
	"shmup": ["shmup/stage_recipe"],
	"run_and_gun": ["run_and_gun/stage_recipe"],
	"racing": ["racing/track_recipe"],
}

func _initialize() -> void:
	var code := _run()
	quit(code)

func _run() -> int:
	var here: Script = get_script()
	var builder_dir: String = here.resource_path.get_base_dir()
	var ctx := BuildContext.new(builder_dir, "build")
	if not ctx.load_inputs():
		ctx.results.write(Paths.RESULTS_BUILD)
		return 1
	ctx.load_build_state()
	var recipes := _recipe_list(ctx)
	_seed_example_recipe(ctx)
	var custom := custom_recipe_paths(CUSTOM_RECIPES_DIR)
	var total := recipes.size() + custom.size()  # one count for both, so the steps run 1..total
	for i in recipes.size():
		var recipe_name: String = recipes[i]
		Log.step("build", i + 1, total, _step_label(recipe_name))
		_run_recipe(ctx, builder_dir, recipe_name)
	_run_custom_recipes(ctx, custom, recipes.size(), total)
	var save_err := ctx.save_build_state()
	if save_err != OK:
		ctx.results.add_issue("BUILD-004", {"file": Paths.BUILD_STATE, "err": save_err}, Paths.BUILD_STATE)
	if OS.get_cmdline_user_args().has(UPDATE_LEDGER_FLAG):
		_update_ledger(ctx)
	ctx.results.write(Paths.RESULTS_BUILD)
	Log.info("build finished ok=%s" % str(ctx.results.ok))
	return 0 if ctx.results.ok else 1

## "turn_based/battle_scene_recipe" -> "battle scene": what the generator shows while it runs.
static func _step_label(recipe_name: String) -> String:
	return recipe_name.get_file().trim_suffix("_recipe").replace("_", " ")

## RECIPE_ORDER with the archetype's recipes inserted before "boot_recipe".
static func _recipe_list(ctx: BuildContext) -> Array:
	var archetype := JsonUtil.to_str(ctx.config.get("archetype", ""))
	var extra: Array = ARCHETYPE_RECIPES.get(archetype, [])
	var skips: Array = ARCHETYPE_SKIPS.get(archetype, [])
	var maps: Array = ARCHETYPE_MAPS.get(archetype, [])
	var out: Array = []
	for recipe_name in RECIPE_ORDER:
		if recipe_name == "boot_recipe":
			out.append_array(extra)
		if skips.has(recipe_name):
			if recipe_name == "starter_map_recipe":
				out.append_array(maps)  # the archetype's own maps, where the starter map would be
			continue
		out.append(recipe_name)
	return out

func _run_recipe(ctx: BuildContext, builder_dir: String, recipe_name: String) -> void:
	var script_path := "%s/recipes/%s.gd" % [builder_dir, recipe_name]
	var script: Variant = load(script_path)
	if script == null or not (script is GDScript):
		ctx.results.add_issue("BUILD-002", {"recipe": recipe_name, "reason": "recipe script failed to load"}, script_path)
		return
	var recipe_script: GDScript = script
	var recipe: RefCounted = recipe_script.new()
	var outs: PackedStringArray = recipe.call("outputs", ctx)
	var in_hash: String = recipe.call("input_hash", ctx)
	var all_skipped := outs.size() > 0
	for out in outs:
		if not ctx.should_skip(out, in_hash):
			all_skipped = false
	if all_skipped:
		for out in outs:
			ctx.results.add_item({"recipe": recipe_name, "output": _rel(out), "action": "skipped"})
		return
	Log.info("running %s" % recipe_name)
	var built: Variant = recipe.call("build", ctx)
	var failed := false
	if built is Array:
		var issue_list: Array = built
		ctx.results.add_issues(issue_list)
		for issue: Dictionary in issue_list:
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

## A new project gets a sample recipe that does nothing until its lines are uncommented (yours:
## a project whose folder exists is left alone, and a deleted sample is not brought back).
func _seed_example_recipe(ctx: BuildContext) -> void:
	if DirAccess.dir_exists_absolute(CUSTOM_RECIPES_DIR):
		return
	DirAccess.make_dir_recursive_absolute(CUSTOM_RECIPES_DIR)
	var f := FileAccess.open(EXAMPLE_RECIPE, FileAccess.WRITE)
	if f == null:
		ctx.results.add_issue("BUILD-004", {"file": EXAMPLE_RECIPE, "err": FileAccess.get_open_error()}, EXAMPLE_RECIPE)
		return
	f.store_string(EXAMPLE_TEXT)
	f.close()
	ctx.results.add_item({"recipe": "custom_recipes", "output": _rel(EXAMPLE_RECIPE), "action": "written"})
	# Its .uid too, with a fixed id: written after the import, the script would otherwise get a
	# random one at the next import, and a regeneration that changes nothing would change that.
	var uid_file := FileAccess.open(EXAMPLE_RECIPE + ".uid", FileAccess.WRITE)
	if uid_file != null:
		uid_file.store_string(ResourceUID.id_to_text(EXAMPLE_UID) + "\n")
		uid_file.close()
		ctx.results.add_item({"recipe": "custom_recipes", "output": _rel(EXAMPLE_RECIPE + ".uid"), "action": "written"})

## The .gd files of `dir_path`, sorted by name (not its sub folders).
static func custom_recipe_paths(dir_path: String) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	for file_name in dir.get_files():
		if file_name.ends_with(".gd"):
			found.append(dir_path.path_join(file_name))
	found.sort()
	return found

## Runs `recipes` (the custom ones) as build steps `first + 1` onwards of `total`.
func _run_custom_recipes(ctx: BuildContext, recipes: Array[String], first: int, total: int) -> void:
	if recipes.is_empty():
		return
	var errors := ScriptErrors.new()
	OS.add_logger(errors)
	for i in recipes.size():
		Log.step("build", first + i + 1, total, "your recipe " + recipes[i].get_file().get_basename())
		run_custom_recipe(ctx, recipes[i], errors)
	OS.remove_logger(errors)

## Runs one custom recipe; a recipe that does not load, has no build(ctx), logs a script error or
## calls ctx.fail() gives BUILD-002 naming it, and fails the build.
static func run_custom_recipe(ctx: BuildContext, path: String, errors: ScriptErrors) -> void:
	var recipe_name := path.get_file().get_basename()
	var label := _rel(path)  # "game/builder_recipes/my_npcs.gd": the message names the file
	var script := load(path) as GDScript
	if script == null or not script.can_instantiate():
		ctx.results.add_issue("BUILD-002", {"recipe": label, "reason": "the script does not load (see the log)"}, _rel(path))
		return
	var instance: Variant = script.new()
	var shape_error := "it must extend RefCounted and have func build(ctx) -> void"
	if not (instance is RefCounted):
		if instance is Node:
			var node: Node = instance
			node.free()
		ctx.results.add_issue("BUILD-002", {"recipe": label, "reason": shape_error}, _rel(path))
		return
	var recipe: RefCounted = instance
	if not recipe.has_method("build"):
		ctx.results.add_issue("BUILD-002", {"recipe": label, "reason": shape_error}, _rel(path))
		return
	Log.info("running %s" % label)
	var recipe_ctx := RecipeContext.new(ctx, recipe_name)
	var before := errors.count
	recipe.call("build", recipe_ctx)
	var problems: PackedStringArray = recipe_ctx.problems()
	if errors.count > before:
		problems.append("script error: %s" % errors.last)
	for out in recipe_ctx.written():
		ctx.results.add_item({"recipe": label, "output": _rel(out), "action": "failed" if not problems.is_empty() else "written"})
	if not problems.is_empty():
		ctx.results.add_issue("BUILD-002", {"recipe": label, "reason": "; ".join(problems)}, _rel(path))

const EXAMPLE_TEXT := """extends RefCounted
## Your own build step (rpggen custom recipe). rpggen runs every .gd file of this folder after its
## own recipes, on every build, in file-name order. Each must extend RefCounted and have
## func build(ctx) -> void. Write under res://game/ (yours, never rewritten) or
## res://generated/custom/ (rewritten on every build). docs/recipes.md lists what ctx offers.
##
## Uncomment the lines in build() to try it: the next build saves a small scene in
## res://generated/custom/.

const RecipeContext := preload("res://generated/builder/lib/recipe_context.gd")

func build(ctx: RecipeContext) -> void:
	# ctx.say("hello from %s" % ctx.recipe_name)
	# var sign := Node2D.new()
	# sign.name = "HelloSign"
	# var label := Label.new()
	# label.text = "Made by a custom recipe for " + ctx.project_name()
	# sign.add_child(label)
	# ctx.save_scene(sign, "res://generated/custom/hello_sign.tscn")
	pass
"""

## Records the hashes of the files this run wrote. Entries of user-owned files (game/) are never
## touched, and a file the run did not write keeps its entry: a change the user made to it must
## still show up as a conflict at the next regeneration.
func _update_ledger(ctx: BuildContext) -> void:
	var hasher: Resource = load(FILE_HASH)
	var ledger_value: Variant = JsonUtil.read(Paths.LEDGER) if FileAccess.file_exists(Paths.LEDGER) else null
	var ledger: Dictionary = {}
	if ledger_value is Dictionary:
		ledger = ledger_value
	if hasher == null or not (ledger.get("files") is Dictionary):
		ctx.results.add_issue("BUILD-002", {"recipe": "build.gd", "reason": "--update-ledger needs the tools addon and an ownership ledger"}, Paths.LEDGER)
		return
	var files: Dictionary = ledger["files"]
	var written := {}
	for item in ctx.results.items:
		if item.get("action", "") == "written":
			written[JsonUtil.to_str(item["output"])] = JsonUtil.to_str(item["recipe"])
	for rel in STATE_FILES:
		if files.has(rel):
			var state_entry: Dictionary = files[rel]
			written[rel] = JsonUtil.to_str(state_entry.get("written_by", "orchestrator"))
	var rels: Array = written.keys()
	rels.sort()
	for rel: String in rels:
		var entry: Variant = files.get(rel)
		var has_entry := entry is Dictionary
		var existing: Dictionary = {}
		if has_entry:
			existing = entry
		if has_entry and existing.get("owner", "") == "user_seed":
			continue
		if not FileAccess.file_exists("res://" + rel):
			continue
		var digest: String = JsonUtil.to_str(hasher.call("file_hash", "res://" + rel))
		if has_entry:
			existing["sha256"] = digest
		elif _covered(rel):
			files[rel] = {"sha256": digest, "written_by": written[rel], "owner": "generated"}
	var err := JsonUtil.write(Paths.LEDGER, ledger)
	if err != OK:
		ctx.results.add_issue("BUILD-004", {"file": Paths.LEDGER, "err": err}, Paths.LEDGER)

## Paths a new ledger entry may be created for (the ledger's covered generated-owned folders).
static func _covered(rel: String) -> bool:
	return rel.begins_with("generated/") or rel.begins_with("addons/") or rel.begins_with("rpggen/")

static func _rel(res_path: String) -> String:
	return res_path.trim_prefix("res://")
