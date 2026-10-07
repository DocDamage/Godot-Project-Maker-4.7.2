extends Node
## Smoke-test driver, registered as the RpgSmoke autoload. Inert in normal play: it only acts when the
## game is started with  `-- --rpg-smoke --rpg-smoke-steps=res://path/to/steps.gd`.
##
## A steps script extends RefCounted and defines `func steps() -> Array[Dictionary]`; each step is
## {name: String, fn: Callable, timeout_s: float}. `fn` is a coroutine returning "" on success or an
## error string.

const RESULTS_PATH := "res://rpggen/results/smoke_results.json"
const ERROR_CODES_PATH := "res://generated/builder/lib/error_codes.gd"

var _items: Array = []
var _providers: Array = []  # keeps the steps objects (and their Callables) alive
var _issues: Array = []

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.has("--rpg-smoke"):
		queue_free()
		return
	var steps_path := ""
	for a in args:
		if String(a).begins_with("--rpg-smoke-steps="):
			steps_path = String(a).trim_prefix("--rpg-smoke-steps=")
	_run(steps_path)

func _run(steps_path: String) -> void:
	var steps: Array = _load_steps(steps_path)
	var index := 0
	for step in steps:
		index += 1
		var started := Time.get_ticks_msec()
		var state := {"done": false, "result": ""}
		_exec(step["fn"], state)
		var timeout_ms := int(float(step.get("timeout_s", 10.0)) * 1000.0)
		while not state["done"] and Time.get_ticks_msec() - started < timeout_ms:
			await get_tree().process_frame
		var elapsed := Time.get_ticks_msec() - started
		if not state["done"]:
			_items.append({"step": index, "name": step["name"], "ok": false, "ms": elapsed, "detail": "timed out"})
			_issues.append(_issue("SMOKE-002", {"step": index}))
			break
		var detail := String(state["result"])
		_items.append({"step": index, "name": step["name"], "ok": detail == "", "ms": elapsed, "detail": detail})
		if detail != "":
			_issues.append(_issue("SMOKE-001", {"step": index, "name": step["name"], "detail": detail}))
			break
	_finish()

func _exec(fn: Callable, state: Dictionary) -> void:
	state["result"] = await fn.call()
	state["done"] = true

## `steps_path` is one script or a comma-separated list; the steps run in that order.
func _load_steps(steps_path: String) -> Array:
	var all: Array = []
	var paths := steps_path.split(",", false)
	if paths.is_empty():
		_issues.append(_issue("SMOKE-001", {"step": 0, "name": "load_steps", "detail": "no steps script given"}))
		return []
	for path in paths:
		if not ResourceLoader.exists(path):
			_issues.append(_issue("SMOKE-001", {"step": 0, "name": "load_steps", "detail": "steps script not found: %s" % path}))
			return []
		var script: Variant = load(path)
		if script == null or not (script is GDScript):
			_issues.append(_issue("SMOKE-001", {"step": 0, "name": "load_steps", "detail": "steps script failed to load: %s" % path}))
			return []
		var provider: RefCounted = script.new()
		_providers.append(provider)
		all.append_array(provider.steps())
	return all

func _issue(code: String, detail: Dictionary) -> Dictionary:
	var severity := "error"
	var message := code
	var fix := ""
	if ResourceLoader.exists(ERROR_CODES_PATH):
		var codes: Dictionary = load(ERROR_CODES_PATH).CODES
		if codes.has(code):
			severity = codes[code]["severity"]
			message = codes[code]["message"]
			fix = codes[code]["fix"]
			for key in detail.keys():
				message = message.replace("{%s}" % str(key), str(detail[key]))
	return {"code": code, "severity": severity, "message": message, "fix": fix}

func _finish() -> void:
	var ok := true
	for issue in _issues:
		if issue["severity"] == "error":
			ok = false
	var data := {
		"results_version": 1,
		"phase": "smoke",
		"ok": ok,
		"started_ms": 0,
		"elapsed_ms": Time.get_ticks_msec(),
		"issues": _issues,
		"items": _items,
	}
	DirAccess.make_dir_recursive_absolute(RESULTS_PATH.get_base_dir())
	var f := FileAccess.open(RESULTS_PATH, FileAccess.WRITE)
	if f == null:
		push_error("[RPG-SMOKE] cannot write %s" % RESULTS_PATH)
		get_tree().quit(1)
		return
	f.store_string(JSON.stringify(data, "  ", true) + "\n")
	f.close()
	print("[rpggen] INFO smoke finished ok=%s" % str(ok))
	await _silence_audio()
	get_tree().quit(0 if ok else 1)

## Stops every audio player and gives the mixer a moment to let go of the playbacks; a stream that is
## still playing at exit is reported by Godot as a resource still in use.
func _silence_audio() -> void:
	var pending: Array[Node] = [get_tree().root]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		pending.append_array(node.get_children())
		if node is AudioStreamPlayer or node is AudioStreamPlayer2D:
			node.call("stop")
			node.set("stream", null)
	await get_tree().create_timer(0.3, true, false, true).timeout

