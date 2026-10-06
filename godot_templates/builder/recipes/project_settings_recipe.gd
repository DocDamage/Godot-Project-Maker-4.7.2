extends RefCounted
## Applies project settings from the generator config and saves project.godot.

const RECIPE_VERSION := 1

# Physics layer names (ARCHITECTURE §17).
const PHYSICS_LAYER_NAMES := [
	"world", "player", "enemies", "npcs", "interactables",
	"triggers", "player_hitbox", "enemy_hitbox", "player_hurtbox", "enemy_hurtbox",
]

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray(["res://project.godot"])

func input_hash(ctx) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"name": ctx.config.get("project_name", ""),
		"resolution": ctx.config.get("resolution", []),
		"window_size": ctx.config.get("window_size", []),
		"input": ctx.config.get("input", {}),
	})

func build(ctx) -> Array:
	var issues: Array = []
	var cfg: Dictionary = ctx.config
	var res: Array = cfg.get("resolution", [640, 360])
	var win: Array = cfg.get("window_size", [1280, 720])
	ProjectSettings.set_setting("application/config/name", str(cfg.get("project_name", "rpggen game")))
	ProjectSettings.set_setting("application/run/main_scene", "res://generated/scenes/bootstrap/boot.tscn")
	ProjectSettings.set_setting("display/window/size/viewport_width", int(res[0]))
	ProjectSettings.set_setting("display/window/size/viewport_height", int(res[1]))
	ProjectSettings.set_setting("display/window/size/window_width_override", int(win[0]))
	ProjectSettings.set_setting("display/window/size/window_height_override", int(win[1]))
	ProjectSettings.set_setting("display/window/stretch/mode", "canvas_items")
	ProjectSettings.set_setting("display/window/stretch/aspect", "keep")
	ProjectSettings.set_setting("display/window/stretch/scale_mode", "integer")
	ProjectSettings.set_setting("rendering/textures/canvas_textures/default_texture_filter", 0)
	ProjectSettings.set_setting("rendering/2d/snap/snap_2d_transforms_to_pixel", true)
	ProjectSettings.set_setting("rendering/2d/snap/snap_2d_vertices_to_pixel", true)
	for i in PHYSICS_LAYER_NAMES.size():
		ProjectSettings.set_setting("layer_names/2d_physics/layer_%d" % (i + 1), PHYSICS_LAYER_NAMES[i])
	_apply_input(ctx, cfg.get("input", {}), issues)
	var err := ProjectSettings.save()
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": "project.godot", "err": err}, "project.godot"))
	return issues

func _apply_input(ctx, input: Dictionary, issues: Array) -> void:
	var actions: Array = input.keys()
	actions.sort()
	for action in actions:
		var binding: Dictionary = input[action]
		var events: Array = []
		for key_name in binding.get("keys", []):
			var code := OS.find_keycode_from_string(str(key_name))
			if code == 0:
				issues.append(ctx.make_issue("BUILD-002", {"recipe": "project_settings_recipe", "reason": "unknown key name \"%s\" for action %s" % [key_name, action]}))
				continue
			var ek := InputEventKey.new()
			ek.physical_keycode = code
			events.append(ek)
		for button in binding.get("joy_buttons", []):
			var jb := InputEventJoypadButton.new()
			jb.device = -1
			jb.button_index = int(button)
			events.append(jb)
		for axis in binding.get("joy_axes", []):
			var jm := InputEventJoypadMotion.new()
			jm.device = -1
			jm.axis = int(axis[0])
			jm.axis_value = float(axis[1])
			events.append(jm)
		for button in binding.get("mouse_buttons", []):
			var mb := InputEventMouseButton.new()
			mb.device = -1
			mb.button_index = int(button)
			events.append(mb)
		ProjectSettings.set_setting("input/%s" % action, {"deadzone": 0.2, "events": events})
