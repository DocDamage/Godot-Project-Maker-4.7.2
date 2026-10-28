extends SceneTree
# Minimal in-house test runner.
# Run: godot --headless --path <proj> --script res://tests/run_tests.gd
# Finds res://tests/unit/**/test_*.gd, runs every method named test_* with a fresh T helper.
# A test that awaits is waited for (up to TEST_TIMEOUT_MS). A GDScript runtime error (SCRIPT ERROR)
# aborts the function it happens in, so a test that logs one fails even when its checks passed.
# At the end, "godot:" lines sum up the errors Godot logged (push_error and push_warning counted
# apart: many tests trigger those on purpose).

const T := preload("lib/t.gd")
const UNIT_DIR := "res://tests/unit"
const RESULTS_PATH := "res://tests/results.json"
const TEST_TIMEOUT_MS := 20000
const SUMMARY_LINES := 10

## Collects what Godot logs, tagged with the test that was running. Called from any thread.
class ErrorLog extends Logger:
	var current := "<runner>"
	var script_errors: Array[String] = []  # "message (file:line)"
	var engine: Array[Array] = []  # [kind, message, script line, test]: not from push_*
	var pushed := 0
	var _mutex := Mutex.new()

	func _log_error(function: String, file: String, line: int, code: String, rationale: String,
			_editor_notify: bool, error_type: int, script_backtraces: Array[ScriptBacktrace]) -> void:
		var text := rationale if rationale != "" else code
		var where := ""
		for bt in script_backtraces:
			if bt.get_frame_count() > 0:
				where = "%s:%d" % [bt.get_frame_file(0), bt.get_frame_line(0)]
				break
		_mutex.lock()
		if error_type == ERROR_TYPE_SCRIPT:
			script_errors.append("%s (%s:%d)" % [text, file, line])
		elif function == "push_error" or function == "push_warning":
			pushed += 1
		else:
			engine.append(["warning" if error_type == ERROR_TYPE_WARNING else "error", text, where, current])
		_mutex.unlock()

	func _log_message(_message: String, _error: bool) -> void:
		pass

	func script_error_count() -> int:
		_mutex.lock()
		var n := script_errors.size()
		_mutex.unlock()
		return n

	func script_errors_since(start: int) -> Array[String]:
		_mutex.lock()
		var found := script_errors.slice(start)
		_mutex.unlock()
		return found

var _log := ErrorLog.new()

func _initialize() -> void:
	OS.add_logger(_log)
	_run()

func _run() -> void:
	var passed := 0
	var failed := 0
	var failures: Array = []
	for path in _list_tests(UNIT_DIR):
		_log.current = path
		var script: Variant = load(path)
		# a file that loads but does not compile cannot be made (and new() would stop the run)
		if script == null or not (script is GDScript) or not (script as GDScript).can_instantiate():
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
			_log.current = "%s::%s" % [path, method_name]
			var t := T.new()
			var errors_before := _log.script_error_count()
			var returned: Variant = inst.call(method_name, t)
			if returned is Object and (returned as Object).get_class() == "GDScriptFunctionState":
				if not await _finish(returned, errors_before):
					t.fail("did not finish within %d ms" % TEST_TIMEOUT_MS)
			await process_frame  # deferred calls the test queued run now, still counted as its own
			for err in _log.script_errors_since(errors_before):
				t.fail("script error: %s" % err)
			if t.failures.is_empty():
				passed += 1
				print("PASS %s::%s" % [path, method_name])
			else:
				failed += 1
				var line := "%s::%s: %s" % [path, method_name, "; ".join(t.failures)]
				failures.append(line)
				print("FAIL %s" % line)
	_log.current = "<runner>"
	print("tests: %d passed, %d failed" % [passed, failed])
	_print_summary()
	var results := {"passed": passed, "failed": failed, "failures": failures}
	var f := FileAccess.open(RESULTS_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(results, "  ", true) + "\n")
		f.close()
	OS.remove_logger(_log)
	quit(0 if failed == 0 else 1)

## Waits for a test that awaited (`state` is its GDScriptFunctionState). True when it returned; false when it timed out. A script error
## after the await stops it for good, so that ends the wait too (the error fails the test).
func _finish(state: Object, errors_before: int) -> bool:
	var done := [false]
	state.connect(&"completed", func(_result: Variant) -> void: done[0] = true)
	var deadline := Time.get_ticks_msec() + TEST_TIMEOUT_MS
	while not done[0]:
		if _log.script_error_count() > errors_before:
			return true
		if Time.get_ticks_msec() > deadline:
			return false
		await process_frame
	return true

## "godot:" lines: how many errors Godot logged, and the engine ones (not push_error or
## push_warning) grouped by message, with the first test that caused each.
func _print_summary() -> void:
	var counts := {}
	var first := {}
	var order: Array[String] = []
	var errors := 0
	for e in _log.engine:
		var key := "%s: %s" % [e[0], e[1]]
		if e[2] != "":
			key += " at " + e[2]
		if e[0] == "error":
			errors += 1
		if not counts.has(key):
			counts[key] = 0
			first[key] = e[3]
			order.append(key)
		counts[key] += 1
	print("godot: %d script errors, %d engine errors, %d engine warnings, %d from push_error/push_warning" % [
			_log.script_errors.size(), errors, _log.engine.size() - errors, _log.pushed])
	for i in mini(order.size(), SUMMARY_LINES):
		var key := order[i]
		print("godot:   %dx %s [%s]" % [counts[key], key, first[key]])
	if order.size() > SUMMARY_LINES:
		print("godot:   ... and %d more" % (order.size() - SUMMARY_LINES))

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
			# RPGGEN_TEST_ONLY="test_a,test_b" runs only the files whose name holds one of them
			var only := OS.get_environment("RPGGEN_TEST_ONLY")
			if only == "" or Array(only.split(",")).any(func(w: String) -> bool: return w in String(e[0])):
				found.append(full)
	return found
