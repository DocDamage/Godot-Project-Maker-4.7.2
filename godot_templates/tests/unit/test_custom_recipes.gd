extends RefCounted
## Custom recipes (T12.60): res://game/builder_recipes/*.gd run after rpggen's own recipes.

const Build := preload("res://builder/build.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const RecipeContext := preload("res://builder/lib/recipe_context.gd")
const OUT_DIR := "res://generated/custom/test_custom_recipes"

static func _ctx() -> BuildContext:
	var ctx := BuildContext.new("res://builder", "build")
	ctx.config = {"project_name": "Recipe Test", "seed": 7, "base_tile_size": 16}
	return ctx

static func _recipe_dir() -> String:
	var dir := "user://test_custom_recipes_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(dir)
	return dir

static func _write(path: String, text: String) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(text)
	f.close()

static func _clean(dir: String) -> void:
	for folder: String in [dir, OUT_DIR]:
		var d := DirAccess.open(folder)
		if d == null:
			continue
		for file_name in d.get_files():
			DirAccess.remove_absolute(folder.path_join(file_name))
		DirAccess.remove_absolute(folder)

const SCENE_RECIPE := """extends RefCounted
func build(ctx: RefCounted) -> void:
	var root := Node2D.new()
	root.name = "FromRecipe"
	var label := Label.new()
	label.text = str(ctx.call("project_name"))
	root.add_child(label)
	ctx.call("save_scene", root, "%s/made.tscn")
"""

func test_a_custom_recipe_creates_a_scene(t) -> void:
	var dir := _recipe_dir()
	_write(dir.path_join("make_scene.gd"), SCENE_RECIPE % OUT_DIR)
	var ctx := _ctx()
	Build.run_custom_recipe(ctx, dir.path_join("make_scene.gd"), Build.ScriptErrors.new())
	t.ok(ctx.results.ok, str(ctx.results.issues))
	var scene := load(OUT_DIR + "/made.tscn") as PackedScene
	t.ok(scene != null, "the scene was saved")
	if scene != null:
		var node := scene.instantiate()
		t.eq(node.name, &"FromRecipe")
		t.eq((node.get_child(0) as Label).text, "Recipe Test", "the recipe read the config")
		node.free()
	var outputs: Array = []
	for item: Dictionary in ctx.results.items:
		outputs.append([item["output"], item["action"]])
	t.eq(outputs, [[OUT_DIR.trim_prefix("res://") + "/made.tscn", "written"]])
	_clean(dir)

func test_a_failing_recipe_is_reported_by_name_and_fails_the_build(t) -> void:
	var dir := _recipe_dir()
	_write(dir.path_join("refuses.gd"), "extends RefCounted\nfunc build(ctx: RefCounted) -> void:\n\tctx.call(\"fail\", \"no NPC sprites to use\")\n")
	_write(dir.path_join("no_build.gd"), "extends RefCounted\nfunc make() -> void:\n\tpass\n")
	_write(dir.path_join("escapes.gd"), "extends RefCounted\nfunc build(ctx: RefCounted) -> void:\n\tctx.call(\"write_text\", \"res://addons/evil.txt\", \"x\")\n")
	var ctx := _ctx()
	for file_name: String in ["refuses.gd", "no_build.gd", "escapes.gd"]:
		Build.run_custom_recipe(ctx, dir.path_join(file_name), Build.ScriptErrors.new())
	t.ok(not ctx.results.ok, "a failing recipe fails the build")
	var messages: Array = []
	for issue: Dictionary in ctx.results.issues:
		t.eq(issue["code"], "BUILD-002")
		messages.append(issue["message"])
	t.eq(messages.size(), 3)
	t.ok(str(messages[0]).contains("refuses.gd") and str(messages[0]).contains("no NPC sprites to use"), str(messages[0]))
	t.ok(str(messages[1]).contains("no_build.gd") and str(messages[1]).contains("func build"), str(messages[1]))
	t.ok(str(messages[2]).contains("escapes.gd") and str(messages[2]).contains("outside"), str(messages[2]))
	t.ok(not FileAccess.file_exists("res://addons/evil.txt"), "nothing was written outside")
	_clean(dir)

func test_recipes_run_in_name_order(t) -> void:
	var dir := _recipe_dir()
	var appender := """extends RefCounted
func build(ctx: RefCounted) -> void:
	var path := "%s/order.txt"
	var before := FileAccess.get_file_as_string(path) if FileAccess.file_exists(path) else ""
	ctx.call("write_text", path, before + str(ctx.get("recipe_name")) + "\\n")
"""
	for file_name: String in ["b_second.gd", "c_third.gd", "a_first.gd"]:
		_write(dir.path_join(file_name), appender % OUT_DIR)
	_write(dir.path_join("notes.txt"), "not a recipe")
	var paths := Build.custom_recipe_paths(dir)
	t.eq(paths.map(func(p: String) -> String: return p.get_file()), ["a_first.gd", "b_second.gd", "c_third.gd"])
	var ctx := _ctx()
	for path in paths:
		Build.run_custom_recipe(ctx, path, Build.ScriptErrors.new())
	t.eq(FileAccess.get_file_as_string(OUT_DIR + "/order.txt"), "a_first\nb_second\nc_third\n")
	t.eq(Build.custom_recipe_paths("user://no_such_recipes"), [])
	_clean(dir)

func test_the_context_api_is_versioned_and_guards_its_paths(t) -> void:
	t.eq(RecipeContext.RECIPE_API_VERSION, 1)
	var ctx := RecipeContext.new(_ctx(), "x")
	t.eq(ctx.api_version, 1)
	t.eq(ctx.rng_seed, 7)
	t.eq(ctx.tile_size(), 16)
	t.ok(RecipeContext.allowed("res://game/data/my.tres"))
	t.ok(RecipeContext.allowed("res://generated/custom/a/b.tscn"))
	t.ok(not RecipeContext.allowed("res://generated/scenes/ui/title_screen.tscn"))
	t.ok(not RecipeContext.allowed("res://game/../addons/x.gd"))
	t.eq(ctx.assets(), [])
