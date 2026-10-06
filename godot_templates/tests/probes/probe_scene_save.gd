extends SceneTree
# Probe: PackedScene packing, owner rules, collision_layer_value, SpriteFrames meta persistence
# and ResourceLoader.get_dependencies() format.

func _initialize() -> void:
	# owner rule: a child without owner is NOT saved.
	var root := Node2D.new()
	root.name = "Root"
	var kept := Node2D.new()
	kept.name = "Kept"
	root.add_child(kept)
	kept.owner = root
	var dropped := Node2D.new()
	dropped.name = "Dropped"
	root.add_child(dropped)
	var packed := PackedScene.new()
	print("PROBE pack: ", packed.pack(root))
	var path := "user://probe_scene.tscn"
	print("PROBE save_scene: ", ResourceSaver.save(packed, path))
	var inst := (load(path) as PackedScene).instantiate()
	print("PROBE owner_rule: kept=", inst.has_node("Kept"), " dropped=", inst.has_node("Dropped"))
	inst.free()
	root.free()

	# collision layer values
	var body := CharacterBody2D.new()
	body.set_collision_layer_value(2, true)
	body.set_collision_mask_value(1, true)
	body.set_collision_mask_value(3, true)
	print("PROBE collision_values: layer=", body.collision_layer, " mask=", body.collision_mask)
	body.free()

	# SpriteFrames: default animation, meta persistence
	var sf := SpriteFrames.new()
	print("PROBE spriteframes_default: ", sf.has_animation("default"))
	if sf.has_animation("default"):
		sf.remove_animation("default")
	sf.add_animation("walk_left")
	sf.set_animation_speed("walk_left", 8.0)
	sf.set_animation_loop("walk_left", true)
	var img := Image.create(32, 24, false, Image.FORMAT_RGBA8)
	var tex := ImageTexture.create_from_image(img)
	var at := AtlasTexture.new()
	at.atlas = tex
	at.region = Rect2(0, 0, 16, 24)
	sf.add_frame("walk_left", at, 1.0)
	sf.set_meta("flip_h_walk_left", true)
	print("PROBE spriteframes_frames: ", sf.get_frame_count("walk_left"), " fps=", sf.get_animation_speed("walk_left"))
	print("PROBE spriteframes_save: ", ResourceSaver.save(sf, "user://probe_sf.tres"))
	var sf2 := load("user://probe_sf.tres") as SpriteFrames
	print("PROBE spriteframes_meta_persisted: ", sf2.has_meta("flip_h_walk_left"), " ", sf2.get_meta("flip_h_walk_left", false))

	# get_dependencies format on a scene that references an external script
	var s := Sprite2D.new()
	s.texture = load("res://icon.svg")
	s.name = "WithScript"
	var p2 := PackedScene.new()
	p2.pack(s)
	ResourceSaver.save(p2, "user://probe_dep.tscn")
	s.free()
	for d in ResourceLoader.get_dependencies("user://probe_dep.tscn"):
		print("PROBE dependency_entry: ", d)
	DirAccess.remove_absolute(path)
	DirAccess.remove_absolute("user://probe_sf.tres")
	DirAccess.remove_absolute("user://probe_dep.tscn")
	quit(0)
