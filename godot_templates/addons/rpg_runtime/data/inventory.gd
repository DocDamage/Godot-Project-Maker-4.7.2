class_name RpgInventory
extends RefCounted
## Stacks of items in acquisition order. Unknown item ids are kept (so data is not lost) but are
## skipped by the UI.

const DEFAULT_MAX_STACK := 99

var slots: Array[Dictionary] = []  # [{item_id: StringName, qty: int}]
var capacity: int = 40  # distinct stacks
## item id -> RpgItemDefinition. GameState points this at its own registry.
var registry: Dictionary = {}

func definition(item_id: StringName) -> RpgItemDefinition:
	var def: RpgItemDefinition = registry.get(item_id)
	return def

func _max_stack(item_id: StringName) -> int:
	var def := definition(item_id)
	return maxi(1, def.max_stack) if def != null else DEFAULT_MAX_STACK

## Adds up to `qty`: existing stacks are filled first, then new stacks are opened while there is
## capacity. Returns the quantity actually added.
func add(item_id: StringName, qty: int = 1) -> int:
	if qty <= 0 or item_id == &"":
		return 0
	var remaining := qty
	var limit := _max_stack(item_id)
	for slot in slots:
		if remaining == 0:
			break
		if slot["item_id"] == item_id and RpgUtil.to_int(slot["qty"]) < limit:
			var room := limit - RpgUtil.to_int(slot["qty"])
			var put := mini(room, remaining)
			slot["qty"] = RpgUtil.to_int(slot["qty"]) + put
			remaining -= put
	while remaining > 0 and slots.size() < capacity:
		var put := mini(limit, remaining)
		slots.append({"item_id": item_id, "qty": put})
		remaining -= put
	var added := qty - remaining
	if added > 0:
		RpgUtil.emit(&"item_added", [item_id, added])
	return added

## All-or-nothing: returns false (and changes nothing) when fewer than `qty` are held.
func remove(item_id: StringName, qty: int = 1) -> bool:
	if qty <= 0 or count(item_id) < qty:
		return false
	var remaining := qty
	var i := slots.size() - 1
	while i >= 0 and remaining > 0:
		var slot := slots[i]
		if slot["item_id"] == item_id:
			var take := mini(RpgUtil.to_int(slot["qty"]), remaining)
			slot["qty"] = RpgUtil.to_int(slot["qty"]) - take
			remaining -= take
			if RpgUtil.to_int(slot["qty"]) == 0:
				slots.remove_at(i)
		i -= 1
	RpgUtil.emit(&"item_removed", [item_id, qty])
	return true

func count(item_id: StringName) -> int:
	var total := 0
	for slot in slots:
		if slot["item_id"] == item_id:
			total += RpgUtil.to_int(slot["qty"])
	return total

func has(item_id: StringName, qty: int = 1) -> bool:
	return count(item_id) >= qty

## Applies the item's use_effect to `target_stats` and removes one on success. A heal at full
## health is refused (the item is kept).
func use(item_id: StringName, target_stats: RpgStats) -> bool:
	var def := definition(item_id)
	if def == null or target_stats == null or not has(item_id):
		return false
	match String(def.use_effect):
		"heal":
			var max_hp := RpgUtil.max_hp(target_stats)
			if target_stats.hp >= max_hp:
				return false
			var before := target_stats.hp
			target_stats.hp = mini(max_hp, target_stats.hp + def.effect_amount)
			var state := RpgUtil.state()
			if state != null and state.get("player_stats") == target_stats:
				RpgUtil.emit(&"player_healed", [target_stats.hp - before])
		_:
			return false
	return remove(item_id, 1)

func to_array() -> Array:
	var out: Array = []
	for slot in slots:
		out.append({"item_id": RpgUtil.to_str(slot["item_id"]), "qty": RpgUtil.to_int(slot["qty"])})
	return out

func load_array(a: Array) -> void:
	slots.clear()
	for entry: Variant in a:
		if not (entry is Dictionary):
			continue
		var row: Dictionary = entry
		var qty := RpgUtil.to_int(row.get("qty", 0))
		if qty > 0:
			slots.append({"item_id": StringName(str(row.get("item_id", ""))), "qty": qty})
