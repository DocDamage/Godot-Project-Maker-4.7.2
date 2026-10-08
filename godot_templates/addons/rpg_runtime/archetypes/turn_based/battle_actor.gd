class_name RpgBattleActor
extends RefCounted
## One combatant of a battle. The player side shares the live GameState stats; enemies get a copy.

var id: StringName
var display_name: String
var stats: RpgStats  # copy for enemies; the live GameState stats for the player
var is_player_side: bool = false
var defending := false
var sprite_frames: SpriteFrames
var portrait: Texture2D
var definition: Resource = null  # the RpgEnemyDefinition of an enemy
var behavior: Dictionary = {}
var inventory: RpgInventory = null  # enemy-side items (the player side uses GameState.inventory)
var chosen_item: StringName = &""  # set by the controller right before an item command runs
var alive: bool:
	get:
		return stats != null and stats.hp > 0

## A stat as combat sees it: the player side wears its equipment, enemies use their stats as they are.
func stat(stat_name: StringName) -> int:
	var state := RpgUtil.state() if is_player_side else null
	if state != null:
		return roundi(state.effective_stat(stats, stat_name))
	return roundi(stats.get_stat(stat_name))

static func make(actor_id: StringName, actor_name: String, actor_stats: RpgStats, player_side: bool) -> RpgBattleActor:
	var a := RpgBattleActor.new()
	a.id = actor_id
	a.display_name = actor_name
	a.stats = actor_stats
	a.is_player_side = player_side
	return a
