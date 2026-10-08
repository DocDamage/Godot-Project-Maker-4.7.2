extends Node
## Entry point of a generated game: creates the persistent services under SceneRouter (audio, UI
## layers, combat mode, debug overlay) once, then sends the router to the first scene (the title).

const UI_DIR := "res://generated/scenes/ui/"

@export var first_scene: String = ""
## The archetype's combat mode scene (empty until an archetype provides one).
@export var combat_scene: String = ""
@export var debug_tools: bool = false
## The HUD scene under ui/ (an archetype may bring its own).
@export var hud_scene: String = "hud_basic"

func _ready() -> void:
	RpgStrings.register_translations()
	if first_scene == "":
		push_error("[RPG-BOOT] first_scene is not set")
		return
	var router := get_node_or_null("/root/SceneRouter") as RpgSceneRouter
	if router == null:
		get_tree().change_scene_to_file.call_deferred(first_scene)
		return
	if not router.has_meta("rpg_services"):
		router.set_meta("rpg_services", true)
		_create_services(router)
	router.go_to.call_deferred(first_scene)

func _create_services(router: RpgSceneRouter) -> void:
	var audio := RpgAudio.new()
	audio.name = "Audio"
	router.add_child(audio)
	router.set("audio", audio)
	_add_scene(router, "dialogue_box")
	_add_scene(router, hud_scene)
	_add_scene(router, "notification", 70)
	var controller := RpgUiController.new()
	controller.name = "UiController"
	router.add_child(controller)
	if combat_scene != "" and ResourceLoader.exists(combat_scene):
		var combat := (load(combat_scene) as PackedScene).instantiate()
		combat.name = "Combat"
		router.add_child(combat)
		router.set("combat", combat)
	if debug_tools and OS.is_debug_build():
		var overlay := RpgDebugOverlay.new()
		overlay.name = "DebugOverlay"
		router.add_child(overlay)

## Instances ui/<name>.tscn under the router. Controls get their own CanvasLayer.
func _add_scene(router: Node, scene_name: String, layer: int = 0) -> void:
	var path := UI_DIR + scene_name + ".tscn"
	if not ResourceLoader.exists(path):
		push_error("[RPG-BOOT] missing UI scene %s" % path)
		return
	var inst := (load(path) as PackedScene).instantiate()
	if inst is Control:
		var holder := CanvasLayer.new()
		holder.name = scene_name.to_pascal_case() + "Layer"
		holder.layer = layer if layer > 0 else 10
		holder.process_mode = Node.PROCESS_MODE_ALWAYS
		holder.add_child(inst)
		router.add_child(holder)
	else:
		router.add_child(inst)
