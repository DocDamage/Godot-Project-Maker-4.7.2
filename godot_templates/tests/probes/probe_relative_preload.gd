extends SceneTree
# Probe: preload() with a path relative to the script, including "..".
const Paths := preload("../../builder/lib/paths.gd")
const Log := preload("../../builder/lib/log.gd")

func _initialize() -> void:
	Log.info("catalog=%s" % Paths.CATALOG)
	print("PROBE relative_preload: ", Paths.CATALOG == "res://rpggen/asset_catalog.json")
	quit(0)
