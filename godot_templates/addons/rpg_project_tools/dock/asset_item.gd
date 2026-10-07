@tool
extends ItemList
## The library's item list. Dragging an item starts a file drag of its scene, which the 2D editor
## instances like a scene dragged from the FileSystem dock.

signal drag_started(scene_path: String)

func _get_drag_data(at_position: Vector2) -> Variant:
	var index := get_item_at_position(at_position, true)
	if index < 0:
		return null
	var scene_path := String(get_item_metadata(index))
	if scene_path == "":
		return null
	var preview := TextureRect.new()
	preview.texture = get_item_icon(index)
	preview.custom_minimum_size = Vector2(48, 48)
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	preview.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	set_drag_preview(preview)
	drag_started.emit(scene_path)
	return {"type": "files", "files": PackedStringArray([scene_path])}
