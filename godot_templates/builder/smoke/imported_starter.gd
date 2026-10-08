extends RefCounted
## T12.49: a starter map imported from a Tiled or LDtk file has none of the demo's entities, so the
## smoke steps that play the demo's enemy pass with a note instead of looking for it.

const CONFIG := "res://rpggen/generator_config.json"

## True when the config picks an imported map as the starter map.
static func active() -> bool:
	var cfg: Variant = JSON.parse_string(FileAccess.get_file_as_string(CONFIG)) if FileAccess.file_exists(CONFIG) else null
	if not cfg is Dictionary:
		return false
	var table: Dictionary = cfg
	var section: Variant = table.get("imported_maps", {})
	if not section is Dictionary:
		return false
	var imported: Dictionary = section
	return str(imported.get("starter", "")) != ""

## The pass of a step that needs the demo's enemy.
static func note(step_name: String) -> String:
	print("[rpggen] INFO %s: the starter map was imported and has no demo enemy, step passes" % step_name)
	return ""
