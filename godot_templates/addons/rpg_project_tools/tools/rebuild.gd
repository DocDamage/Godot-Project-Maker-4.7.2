@tool
extends RefCounted
## Regenerates the affected resources from inside the editor (T8.05): saves the open scenes,
## runs the builder as a headless subprocess and rescans the file system. The builder only writes
## generated-owned files whose recipe hash changed; it does not run promotion. With
## --update-ledger it records the hashes of the files it wrote, so the next regeneration from the
## wizard does not take them for user edits.

const JsonIo := preload("json_io.gd")

const BUILD_SCRIPT := "res://generated/builder/build.gd"
const RESULTS_PATH := "res://rpggen/results/build_results.json"
const RPGGEN_SETTING := "rpg_tools/rpggen_executable"

## The Godot executable that runs the build: the console build next to the editor when there is
## one (the GUI build has no stdout), else the editor itself.
static func godot_executable() -> String:
	var exe := OS.get_executable_path()
	if exe.get_extension().to_lower() == "exe":
		var console := exe.get_basename() + "_console.exe"
		if FileAccess.file_exists(console):
			return console
	return exe

static func build_arguments() -> PackedStringArray:
	return PackedStringArray([
		"--headless", "--path", ProjectSettings.globalize_path("res://"),
		"--script", BUILD_SCRIPT, "--", "--update-ledger",
	])

## The issues of the last build, from build_results.json ([] when there is none).
static func read_issues() -> Array:
	var data: Variant = JsonIo.read(RESULTS_PATH)
	if data is Dictionary:
		var results: Dictionary = data
		if results.get("issues") is Array:
			var listed: Array = results["issues"]
			return listed
	return []

static func has_errors(issues: Array) -> bool:
	for issue: Dictionary in issues:
		if issue.get("severity", "") == "error":
			return true
	return false

## Runs the builder and waits for it. Returns {ok, exit_code, issues, output}.
static func run_build(executable: String = "") -> Dictionary:
	var output: Array = []
	var exit_code := OS.execute(executable if executable != "" else godot_executable(), build_arguments(), output, true)
	var issues := read_issues() if exit_code >= 0 else []
	var text := "\n".join(PackedStringArray(output.map(func(o: Variant) -> String: return str(o))))
	if exit_code < 0:
		issues = [{"code": "BUILD-002", "severity": "error", "message": "Recipe build.gd failed: the Godot process could not be started.", "file": ""}]
	return {"ok": exit_code == 0 and not has_errors(issues), "exit_code": exit_code, "issues": issues, "output": text}

## Editor only: save the scenes, build, rescan.
static func regenerate() -> Dictionary:
	EditorInterface.save_all_scenes()
	var result := run_build()
	EditorInterface.get_resource_filesystem().scan()
	return result

## The wizard command line: [executable, "--target", project]. "" executable when the editor
## setting rpg_tools/rpggen_executable is empty.
static func generator_command(executable: String, project_path: String) -> PackedStringArray:
	if executable.strip_edges() == "":
		return PackedStringArray()
	return PackedStringArray([executable, "--target", project_path])

static func generator_executable() -> String:
	var settings := EditorInterface.get_editor_settings()
	if settings.has_setting(RPGGEN_SETTING):
		return str(settings.get_setting(RPGGEN_SETTING))
	return ""

## Starts the wizard on this project. Returns the process id, or -1 when no executable is set
## (the caller shows instructions then).
static func open_generator() -> int:
	var command := generator_command(generator_executable(), ProjectSettings.globalize_path("res://").trim_suffix("/"))
	if command.is_empty():
		return -1
	return OS.create_process(command[0], command.slice(1))
