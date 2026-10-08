class_name RpgLootTable
extends Resource

@export var entries: Array[Dictionary] = []  # [{item_id, chance (0..1), min, max}]

## Rolls every entry once with `rng` (an RpgRng; a test seeds one with seed_value()). Returns
## [{item_id, qty}].
func roll(rng: RpgRng) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for e in entries:
		var chance := RpgUtil.to_float(e.get("chance", 1.0))
		if chance < 1.0 and rng.randf() >= chance:
			continue
		var lo := RpgUtil.to_int(e.get("min", 1))
		var hi := maxi(lo, RpgUtil.to_int(e.get("max", lo)))
		var qty: int = rng.randi_range(lo, hi) if hi > lo else lo
		if qty > 0:
			out.append({"item_id": StringName(str(e.get("item_id", ""))), "qty": qty})
	return out
