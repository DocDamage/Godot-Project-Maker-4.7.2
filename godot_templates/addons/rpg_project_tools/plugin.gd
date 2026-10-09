@tool
extends EditorPlugin
## RPG Project Tools: the asset library dock (browse, drag into maps, edit catalog overrides,
## rebuild affected resources, validate content). Never runs game logic and never writes inside
## generated/ except by starting the builder (tools/rebuild.gd).

# Loaded, not preloaded: the script lives next to this file, but a failure to parse the dock must
# disable the dock, not the plugin.
const DOCK_SCRIPT := "res://addons/rpg_project_tools/dock/asset_dock.gd"

var dock: EditorDock = null
## Messages to the game that runs from the editor (the Cutscenes tab's Test, T13.19).
var debug_link: DebugLink = null

## The editor's side of the debugger channel: `send` hands a message to every running game.
class DebugLink extends EditorDebuggerPlugin:
	func send(message: String, data: Array) -> bool:
		var sent := false
		for session: EditorDebuggerSession in get_sessions():
			if session.is_active():
				session.send_message(message, data)
				sent = true
		return sent

func _enter_tree() -> void:
	debug_link = DebugLink.new()
	add_debugger_plugin(debug_link)
	var script := load(DOCK_SCRIPT) as GDScript
	if script == null:
		push_error("[RPG-TOOLS] could not load %s" % DOCK_SCRIPT)
		return
	dock = script.new()
	dock.set("plugin", self)
	add_dock(dock)

func _exit_tree() -> void:
	if dock != null:
		remove_dock(dock)
		dock.queue_free()
		dock = null
	if debug_link != null:
		remove_debugger_plugin(debug_link)
		debug_link = null
