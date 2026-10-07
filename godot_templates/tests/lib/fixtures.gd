extends RefCounted
## Test helpers that stand in for the autoloads of a generated project (the template project does
## not register any). Nodes are added under /root with the autoload names.

const EVENTS := "res://addons/rpg_runtime/core/events.gd"
const GAME_STATE := "res://addons/rpg_runtime/core/game_state.gd"
const SAVE_MANAGER := "res://addons/rpg_runtime/core/save_manager.gd"
const SETTINGS := "res://addons/rpg_runtime/core/settings.gd"

static func tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

## Adds a node with `script_path` as /root/<autoload_name> (replacing an existing one).
static func install(autoload_name: String, script_path: String) -> Node:
	var root := tree().root
	var old := root.get_node_or_null(autoload_name)
	if old != null:
		root.remove_child(old)
		old.free()
	var node := Node.new()
	node.name = autoload_name
	node.set_script(load(script_path))
	root.add_child(node)
	# While --script runs _initialize the root is not in the tree yet, so _ready() is not called.
	if node.has_method("_ready") and not node.is_node_ready():
		node._ready()
	return node

static func uninstall(autoload_name: String) -> void:
	var root := tree().root
	var old := root.get_node_or_null(autoload_name)
	if old != null:
		root.remove_child(old)
		old.free()

## Events + GameState (with a small item registry) ready for use.
static func install_state(registry: Dictionary = {}) -> Node:
	install("Events", EVENTS)
	var state := install("GameState", GAME_STATE)
	for id in registry.keys():
		state.items[id] = registry[id]
	return state

static func uninstall_state() -> void:
	uninstall("GameState")
	uninstall("Events")

static func item(id: StringName, max_stack: int = 99, effect: StringName = &"", amount: int = 0) -> RpgItemDefinition:
	var def := RpgItemDefinition.new()
	def.id = id
	def.max_stack = max_stack
	def.use_effect = effect
	def.effect_amount = amount
	return def
