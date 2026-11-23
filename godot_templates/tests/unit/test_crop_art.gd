extends RefCounted

func test_a_saved_stage_count_still_reaches_ripe_when_the_art_gains_a_stage(t) -> void:
	var crop := RpgCrop.new()
	var visual := Sprite2D.new()
	visual.name = "Visual"
	visual.texture = ImageTexture.create_from_image(Image.create(64, 16, false, Image.FORMAT_RGBA8))
	visual.hframes = 4
	crop.add_child(visual)
	crop.show_stage(0, 3, false, false)
	t.eq(visual.frame, 0)
	crop.show_stage(1, 3, false, false)
	t.eq(visual.frame, 2, "saved progress maps over all available art")
	crop.show_stage(2, 3, true, false)
	t.eq(visual.frame, 3, "harvest shows the final native frame")
	t.eq(crop.stage, 2, "the saved logical stage remains unchanged")
	t.ok(crop.ripe)
	crop.show_stage(1, 4, true, false)
	t.eq(visual.frame, 1, "matching frame counts retain the requested frame")
	crop.show_stage(2, 3, true, true)
	t.ok(not crop.ripe and crop.withered)
	t.eq(visual.frame, 3)
	crop.free()
