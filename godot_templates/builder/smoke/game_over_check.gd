extends RefCounted
## Shared by both archetypes' smoke steps: the game-over screen really appears (in a run that is
## not automatic) and confirming the focused button resumes play. The normal defeat steps run in
## automatic mode and skip the screen, so their timing does not change.

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func _autoload(autoload_name: String) -> Node:
	return _tree().root.get_node_or_null(autoload_name)

func _frames(n: int) -> void:
	for i in n:
		await _tree().process_frame

## Returns "" on success, else what went wrong.
func run() -> String:
	var tree := _tree()
	var router: RpgSceneRouter = _autoload("SceneRouter") as RpgSceneRouter
	if router == null or _autoload("GameState") == null:
		return "SceneRouter or GameState is missing"
	for i in 300:  # the map of the previous step may still be fading in
		if not router.is_busy() and tree.current_scene is RpgMapRoot:
			break
		await tree.process_frame
	RpgDefeatPolicy.force_screen = true
	RpgDefeatPolicy.show_game_over()  # a coroutine: it returns at the screen, which we drive below
	var layer: Node = null
	for i in 120:
		layer = router.get_node_or_null("GameOverLayer")
		if layer != null:
			break
		await tree.process_frame
	if layer == null:
		RpgDefeatPolicy.force_screen = false
		return "the game-over screen did not appear"
	await _frames(6)  # the deferred initial focus
	var focused := tree.root.gui_get_focus_owner()
	var result := ""
	if not tree.paused:
		result = "the game should be paused behind the game-over screen"
	elif not focused is Button or not layer.is_ancestor_of(focused):
		result = "no button of the game-over screen has the focus"
	if result != "":
		(layer.get_child(0) as Node).call("_choose", RpgDefeatPolicy.Choice.RETRY)  # leave the pause
		RpgDefeatPolicy.force_screen = false
		return result
	var key := InputEventKey.new()
	key.keycode = KEY_ENTER
	key.physical_keycode = KEY_ENTER
	key.pressed = true
	Input.parse_input_event(key)
	await _frames(2)
	key = key.duplicate() as InputEventKey
	key.pressed = false
	Input.parse_input_event(key)
	RpgDefeatPolicy.force_screen = false
	for i in 600:
		await tree.process_frame
		if not tree.paused and router.get_node_or_null("GameOverLayer") == null and not router.is_busy() and tree.current_scene is RpgMapRoot:
			return ""
	return "confirming the focused button did not resume play (paused: %s)" % str(tree.paused)
