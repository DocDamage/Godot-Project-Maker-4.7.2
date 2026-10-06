extends SceneTree
# Minimal in-house test runner.
# Run: godot --headless --path <proj> --script res://tests/run_tests.gd
# Finds res://tests/unit/**/test_*.gd, runs every method named test_* with a fresh T helper.

const T := preload("lib/t.gd")
const UNIT_DIR := "res://tests/unit"
const RESULTS_PATH := "res://tests/results.json"

func _initialize() -> void:
	var passed := 0
	var failed := 0
	var failures: Array = []
	for path in _list_tests(UNIT_DIR):
		var script: Variant = load(path)
		if script == null or not (script is GDScript):
			failed += 1
			failures.append("%s: failed to load" % path)
			print("FAIL %s: failed to load" % path)
			continue
		var inst: Object = script.new()
		var names: Array = []
		for m in inst.get_method_list():
			if String(m["name"]).begins_with("test_"):
				names.append(String(m["name"]))
		names.sort()
		for method_name in names:
			var t := T.new()
			inst.call(method_name, t)
			if t.failures.is_empty():
				passed += 1
				print("PASS %s::%s" % [path, method_name])
			else:
				failed += 1
				var line := "%s::%s: %s" % [path, method_name, "; ".join(t.failures)]
				failures.append(line)
				print("FAIL %s" % line)
	print("tests: %d passed, %d failed" % [passed, failed])
	var results := {"passed": passed, "failed": failed, "failures": failures}
	var f := FileAccess.open(RESULTS_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(results, "  ", true) + "\n")
		f.close()
	quit(0 if failed == 0 else 1)

func _list_tests(dir_path: String) -> Array:
	var found: Array = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	var entries: Array = []
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		entries.append([name, dir.current_is_dir()])
		name = dir.get_next()
	dir.list_dir_end()
	entries.sort_custom(func(a: Array, b: Array) -> bool: return String(a[0]) < String(b[0]))
	for e in entries:
		var full: String = dir_path + "/" + e[0]
		if e[1]:
			found.append_array(_list_tests(full))
		elif String(e[0]).begins_with("test_") and String(e[0]).ends_with(".gd"):
			found.append(full)
	return found
