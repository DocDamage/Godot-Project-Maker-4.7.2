class_name RpgEncounterTable
extends Resource
## Who a random encounter brings: enemy groups with weights. Files live in
## game/data/encounters/<id>.tres; an RpgEncounterZone points at one (turn-based games only).

@export var id: StringName
## [{enemies: [<enemy ids>], weight: int (default 1)}]. An enemy id names
## game/data/enemies/<id>.tres (a path with "://" is used as it is).
@export var groups: Array[Dictionary] = []
@export var can_escape: bool = true

## The file of an enemy id.
static func enemy_path(enemy_id: String) -> String:
	return enemy_id if enemy_id.contains("://") else "%s/%s.tres" % [RpgGameState.ENEMIES_DIR, enemy_id]

## The index of a group drawn by weight (weights below 1 count as 0), or -1 when no group can be
## drawn. Draws exactly one number from `rng`.
func pick(rng: RpgRng) -> int:
	var total := 0
	for group in groups:
		total += maxi(0, RpgUtil.to_int(group.get("weight", 1)))
	if total <= 0:
		return -1
	var roll := rng.randi_range(1, total)
	for i in groups.size():
		roll -= maxi(0, RpgUtil.to_int(groups[i].get("weight", 1)))
		if roll <= 0:
			return i
	return groups.size() - 1

## The enemy definitions of a group (ids whose file is missing are left out).
func enemies_of(index: int) -> Array[RpgEnemyDefinition]:
	var out: Array[RpgEnemyDefinition] = []
	if index < 0 or index >= groups.size():
		return out
	for enemy_id: Variant in RpgUtil.to_array(groups[index].get("enemies")):
		var path := enemy_path(str(enemy_id))
		var def: RpgEnemyDefinition = load(path) as RpgEnemyDefinition if ResourceLoader.exists(path) else null
		if def == null:
			push_error("[RPG-COMBAT] encounter table %s: no enemy '%s'" % [id, str(enemy_id)])
			continue
		out.append(def)
	return out

## The encounter of a drawn group (no entity: nothing on the map is defeated by it).
func encounter_for(index: int) -> RpgEncounterData:
	var data := RpgEncounterData.new()
	data.enemies.assign(enemies_of(index))
	data.can_escape = can_escape
	return data

## What is wrong with the groups, one sentence each (static, for the editor's validator).
static func problems_of(group_list: Array) -> Array[String]:
	var out: Array[String] = []
	if group_list.is_empty():
		out.append("the table has no groups")
	var weighted := false
	for i in group_list.size():
		var group := RpgUtil.to_dict(group_list[i])
		var enemies := RpgUtil.to_array(group.get("enemies"))
		if enemies.is_empty():
			out.append("group %d has no enemies" % (i + 1))
		for enemy_id: Variant in enemies:
			if not ResourceLoader.exists(enemy_path(str(enemy_id))):
				out.append("group %d names the unknown enemy '%s'" % [i + 1, str(enemy_id)])
		if RpgUtil.to_int(group.get("weight", 1)) > 0:
			weighted = true
	if not group_list.is_empty() and not weighted:
		out.append("every group has a weight of 0")
	return out
