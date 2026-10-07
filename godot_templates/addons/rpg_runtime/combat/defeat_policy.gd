class_name RpgDefeatPolicy
extends RefCounted
## What happens when the player is defeated, shared by both archetypes. The player is never left
## at 0 HP. A game-over screen offers: continue from the newest save (hidden when there is none),
## try again from the start of the map, or quit to the title. Without a screen (smoke tests, a
## scene that has none) the default applies at once: the newest save when one exists, else the
## start of the map with full HP.

enum Choice { CONTINUE, RETRY, QUIT }

const GAME_OVER_SCENE := "game_over"

## Smoke tests run without a player; a test sets this to see the real screen once.
static var force_screen := false

## The save slot written last (the autosave slot 0 counts), or -1 when there is none.
static func latest_save_slot() -> int:
	var save := RpgUtil.autoload(&"SaveManager")
	if save == null:
		return -1
	var best := -1
	var best_time := ""
	for slot in range(int(save.get("AUTOSAVE_SLOT")), int(save.get("SLOTS")) + 1):
		if not save.has_save(slot):
			continue
		var saved_at := str(save.header(slot).get("saved_at", ""))
		if best < 0 or saved_at >= best_time:
			best = slot
			best_time = saved_at
	return best

## True when nobody can press a button: a smoke run, or a combat mode with an auto_choose hook.
static func is_automatic() -> bool:
	if force_screen:
		return false
	if OS.get_cmdline_user_args().has("--rpg-smoke"):
		return true
	var router := RpgUtil.router()
	var combat: Variant = router.get("combat") if router != null else null
	if combat != null and combat.get("auto_choose") is Callable:
		return (combat.get("auto_choose") as Callable).is_valid()
	return false

## Shows the game-over screen (or applies the default at once) and carries out the choice. Await it.
static func show_game_over() -> void:
	var tree := RpgUtil.tree()
	var router := RpgUtil.router()
	if tree == null or router == null or RpgUtil.state() == null:
		return
	var path := RpgMenuUtil.scene_path(GAME_OVER_SCENE)
	if is_automatic() or not ResourceLoader.exists(path):
		await apply(Choice.CONTINUE if latest_save_slot() >= 0 else Choice.RETRY)
		return
	var screen := (load(path) as PackedScene).instantiate() as Control
	var layer := CanvasLayer.new()
	layer.name = "GameOverLayer"
	layer.layer = 80
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	layer.add_child(screen)
	router.add_child(layer)
	tree.paused = true
	var choice: int = await screen.chosen
	tree.paused = false
	layer.queue_free()
	await apply(choice)

## Carries out a choice. Continue without a save falls back to retry.
static func apply(choice: int) -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	if state == null or router == null:
		return
	state.player_stats.hp = maxi(1, state.player_stats.hp)
	if choice == Choice.QUIT:
		await router.go_to(RpgMenuUtil.TITLE_SCENE)
		return
	if choice == Choice.CONTINUE:
		var slot := latest_save_slot()
		if slot >= 0 and RpgUtil.autoload(&"SaveManager").load(slot):
			while router.is_busy():
				await router.get_tree().process_frame
			return
	state.player_stats.hp = state.player_stats.max_hp
	var map := router.get("current_map") as RpgMapRoot
	if map != null:
		await router.go_to(map.scene_file_path, &"default")
