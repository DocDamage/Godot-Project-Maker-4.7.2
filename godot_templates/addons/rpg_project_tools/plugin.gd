@tool
extends EditorPlugin
## RPG Project Tools: the asset library dock (browse, drag into maps, edit catalog overrides,
## rebuild affected resources, validate content). Never runs game logic and never writes inside
## generated/ except by starting the builder (tools/rebuild.gd).

# Loaded, not preloaded: the script lives next to this file, but a failure to parse the dock must
# disable the dock, not the plugin.
const DOCK_SCRIPT := "res://addons/rpg_project_tools/dock/asset_dock.gd"

var dock: EditorDock = null

func _enter_tree() -> void:
	var script := load(DOCK_SCRIPT) as GDScript
	if script == null:
		push_error("[RPG-TOOLS] could not load %s" % DOCK_SCRIPT)
		return
	dock = script.new()
	dock.plugin = self
	add_dock(dock)

func _exit_tree() -> void:
	if dock != null:
		remove_dock(dock)
		dock.queue_free()
		dock = null
