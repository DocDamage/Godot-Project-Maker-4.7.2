extends SceneTree
## Renders the dock's Quests tab of a generated project into a PNG: the picture of the user guide
## (tools/make_doc_screenshots.py runs it). It needs a window, so it is run without --headless:
##   godot --path <project> --script <this file> -- <out.png>

func _init() -> void:
	_shoot.call_deferred()

func _shoot() -> void:
	var args := OS.get_cmdline_user_args()
	var out := args[0] if not args.is_empty() else "user://quests_tab.png"
	var script := load("res://addons/rpg_project_tools/dock/quest_tab.gd") as GDScript
	var tab: Control = script.new()
	root.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	root.size = Vector2i(1000, 660)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(panel)
	panel.add_child(tab)
	for i in 12:
		await process_frame
	tab.call("select_stage", 0)
	tab.call("set_test_atom", "flag:starter_npc.talked", true)
	for i in 8:
		await process_frame
	var image := root.get_texture().get_image()
	var err := image.save_png(out)
	print("[shot] saved %s: %d (%dx%d)" % [out, err, image.get_width(), image.get_height()])
	quit(0 if err == OK else 1)
