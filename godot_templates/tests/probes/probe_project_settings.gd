extends SceneTree
# Probe: every ProjectSettings key used by project_settings_recipe is a registered engine setting
# (checked BEFORE setting it), input events can be built, and save_custom() writes them.

const KEYS := [
	"application/config/name",
	"application/run/main_scene",
	"display/window/size/viewport_width",
	"display/window/size/viewport_height",
	"display/window/size/window_width_override",
	"display/window/size/window_height_override",
	"display/window/stretch/mode",
	"display/window/stretch/aspect",
	"display/window/stretch/scale_mode",
	"rendering/textures/canvas_textures/default_texture_filter",
	"rendering/2d/snap/snap_2d_transforms_to_pixel",
	"rendering/2d/snap/snap_2d_vertices_to_pixel",
	"layer_names/2d_physics/layer_1",
	"layer_names/2d_physics/layer_10",
	"physics/common/physics_ticks_per_second",
]

func _initialize() -> void:
	for k in KEYS:
		print("PROBE setting_registered: ", k, " = ", ProjectSettings.has_setting(k))
	print("PROBE keycode_W: ", OS.find_keycode_from_string("W"), " (KEY_W=", KEY_W, ")")
	print("PROBE keycode_Up: ", OS.find_keycode_from_string("Up"), " (KEY_UP=", KEY_UP, ")")
	print("PROBE keycode_Space: ", OS.find_keycode_from_string("Space"), " (KEY_SPACE=", KEY_SPACE, ")")
	print("PROBE keycode_Enter: ", OS.find_keycode_from_string("Enter"), " (KEY_ENTER=", KEY_ENTER, ")")
	print("PROBE keycode_Escape: ", OS.find_keycode_from_string("Escape"), " (KEY_ESCAPE=", KEY_ESCAPE, ")")
	print("PROBE keycode_Backspace: ", OS.find_keycode_from_string("Backspace"), " (KEY_BACKSPACE=", KEY_BACKSPACE, ")")
	print("PROBE keycode_Tab: ", OS.find_keycode_from_string("Tab"), " (KEY_TAB=", KEY_TAB, ")")
	print("PROBE keycode_Shift: ", OS.find_keycode_from_string("Shift"), " (KEY_SHIFT=", KEY_SHIFT, ")")
	print("PROBE keycode_unknown: ", OS.find_keycode_from_string("NotAKey"))

	var e := InputEventKey.new()
	e.physical_keycode = OS.find_keycode_from_string("W")
	var jb := InputEventJoypadButton.new()
	jb.button_index = JOY_BUTTON_DPAD_UP
	var jm := InputEventJoypadMotion.new()
	jm.axis = JOY_AXIS_LEFT_Y
	jm.axis_value = -1.0
	var mb := InputEventMouseButton.new()
	mb.button_index = MOUSE_BUTTON_LEFT
	ProjectSettings.set_setting("input/probe_action", {"deadzone": 0.2, "events": [e, jb, jm, mb]})
	ProjectSettings.set_setting("layer_names/2d_physics/layer_1", "world")
	print("PROBE joy_button_dpad_up: ", JOY_BUTTON_DPAD_UP, " (spec table says 11)")
	print("PROBE joy_button_dpad_down/left/right: ", JOY_BUTTON_DPAD_DOWN, " ", JOY_BUTTON_DPAD_LEFT, " ", JOY_BUTTON_DPAD_RIGHT)
	print("PROBE joy_button_a/b/x/y/start/rb: ", JOY_BUTTON_A, " ", JOY_BUTTON_B, " ", JOY_BUTTON_X, " ", JOY_BUTTON_Y, " ", JOY_BUTTON_START, " ", JOY_BUTTON_RIGHT_SHOULDER)
	var out_path := ProjectSettings.globalize_path("user://probe_project.godot")
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var err := ProjectSettings.save_custom(out_path)
	print("PROBE save_custom: ", err)
	print(FileAccess.get_file_as_string(out_path))
	DirAccess.remove_absolute(out_path)
	quit(0)
