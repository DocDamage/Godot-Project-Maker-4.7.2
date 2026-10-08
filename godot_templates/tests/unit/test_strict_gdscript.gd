extends RefCounted
## T12.29: the template project turns the untyped_declaration and unsafe_* warnings into errors
## (project.godot, tests/ excluded). A script that breaks them does not load, so loading every
## script under addons/ and builder/ is the check; the error text is in the log.

const ROOTS: Array[String] = ["res://addons", "res://builder"]

func _scripts(dir_path: String, out: Array[String]) -> void:
	for sub: String in DirAccess.get_directories_at(dir_path):
		_scripts(dir_path.path_join(sub), out)
	for file: String in DirAccess.get_files_at(dir_path):
		if file.ends_with(".gd"):
			out.append(dir_path.path_join(file))

func test_every_runtime_and_builder_script_compiles_under_the_strict_settings(t) -> void:
	var paths: Array[String] = []
	for root: String in ROOTS:
		_scripts(root, paths)
	paths.sort()
	t.ok(paths.size() > 100, "found %d scripts" % paths.size())
	for path: String in paths:
		var script := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_IGNORE) as GDScript
		t.ok(script != null and script.can_instantiate(), "%s does not compile" % path)

func test_the_warnings_are_errors_in_the_project_settings(t) -> void:
	for name: String in ["untyped_declaration", "unsafe_property_access", "unsafe_method_access", "unsafe_cast", "unsafe_call_argument"]:
		t.eq(ProjectSettings.get_setting("debug/gdscript/warnings/" + name), 2, name)
