class_name RpgInventory
extends RefCounted
## Stacks of items in acquisition order. Unknown item ids are kept (so data is not lost) but are
## skipped by the UI.
##
## 1.5.0: a slot may carry its own `data` (a Dictionary, such as {"wear": 3}); such a slot holds
## one item and never stacks (add_with, take_one). `transact` gives and takes several rows all or
## nothing, and `fits` says whether rows would fit.

const DEFAULT_MAX_STACK := 99

var slots: Array[Dictionary] = []  # [{item_id: StringName, qty: int, data?: Dictionary}]
var capacity: int = 40  # distinct stacks
## item id -> RpgItemDefinition. GameState points this at its own registry.
var registry: Dictionary = {}
## True: add and remove emit nothing (the trial copy of `fits` and `transact`).
var quiet := false

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
		if slot["item_id"] == item_id and not slot.has("data") and RpgUtil.to_int(slot["qty"]) < limit:
			var room := limit - RpgUtil.to_int(slot["qty"])
			var put := mini(room, remaining)
			slot["qty"] = RpgUtil.to_int(slot["qty"]) + put
			remaining -= put
	while remaining > 0 and slots.size() < capacity:
		var put := mini(limit, remaining)
		slots.append({"item_id": item_id, "qty": put})
		remaining -= put
	var added := qty - remaining
	if added > 0 and not quiet:
		RpgUtil.emit(&"item_added", [item_id, added])
	return added

## Adds one `item_id` that carries `data` in a slot of its own (it never stacks). False when the
## bag has no free slot. Empty data adds a plain item.
func add_with(item_id: StringName, data: Dictionary) -> bool:
	if data.is_empty():
		return add(item_id, 1) == 1
	if item_id == &"" or slots.size() >= capacity:
		return false
	slots.append({"item_id": item_id, "qty": 1, "data": data.duplicate(true)})
	if not quiet:
		RpgUtil.emit(&"item_added", [item_id, 1])
	return true

## Removes one `item_id` and returns its data ({} for a plain one): the first slot that holds it.
## Null when none is held.
func take_one(item_id: StringName) -> Variant:
	for i in slots.size():
		if slots[i]["item_id"] != item_id:
			continue
		var data := RpgUtil.to_dict(slots[i].get("data", {})).duplicate(true)
		slots[i]["qty"] = RpgUtil.to_int(slots[i]["qty"]) - 1
		if RpgUtil.to_int(slots[i]["qty"]) <= 0:
			slots.remove_at(i)
		if not quiet:
			RpgUtil.emit(&"item_removed", [item_id, 1])
		return data
	return null

## The data of slot `index` ({} for a plain slot or one out of range).
func data_at(index: int) -> Dictionary:
	if index < 0 or index >= slots.size():
		return {}
	return RpgUtil.to_dict(slots[index].get("data", {}))

## A copy that adds and removes without signals: what `fits` and `transact` try first.
func trial() -> RpgInventory:
	var copy := RpgInventory.new()
	copy.capacity = capacity
	copy.registry = registry
	copy.quiet = true
	for slot in slots:
		copy.slots.append(slot.duplicate(true))
	return copy

## True when every row of `giving` ([{item_id, qty}]) would fit at once, after `taking` is taken.
func fits(giving: Array, taking: Array = []) -> bool:
	return trial()._apply(giving, taking)

## Takes every row of `taking` and adds every row of `giving` ([{item_id, qty}] both), or does
## nothing at all: false when something to take is not held or something to give does not fit.
func transact(giving: Array, taking: Array = []) -> bool:
	if not fits(giving, taking):
		return false
	return _apply(giving, taking)

func _apply(giving: Array, taking: Array) -> bool:
	for raw: Variant in taking:
		var row := RpgUtil.to_dict(raw)
		if not remove(StringName(str(row.get("item_id", ""))), maxi(1, RpgUtil.to_int(row.get("qty", 1)))):
			return false
	for raw: Variant in giving:
		var row := RpgUtil.to_dict(raw)
		var qty := maxi(1, RpgUtil.to_int(row.get("qty", 1)))
		if add(StringName(str(row.get("item_id", ""))), qty) < qty:
			return false
	return true

## How many more of `item_id` fit: the room left in its stacks plus the free slots.
func room_for(item_id: StringName) -> int:
	if item_id == &"":
		return 0
	var limit := _max_stack(item_id)
	var room := maxi(0, capacity - slots.size()) * limit
	for slot in slots:
		if slot["item_id"] == item_id:
			room += maxi(0, limit - RpgUtil.to_int(slot["qty"]))
	return room

## All-or-nothing: returns false (and changes nothing) when fewer than `qty` are held.
func remove(item_id: StringName, qty: int = 1) -> bool:
	if qty <= 0 or count(item_id) < qty:
		return false
	var remaining := qty
	var i := slots.size() - 1
	while i >= 0 and remaining > 0:
		var slot := slots[i]
		if slot["item_id"] == item_id and not slot.has("data"):
			var take := mini(RpgUtil.to_int(slot["qty"]), remaining)
			slot["qty"] = RpgUtil.to_int(slot["qty"]) - take
			remaining -= take
			if RpgUtil.to_int(slot["qty"]) == 0:
				slots.remove_at(i)
		i -= 1
	i = slots.size() - 1
	while i >= 0 and remaining > 0:  # then the ones that carry data, the latest first
		if slots[i]["item_id"] == item_id:
			slots.remove_at(i)
			remaining -= 1
		i -= 1
	if not quiet:
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

## Applies the item's use_effect ("heal" or "mp") to `target_stats` and removes one on success. A
## heal at full health (or MP at full MP) is refused (the item is kept).
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
		"mp":
			var max_mp := RpgUtil.max_mp(target_stats)
			if max_mp <= 0 or target_stats.mp >= max_mp:
				return false
			target_stats.mp = mini(max_mp, target_stats.mp + def.effect_amount)
		_:
			return false  # "cure" works in battle only (statuses end with the battle)
	return remove(item_id, 1)

func to_array() -> Array:
	var out: Array = []
	for slot in slots:
		var row := {"item_id": RpgUtil.to_str(slot["item_id"]), "qty": RpgUtil.to_int(slot["qty"])}
		if slot.has("data"):
			row["data"] = RpgUtil.to_dict(slot["data"]).duplicate(true)
		out.append(row)
	return out

func load_array(a: Array) -> void:
	slots.clear()
	for entry: Variant in a:
		if not (entry is Dictionary):
			continue
		var row: Dictionary = entry
		var qty := RpgUtil.to_int(row.get("qty", 0))
		if qty > 0:
			var slot := {"item_id": StringName(str(row.get("item_id", ""))), "qty": qty}
			var data := RpgUtil.to_dict(row.get("data", {}))
			if not data.is_empty():
				slot["qty"] = 1  # a slot that carries data holds one
				slot["data"] = data.duplicate(true)
			slots.append(slot)
