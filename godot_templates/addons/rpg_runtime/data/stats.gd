class_name RpgStats
extends Resource
## Actor stats. `extra` holds archetype extensions such as {"crit_chance": 0.05}.

const STAT_NAMES: Array[StringName] = [
	&"level", &"experience", &"max_hp", &"hp", &"attack", &"defense", &"speed", &"magic",
	&"resistance", &"move_speed",
]

@export var level: int = 1
@export var experience: int = 0
@export var max_hp: int = 20
@export var hp: int = 20
@export var attack: int = 5
@export var defense: int = 2
@export var speed: int = 5
@export var magic: int = 0  # turn-based uses
@export var resistance: int = 0
@export var move_speed: float = 80.0  # ARPG uses (px/s)
@export var extra: Dictionary = {}  # archetype extensions: {"crit_chance": 0.05, ...}

## Base value of the stat plus modifiers (Array of {stat, add, mul}): all `add` values are summed
## first, then multiplied by the product of all `mul` values. Unknown names read `extra`.
func get_stat(stat_name: StringName, modifiers: Array = []) -> float:
	var base := 0.0
	if STAT_NAMES.has(stat_name):
		base = float(get(stat_name))
	else:
		base = float(extra.get(String(stat_name), extra.get(stat_name, 0.0)))
	var added := 0.0
	var mult := 1.0
	for m in modifiers:
		if StringName(str(m.get("stat", ""))) != stat_name:
			continue
		added += float(m.get("add", 0.0))
		mult *= float(m.get("mul", 1.0))
	return (base + added) * mult

func xp_to_next() -> int:
	return int(round(10.0 * pow(level, 1.5)))

## Adds experience and returns the number of levels gained. Each level: max_hp +3, attack +1,
## defense +1, speed +1 on every 2nd level, and hp is refilled.
func add_experience(amount: int) -> int:
	if amount <= 0:
		return 0
	experience += amount
	var gained := 0
	while experience >= xp_to_next():
		experience -= xp_to_next()
		level += 1
		gained += 1
		max_hp += 3
		attack += 1
		defense += 1
		if level % 2 == 0:
			speed += 1
		hp = max_hp
	return gained

func to_dict() -> Dictionary:
	return {
		"level": level, "experience": experience, "max_hp": max_hp, "hp": hp, "attack": attack,
		"defense": defense, "speed": speed, "magic": magic, "resistance": resistance,
		"move_speed": move_speed, "extra": extra.duplicate(true),
	}

static func from_dict(d: Dictionary) -> RpgStats:
	var s := RpgStats.new()
	s.level = int(d.get("level", s.level))
	s.experience = int(d.get("experience", s.experience))
	s.max_hp = int(d.get("max_hp", s.max_hp))
	s.hp = int(d.get("hp", s.max_hp))
	s.attack = int(d.get("attack", s.attack))
	s.defense = int(d.get("defense", s.defense))
	s.speed = int(d.get("speed", s.speed))
	s.magic = int(d.get("magic", s.magic))
	s.resistance = int(d.get("resistance", s.resistance))
	s.move_speed = float(d.get("move_speed", s.move_speed))
	var e: Variant = d.get("extra", {})
	s.extra = (RpgUtil.restore_numbers(e) as Dictionary) if e is Dictionary else {}
	return s
