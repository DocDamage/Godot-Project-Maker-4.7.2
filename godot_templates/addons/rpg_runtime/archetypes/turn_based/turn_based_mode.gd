class_name RpgTurnBasedMode
extends RpgCombatMode
## The turn-based archetype's combat mode: pushes the battle scene, takes the result back to the
## overworld and applies what it means (defeated enemy, escape grace, defeat policy).

const BATTLE_SCENE := "res://generated/scenes/battle/battle.tscn"
const ESCAPE_GRACE_S := 1.5

var battle_scene_path: String = BATTLE_SCENE
## Picked up by the next battle in place of the UI (the smoke test sets it). Called as
## auto_choose.call(actor, battle) and returns {command_id, target_index}.
var auto_choose: Callable = Callable()

var _in_combat := false
var _active: RpgEncounterData = null

func _ready() -> void:
	var bus := RpgUtil.events()
	if bus != null:
		bus.encounter_finished.connect(_on_pop_finished)

func is_in_combat() -> bool:
	return _in_combat

func start_encounter(data: RpgEncounterData) -> void:
	if _in_combat or data == null:
		return
	var router := RpgUtil.router()
	if router == null or not ResourceLoader.exists(battle_scene_path):
		push_error("[RPG-COMBAT] cannot start a battle: the router or %s is missing" % battle_scene_path)
		return
	if router.is_busy():
		return  # the caller tries again
	_in_combat = true
	_active = data
	_fill_way_back(data, router)
	_freeze_player(router)
	var state := RpgUtil.state()
	if state != null:
		state.pending_encounter = data
	RpgUtil.emit(&"encounter_requested", [data])
	router.push_scene(battle_scene_path, data)

func _player_of(router: Node) -> Node2D:
	var map := router.get("current_map") as RpgMapRoot
	return map.get_player() if map != null else null

func _fill_way_back(data: RpgEncounterData, router: Node) -> void:
	var map := router.get("current_map") as RpgMapRoot
	if map == null:
		return
	if data.return_map == "":
		data.return_map = map.scene_file_path
	var player := _player_of(router)
	if player != null:
		data.return_position = player.global_position
		if "facing" in player:
			data.return_facing = str(player.get("facing"))

func _freeze_player(router: Node) -> void:
	var player := _player_of(router)
	if player != null and "input_enabled" in player:
		player.set("input_enabled", false)
		player.call("move_dir", Vector2.ZERO)

## SceneRouter.pop_scene emits this after the map is back and faded in.
func _on_pop_finished(result: Resource) -> void:
	if not _in_combat:
		return
	var res := result as RpgEncounterResult
	if res == null:
		res = RpgEncounterResult.new()
		res.outcome = RpgEncounterResult.Outcome.ESCAPED
	var entity_id := _active.entity_id if _active != null else res.entity_id
	match res.outcome:
		RpgEncounterResult.Outcome.VICTORY:
			_enemy_defeated(entity_id)
		RpgEncounterResult.Outcome.ESCAPED:
			var enemy := find_entity(entity_id)
			if enemy != null and enemy.has_method("grant_grace"):
				enemy.call("grant_grace", ESCAPE_GRACE_S)
		RpgEncounterResult.Outcome.DEFEAT:
			await _apply_defeat()
	_active = null
	_in_combat = false
	encounter_finished.emit(res)

func _enemy_defeated(entity_id: String) -> void:
	if entity_id == "":
		return
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(entity_id, "defeated", true)
	RpgUtil.emit(&"entity_defeated", [entity_id])
	var enemy := find_entity(entity_id)
	if enemy != null:
		enemy.queue_free()

## The node with this `entity_id` in the current map, or null.
static func find_entity(entity_id: String) -> Node:
	var router := RpgUtil.router()
	if router == null or entity_id == "":
		return null
	var map := router.get("current_map") as RpgMapRoot
	if map == null:
		return null
	for node in map.find_children("*", "", true, false):
		if node.get("entity_id") != null and str(node.get("entity_id")) == entity_id and not node.is_queued_for_deletion():
			return node
	return null

## The save slot written last, or 0 when there is none.
static func latest_save_slot() -> int:
	return RpgDefeatPolicy.latest_save_slot()

## The defeat policy is shared with the action-RPG archetype (RpgDefeatPolicy): the game-over
## screen, or at once the newest save / the start of the map when nobody can press a button.
func _apply_defeat() -> void:
	await RpgDefeatPolicy.show_game_over()
