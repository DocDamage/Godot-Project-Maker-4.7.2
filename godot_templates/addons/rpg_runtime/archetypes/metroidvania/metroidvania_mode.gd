class_name RpgMetroidvaniaMode
extends RpgCombatMode
## The metroidvania archetype's combat mode, SceneRouter.combat. The fighting happens in the rooms
## themselves (the real-time set of combat/realtime/), so there are no encounters and
## is_in_combat() is always false. The mode owns what the shared code asks an archetype for: the
## defeat policy and the rules of saving.
##
## Saving: by hand only at a save station (the pause menu's Save is off), and by itself into the
## autosave slot on every room change. A defeated player comes back at the last station used with
## everything it had (progress since the last save is kept; where it stood is not).

## Read by the pause menu: Save is shown as "Save at a station" and cannot be pressed.
var save_at_stations := true
## Read by the save manager: every room change saves, without the wait between two autosaves and
## without a toast.
var autosave_on_every_map := true

func _ready() -> void:
	var bus := RpgUtil.events()
	if bus != null:
		bus.map_entered.connect(_on_map_entered)
		bus.dialogue_event.connect(_on_dialogue_event)

func is_in_combat() -> bool:
	return false

func start_encounter(_data: RpgEncounterData) -> void:
	push_warning("[RPG-COMBAT] the metroidvania has no encounters; enemies fight in the rooms")

## Every room entered is on the room map from then on.
func _on_map_entered(map_id: StringName) -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	var map: Node = router.current_map if router != null else null
	if state != null and map != null and RpgUtil.to_bool(map.get("side_view")):
		state.visit_room(String(map_id))

## `emit:credits` in a dialogue (the hermit of the last room): the credits open when it closes.
func _on_dialogue_event(event_name: String, _arg: String) -> void:
	if event_name != "credits":
		return
	var bus := RpgUtil.events()
	if bus != null and not bus.dialogue_finished.is_connected(_show_credits):
		bus.dialogue_finished.connect(_show_credits, CONNECT_ONE_SHOT)

func _show_credits(_resource: Resource = null) -> void:
	var router := RpgUtil.router()
	var controller := router.get_node_or_null("UiController") if router != null else null
	if controller != null and controller.has_method(&"open_menu"):
		controller.call(&"open_menu", "credits_menu", {})

## The player was defeated: the shared policy (the game-over screen, or at once in a smoke test).
## Its Continue is respawn_after_defeat().
func apply_defeat() -> void:
	await RpgDefeatPolicy.show_game_over()

## Continue after a defeat: full health, at the last save station used (the start of the game
## before any was), with everything the player had. Called by RpgDefeatPolicy.
func respawn_after_defeat() -> void:
	var state := RpgUtil.state()
	var router := RpgUtil.router()
	if state == null or router == null:
		return
	state.revive_party()
	state.heal_party_full()
	var point := RpgSaveStation.respawn_point(state)
	if point.is_empty():
		var start := RpgNewGameData.new()
		if ResourceLoader.exists(RpgGameState.NEW_GAME_PATH):
			start = load(RpgGameState.NEW_GAME_PATH) as RpgNewGameData
		await router.go_to(start.start_map, start.start_spawn)
		return
	state.current_map = str(point["map"])
	state.player_position = point["position"]
	state.player_facing = "1"
	await router.reload_from_state()
