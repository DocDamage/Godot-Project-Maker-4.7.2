extends Node
## Smoke-test driver, registered as the RpgSmoke autoload. Inert in normal play: it only acts when the
## game is started with  `-- --rpg-smoke --rpg-smoke-steps=res://path/to/steps.gd`.
##
## A steps script extends RefCounted and defines `func steps() -> Array[Dictionary]`; each step is
## {name: String, fn: Callable, timeout_s: float}. `fn` is a coroutine returning "" on success or an
## error string. A step may name the error code its failure is reported with (`code`, a code with
## the placeholders of SMOKE-001: the sequence of a kind of game that has its own); without one it
## is SMOKE-001.

const RESULTS_PATH := "res://rpggen/results/smoke_results.json"
const ERROR_CODES_PATH := "res://generated/builder/lib/error_codes.gd"
## Where the steps save when the run was given no name: `user://` is one folder for every
## project of one name, so two runs at one time that both saved here read and replaced each
## other's files (a save that "was not replaced", a `.tmp` that could not be moved into place).
const SAVE_ROOT := "user://smoke_saves"
## The argument that names a run (`--rpg-smoke-run=3fa9c2d1`, the generator's run id): its
## saves go into a folder of its own, which is emptied before the first step and removed after
## the last.
const RUN_ARG := "--rpg-smoke-run="

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

## The folder the steps of this run save into: never the player's saves, and never another
## run's. Every steps script sets `SaveManager.dir` to it.
static func save_dir() -> String:
	return save_dir_for(OS.get_cmdline_user_args())

## `save_dir()` for a list of arguments. A name is kept to letters, digits, `-` and `_` (it
## becomes part of a folder's name); a run without one saves into SAVE_ROOT, as every run did.
static func save_dir_for(args: PackedStringArray) -> String:
	for a in args:
		if not a.begins_with(RUN_ARG):
			continue
		var run := ""
		for ch: String in a.trim_prefix(RUN_ARG):
			if (ch >= "a" and ch <= "z") or (ch >= "A" and ch <= "Z") or (ch >= "0" and ch <= "9") or ch == "-" or ch == "_":
				run += ch
		if run != "":
			return "%s_%s" % [SAVE_ROOT, run.left(40)]
	return SAVE_ROOT

## Removes the files of `dir` and, when it is a run's own folder, the folder too (SAVE_ROOT is
## kept: it is shared, and was never removed).
static func clear_saves(dir: String) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for file: String in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir.path_join(file))
	if dir != SAVE_ROOT:
		DirAccess.remove_absolute(dir)

func _run(steps_path: String) -> void:
	if save_dir() != SAVE_ROOT:
		clear_saves(save_dir())  # a run that was killed left its folder behind
	var steps: Array = _load_steps(steps_path)
	var index := 0
	for step: Dictionary in steps:
		index += 1
		var started := Time.get_ticks_msec()
		var state := {"done": false, "result": ""}
		var step_fn: Callable = step["fn"]
		_exec(step_fn, state)
		var timeout_ms := int(RpgUtil.to_float(step.get("timeout_s", 10.0)) * 1000.0)
		while not state["done"] and Time.get_ticks_msec() - started < timeout_ms:
			await get_tree().process_frame
		var elapsed := Time.get_ticks_msec() - started
		if not state["done"]:
			_items.append({"step": index, "name": step["name"], "ok": false, "ms": elapsed, "detail": "timed out"})
			_issues.append(_issue("SMOKE-002", {"step": index}))
			break
		var detail := RpgUtil.to_str(state["result"])
		_items.append({"step": index, "name": step["name"], "ok": detail == "", "ms": elapsed, "detail": detail})
		if detail != "":
			var code := RpgUtil.to_str(step.get("code", "SMOKE-001"))
			_issues.append(_issue(code, {"step": index, "name": step["name"], "detail": detail}))
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
		var steps_script: GDScript = script
		var provider: RefCounted = steps_script.new()
		_providers.append(provider)
		var provided: Array = provider.call("steps")
		all.append_array(provided)
	return all

func _issue(code: String, detail: Dictionary) -> Dictionary:
	var severity := "error"
	var message := code
	var fix := ""
	if ResourceLoader.exists(ERROR_CODES_PATH):
		var codes_script: GDScript = load(ERROR_CODES_PATH)
		var codes: Dictionary = codes_script.get_script_constant_map()["CODES"]
		if codes.has(code):
			severity = codes[code]["severity"]
			message = codes[code]["message"]
			fix = codes[code]["fix"]
			for key: Variant in detail.keys():
				message = message.replace("{%s}" % str(key), str(detail[key]))
	return {"code": code, "severity": severity, "message": message, "fix": fix}

func _finish() -> void:
	var ok := true
	for issue: Dictionary in _issues:
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
	# last of all: the game runs on while the sound is let go, and a map that is entered then
	# writes its autosave
	if save_dir() != SAVE_ROOT:
		clear_saves(save_dir())
	get_tree().quit(0 if ok else 1)

## Stops every audio player and gives the mixer a moment to let go of the playbacks; a stream that is
## still playing at exit is reported by Godot as a resource still in use.
## A sound that begins while the mixer is given its moment (the music of the screen the last
## step opened, an explosion that was on its way) would be playing at exit after all, so the
## players are looked at again until a round finds none of them playing: an arcade game, which
## plays far more sounds than the others, ended that way now and then on a slow machine.
func _silence_audio() -> void:
	for _round in SILENCE_ROUNDS:
		var stopped := _stop_players()
		await get_tree().create_timer(0.3, true, false, true).timeout
		if stopped == 0:
			return

const SILENCE_ROUNDS := 6

## Stops every player of the tree and takes its stream; returns how many were playing.
func _stop_players() -> int:
	var playing := 0
	var pending: Array[Node] = [get_tree().root]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		pending.append_array(node.get_children())
		if node is AudioStreamPlayer or node is AudioStreamPlayer2D:
			if node.get("playing"):
				playing += 1
			node.call("stop")
			node.set("stream", null)
	return playing

