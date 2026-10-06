extends SceneTree
# Probe: quit(3) from _initialize() under --script ends the process with exit code 3.

func _initialize() -> void:
	print("PROBE quit_code: calling quit(3)")
	quit(3)
