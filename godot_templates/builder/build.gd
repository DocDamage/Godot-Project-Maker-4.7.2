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
	"object_scenes_recipe",
	"interior_recipe",
	"theme_recipe",
	"ui_recipes",
	"audio_bus_recipe",
	"boot_recipe",
	"starter_map_recipe",
	"second_map_recipe",
	"translations_recipe",
]

## Recipes of the archetype's folder (builder/recipes/<archetype>/), run before the boot scene is
## built because boot adds the archetype's combat mode.
const ARCHETYPE_RECIPES := {
	"turn_based": ["turn_based/battle_commands_recipe", "turn_based/enemy_recipes", "turn_based/battle_scene_recipe"],
	"arpg": ["arpg/swing_recipe", "arpg/enemy_recipes", "arpg/hud_recipe", "arpg/mode_recipe"],
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
	for i in recipes.size():
		var recipe_name: String = recipes[i]
		Log.step("build", i + 1, recipes.size(), _step_label(recipe_name))
		_run_recipe(ctx, builder_dir, recipe_name)
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
	var extra: Array = ARCHETYPE_RECIPES.get(JsonUtil.to_str(ctx.config.get("archetype", "")), [])
	var out: Array = []
	for recipe_name in RECIPE_ORDER:
		if recipe_name == "boot_recipe":
			out.append_array(extra)
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
