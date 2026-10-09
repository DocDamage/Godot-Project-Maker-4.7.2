class_name RpgSaveStation
extends RpgSideInteractable
## A place to rest and save (a bench). Interacting with it restores the party's health, brings
## back the enemies the player defeated (the guardian stays defeated), makes this the place a
## defeated player returns to, and opens the save menu. A metroidvania saves by hand only here;
## the game also saves by itself into the autosave slot on every room change.

signal rested

## The entity under which the place to return to is kept in the saved game's flags.
const RESPAWN := "respawn"
## The part of an enemy's entity id that marks it as one a rest brings back.
const ENEMY_MARK := "_enemy_"

## Restores health, brings the enemies back and remembers this station. Returns how many enemies
## came back.
func rest() -> int:
	var state := RpgUtil.state()
	if state == null:
		return 0
	state.heal_party_full()
	var back := revive_enemies(state)
	var room := _room()
	if room != null:
		state.set_flag(RESPAWN, "map", room.scene_file_path)
		state.set_flag(RESPAWN, "x", global_position.x)
		state.set_flag(RESPAWN, "y", global_position.y)
		if room.has_method(&"respawn_enemies"):
			room.call(&"respawn_enemies")
	rested.emit()
	RpgUtil.notify(RpgMetroidvaniaStrings.t("MV_RESTED"))
	return back

## Clears the `defeated` flag of every ordinary enemy. Returns how many were cleared.
static func revive_enemies(state: RpgGameState) -> int:
	var count := 0
	for entity: Variant in state.flags.keys():
		var id := str(entity)
		if id.contains(ENEMY_MARK) and RpgUtil.to_bool(state.get_flag(id, "defeated", false)):
			state.set_flag(id, "defeated", false)
			count += 1
	return count

## Where a defeated player returns to: {map, position}, or {} when no station was used yet.
static func respawn_point(state: RpgGameState) -> Dictionary:
	if state == null:
		return {}
	var map := str(state.get_flag(RESPAWN, "map", ""))
	if map == "":
		return {}
	return {"map": map, "position": Vector2(RpgUtil.to_float(state.get_flag(RESPAWN, "x", 0.0)), RpgUtil.to_float(state.get_flag(RESPAWN, "y", 0.0)))}

func _room() -> Node:
	var node := get_parent()
	while node != null:
		if node is RpgMapRoot:
			return node
		node = node.get_parent()
	return null

## Rests, then saves into `slot` without a menu. False when the save failed.
func save_to(slot: int) -> bool:
	rest()
	var save := RpgUtil.save_manager()
	return save != null and save.save(slot)

func _use(_actor: Node) -> void:
	rest()
	var router := RpgUtil.router()
	var controller := router.get_node_or_null("UiController") if router != null else null
	if controller != null and controller.has_method(&"open_menu"):
		controller.call(&"open_menu", "save_load_menu", {"mode": "save"})
