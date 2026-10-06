extends SceneTree
# Probe: AtlasTexture.margin semantics. For a trimmed frame cut from a sheet, margin =
# Rect2(offset_x, offset_y, source_w - w, source_h - h) must make get_size() the untrimmed size and
# draw the region at the offset.

func _initialize() -> void:
	var img := Image.create(40, 40, false, Image.FORMAT_RGBA8)
	var tex := ImageTexture.create_from_image(img)
	var at := AtlasTexture.new()
	at.atlas = tex
	at.region = Rect2(4, 5, 20, 30)
	at.margin = Rect2(2, 2, 4, 2)
	print("PROBE atlas_margin_size: ", at.get_size(), " (expect (24, 32))")
	print("PROBE atlas_margin_roundtrip: ", at.margin)
	quit(0)
