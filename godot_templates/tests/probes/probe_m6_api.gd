extends SceneTree
# APIs M6 relies on (docs/godot_api_verified.md): bus layout generation, tree collision hint,
# CSV-free Translation resources, Area2D vs StaticBody2D monitorable rule.
func _initialize() -> void:
	AudioServer.add_bus()
	AudioServer.set_bus_name(AudioServer.bus_count - 1, "Music")
	var layout := AudioServer.generate_bus_layout()
	print("bus layout saved: ", ResourceSaver.save(layout, "user://probe_buses.tres") == OK)
	var before := debug_collisions_hint
	debug_collisions_hint = not before
	print("debug_collisions_hint toggles: ", debug_collisions_hint != before)
	var tr := Translation.new()
	tr.locale = "en"
	tr.add_message(&"K", "V")
	print("translation saved: ", ResourceSaver.save(tr, "user://probe_tr.tres") == OK)
	print("translation reloaded: ", (load("user://probe_tr.tres") as Translation).get_message(&"K"))
	quit()
