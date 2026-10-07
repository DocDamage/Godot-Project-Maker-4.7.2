class_name RpgLootDrop
extends Node
## Enemy component: what a defeated enemy leaves behind. Item loot becomes pickups on the map
## (rolled with GameState.rng, so a seeded game drops the same things); gold is added at once with
## a toast.

var actor: RpgActor

func _ready() -> void:
	var node := get_parent()
	while node != null and not (node is RpgActor):
		node = node.get_parent()
	actor = node as RpgActor

## Rolls the loot table of the actor's definition. Returns [{item_id, qty}] without spawning.
func roll() -> Array[Dictionary]:
	var def := actor.definition as RpgEnemyDefinition if actor != null else null
	if def == null or def.loot == null:
		return []
	var state := RpgUtil.state()
	var rng: Variant = state.get("rng") if state != null else RpgRng.new()
	return def.loot.roll(rng)

## Spawns the rolled items and grants the gold. Returns the dropped items.
func drop() -> Array[Dictionary]:
	var def := actor.definition as RpgEnemyDefinition if actor != null else null
	var items := roll()
	var parent := actor.get_parent() if actor != null else null
	var state := RpgUtil.state()
	for i in items.size():
		if parent == null or state == null:
			break
		var id: StringName = items[i]["item_id"]
		var icon: Texture2D = null
		var item_def: RpgItemDefinition = state.items.get(id)
		if item_def != null:
			icon = item_def.icon
		var pickup := RpgPickup.create(id, int(items[i]["qty"]), icon)
		# Spread several drops a little so they do not stack.
		pickup.position = actor.position + Vector2((i - (items.size() - 1) * 0.5) * 8.0, 2.0)
		parent.add_child.call_deferred(pickup)
	if def != null and def.gold_reward > 0 and state != null:
		state.gold += def.gold_reward
		RpgUtil.notify(RpgArpgText.t("ARPG_GOLD_GAINED", [def.gold_reward]))
	return items
