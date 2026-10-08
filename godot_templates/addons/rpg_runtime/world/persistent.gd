class_name RpgPersistent
extends Node
## Component for entities whose state survives map changes and saves. Add it as a child of the
## entity; the entity is its parent. Reads the flags in GameState when the entity enters a map.

## Empty = use the parent's own `entity_id` property.
@export var entity_id: String = ""
@export var keys: PackedStringArray = ["defeated", "opened", "collected"]

func resolved_id() -> String:
	if entity_id != "":
		return entity_id
	var parent := get_parent()
	if parent != null and parent.get("entity_id") != null:
		return str(parent.get("entity_id"))
	return ""

func _ready() -> void:
	var state := RpgUtil.state()
	var entity := get_parent()
	var id := resolved_id()
	if state == null or entity == null or id == "":
		return
	for key in keys:
		if not RpgUtil.to_bool(state.get_flag(id, key, false)):
			continue
		if key == "opened":
			if entity.has_method("apply_opened_state"):
				entity.call("apply_opened_state")
		else:
			entity.queue_free()
			return
