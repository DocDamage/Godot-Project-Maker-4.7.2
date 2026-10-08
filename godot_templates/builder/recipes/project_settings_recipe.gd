extends RefCounted
## Applies project settings from the generator config and saves project.godot.

const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const RECIPE_VERSION := 5

# Autoloads in registration order (T6): the runtime's singletons, nothing else.
const AUTOLOADS := [
	["Events", "res://addons/rpg_runtime/core/events.gd"],
	["GameState", "res://addons/rpg_runtime/core/game_state.gd"],
	["SaveManager", "res://addons/rpg_runtime/core/save_manager.gd"],
	["SceneRouter", "res://addons/rpg_runtime/world/scene_router.gd"],
	["RpgSettings", "res://addons/rpg_runtime/core/settings.gd"],
	["RpgSmoke", "res://addons/rpg_runtime/debug/smoke_runner.gd"],
]
# The editor plugin of the tools addon (T8.01); enabled when the addon is installed and the
# editor_tools feature is on.
const TOOLS_PLUGIN := "res://addons/rpg_project_tools/plugin.cfg"
const THEME_PATH := "res://generated/theme/main_theme.tres"
const BUS_LAYOUT_PATH := "res://generated/audio/default_bus_layout.tres"

# Physics layer names (ARCHITECTURE §17).
const PHYSICS_LAYER_NAMES := [
	"world", "player", "enemies", "npcs", "interactables",
	"triggers", "player_hitbox", "enemy_hitbox", "player_hurtbox", "enemy_hurtbox",
]

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray(["res://project.godot"])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({
		"v": RECIPE_VERSION,
		"name": ctx.config.get("project_name", ""),
		"resolution": ctx.config.get("resolution", []),
		"window_size": ctx.config.get("window_size", []),
		"input": ctx.config.get("input", {}),
		"seed": ctx.config.get("seed", 12345),
		"debug": JsonUtil.to_bool(ctx.section("features").get("debug_tools", false)),
		"tools_plugin": _wants_tools_plugin(ctx.config),
	})

func _wants_tools_plugin(cfg: Dictionary) -> bool:
	var features: Dictionary = cfg.get("features", {})
	return JsonUtil.to_bool(features.get("editor_tools", true)) and FileAccess.file_exists(TOOLS_PLUGIN)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var cfg: Dictionary = ctx.config
	var res: Array = cfg.get("resolution", [640, 360])
	var win: Array = cfg.get("window_size", [1280, 720])
	ProjectSettings.set_setting("application/config/name", str(cfg.get("project_name", "rpggen game")))
	if str(ProjectSettings.get_setting("application/config/version", "")) == "":
		ProjectSettings.set_setting("application/config/version", "0.1.0")  # the game's own number: change it when you like
	ProjectSettings.set_setting("application/run/main_scene", "res://generated/scenes/bootstrap/boot.tscn")
	ProjectSettings.set_setting("display/window/size/viewport_width", JsonUtil.to_int(res[0]))
	ProjectSettings.set_setting("display/window/size/viewport_height", JsonUtil.to_int(res[1]))
	ProjectSettings.set_setting("display/window/size/window_width_override", JsonUtil.to_int(win[0]))
	ProjectSettings.set_setting("display/window/size/window_height_override", JsonUtil.to_int(win[1]))
	ProjectSettings.set_setting("display/window/stretch/mode", "canvas_items")
	ProjectSettings.set_setting("display/window/stretch/aspect", "keep")
	ProjectSettings.set_setting("display/window/stretch/scale_mode", "integer")
	ProjectSettings.set_setting("rendering/textures/canvas_textures/default_texture_filter", 0)
	ProjectSettings.set_setting("rendering/2d/snap/snap_2d_transforms_to_pixel", true)
	ProjectSettings.set_setting("rendering/2d/snap/snap_2d_vertices_to_pixel", true)
	for i in PHYSICS_LAYER_NAMES.size():
		ProjectSettings.set_setting("layer_names/2d_physics/layer_%d" % (i + 1), PHYSICS_LAYER_NAMES[i])
	_apply_autoloads()
	_apply_tools_plugin(cfg)
	# The seed of the smoke test (used only with --rpg-smoke).
	ProjectSettings.set_setting("rpg/seed", JsonUtil.to_int(cfg.get("seed", 12345)))
	ProjectSettings.set_setting("gui/theme/custom", THEME_PATH)
	ProjectSettings.set_setting("audio/buses/default_bus_layout", BUS_LAYOUT_PATH)
	var configured_input: Dictionary = cfg.get("input", {})
	var input := configured_input.duplicate(true)
	var build_features: Dictionary = cfg.get("features", {})
	if JsonUtil.to_bool(build_features.get("debug_tools", false)):
		input["debug_toggle"] = {"keys": ["F3"]}
	_apply_input(ctx, input, issues)
	var err := ProjectSettings.save()
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": "project.godot", "err": err}, "project.godot"))
	return issues

## Adds the tools plugin to editor_plugins/enabled without touching the user's other plugins.
func _apply_tools_plugin(cfg: Dictionary) -> void:
	if not _wants_tools_plugin(cfg):
		return
	var enabled: PackedStringArray = ProjectSettings.get_setting("editor_plugins/enabled", PackedStringArray())
	if not enabled.has(TOOLS_PLUGIN):
		enabled.append(TOOLS_PLUGIN)
		ProjectSettings.set_setting("editor_plugins/enabled", enabled)

## Registers the runtime autoloads in order. RpgSmoke is inert unless the game is started with
## --rpg-smoke.
func _apply_autoloads() -> void:
	for i in AUTOLOADS.size():
		var key: String = "autoload/%s" % AUTOLOADS[i][0]
		ProjectSettings.set_setting(key, "*" + JsonUtil.to_str(AUTOLOADS[i][1]))
		ProjectSettings.set_order(key, 1000 + i)

func _apply_input(ctx: BuildContext, input: Dictionary, issues: Array) -> void:
	var actions: Array = input.keys()
	actions.sort()
	for action: String in actions:
		var binding: Dictionary = input[action]
		var events: Array = []
		var key_names: Array = binding.get("keys", [])
		for key_name: Variant in key_names:
			var code := OS.find_keycode_from_string(str(key_name))
			if code == 0:
				issues.append(ctx.make_issue("BUILD-002", {"recipe": "project_settings_recipe", "reason": "unknown key name \"%s\" for action %s" % [key_name, action]}))
				continue
			var ek := InputEventKey.new()
			ek.physical_keycode = code
			events.append(ek)
		var joy_buttons: Array = binding.get("joy_buttons", [])
		for button: Variant in joy_buttons:
			var jb := InputEventJoypadButton.new()
			jb.device = -1
			jb.button_index = JsonUtil.to_int(button)
			events.append(jb)
		var joy_axes: Array = binding.get("joy_axes", [])
		for axis: Array in joy_axes:
			var jm := InputEventJoypadMotion.new()
			jm.device = -1
			jm.axis = JsonUtil.to_int(axis[0])
			jm.axis_value = JsonUtil.to_float(axis[1])
			events.append(jm)
		var mouse_buttons: Array = binding.get("mouse_buttons", [])
		for button: Variant in mouse_buttons:
			var mb := InputEventMouseButton.new()
			mb.device = -1
			mb.button_index = JsonUtil.to_int(button)
			events.append(mb)
		ProjectSettings.set_setting("input/%s" % action, {"deadzone": 0.2, "events": events})
