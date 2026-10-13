extends RefCounted
## Takes a picture of a generated game while its own smoke sequence plays it: the pictures
## of the user guide (tools/make_doc_screenshots.py copies this file into a generated project and
## runs it). It is a steps script that hands on the steps of the kind and, a number of frames
## into one of them, saves what is on the screen. It needs a window, so the game is run without
## --headless:
##   godot --path <project> -- --rpg-smoke --rpg-smoke-steps=res://rpggen/doc_shot.gd
##       --rpg-doc-steps=res://generated/builder/smoke/smoke_steps_shmup.gd
##       --rpg-doc-step=second_wave_is_survived --rpg-doc-frames=120 --rpg-doc-out=<out.png>

var _taken := false
var _kinds: Array[RefCounted] = []  # the steps of the kind: kept, as their Callables are used

func _arg(arg_name: String, fallback: String) -> String:
	var prefix := "--rpg-doc-%s=" % arg_name
	for a in OS.get_cmdline_user_args():
		if String(a).begins_with(prefix):
			return String(a).trim_prefix(prefix)
	return fallback

func steps() -> Array[Dictionary]:
	# one script, or several with commas between them (the shared steps, then the kind's own)
	var provided: Array = []
	for path in _arg("steps", "").split(",", false):
		var script := load(path.strip_edges()) as GDScript
		if script == null:
			return []
		var kind: RefCounted = script.new()
		_kinds.append(kind)
		var its: Array = kind.call("steps")
		provided.append_array(its)
	var wanted := _arg("step", "")
	var out: Array[Dictionary] = []
	for step: Dictionary in provided:
		if String(step.get("name", "")) == wanted:
			var played: Callable = step["fn"]
			step = step.duplicate()
			step["fn"] = func() -> String:
				_shoot(int(_arg("frames", "120")))
				return await played.call()
		out.append(step)
	return out

func _shoot(frames: int) -> void:
	if _taken:  # a step that the sequence plays twice is on the picture the first time
		return
	_taken = true
	var tree := Engine.get_main_loop() as SceneTree
	for i in frames:
		await tree.process_frame
	await RenderingServer.frame_post_draw
	var image := tree.root.get_texture().get_image()
	var out := _arg("out", "user://game_shot.png")
	var err := image.save_png(out)
	print("[shot] saved %s: %d (%dx%d)" % [out, err, image.get_width(), image.get_height()])
