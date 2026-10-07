class_name RpgRng
extends RefCounted
## Seeded wrapper around RandomNumberGenerator. All gameplay randomness uses GameState.rng so the
## smoke test is deterministic.

var gen := RandomNumberGenerator.new()

func _init() -> void:
	gen.randomize()

func seed_value(s: int) -> void:
	gen.seed = s

## In smoke mode (`--rpg-smoke`) the seed comes from the project setting `rpg/seed`; otherwise the
## generator is randomized.
func seed_from_config() -> void:
	if OS.get_cmdline_user_args().has("--rpg-smoke"):
		gen.seed = int(ProjectSettings.get_setting("rpg/seed", 12345))
	else:
		gen.randomize()

func randf() -> float:
	return gen.randf()

func randi_range(from: int, to: int) -> int:
	return gen.randi_range(from, to)

func randf_range(from: float, to: float) -> float:
	return gen.randf_range(from, to)

## A random element, or null for an empty array.
func pick(items: Array) -> Variant:
	if items.is_empty():
		return null
	return items[gen.randi_range(0, items.size() - 1)]

func get_state() -> Dictionary:
	return {"seed": str(gen.seed), "state": str(gen.state)}

func set_state(d: Dictionary) -> void:
	if d.has("seed"):
		gen.seed = int(str(d["seed"]))
	if d.has("state"):
		gen.state = int(str(d["state"]))
