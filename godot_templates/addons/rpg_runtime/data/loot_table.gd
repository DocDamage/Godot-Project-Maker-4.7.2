class_name RpgLootTable
extends Resource

@export var entries: Array[Dictionary] = []  # [{item_id, chance (0..1), min, max}]

## Rolls every entry once. `rng` is a RandomNumberGenerator or an RpgRng (anything with randf()
## and randi_range()). Returns [{item_id, qty}].
func roll(rng: Variant) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for e in entries:
		var chance := float(e.get("chance", 1.0))
		if chance < 1.0 and rng.randf() >= chance:
			continue
		var lo := int(e.get("min", 1))
		var hi := maxi(lo, int(e.get("max", lo)))
		var qty: int = rng.randi_range(lo, hi) if hi > lo else lo
		if qty > 0:
			out.append({"item_id": StringName(str(e.get("item_id", ""))), "qty": qty})
	return out
