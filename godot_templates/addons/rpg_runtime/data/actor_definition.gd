class_name RpgActorDefinition
extends Resource

@export var id: StringName
@export var display_name: String
@export var sprite_frames: SpriteFrames
@export var portrait: Texture2D
@export var base_stats: RpgStats

@export_group("Battle (turn-based)")
## The skills the actor knows: {skill id: the level it is learned at} (game/data/skills/<id>.tres).
## Enemies use theirs through behavior (weights and turn_based_rules) instead.
@export var skills: Dictionary = {}
## {element: rate}: 2 = weak, 0.5 = resists, 0 = immune, negative = absorbs. Unlisted = 1.
@export var element_rates: Dictionary = {}
## Statuses that never take hold (RpgBattleStatus names: poison, sleep, ...).
@export var status_immune: Array[StringName] = []
## The element of a plain attack (a weapon's element replaces it).
@export var attack_element: StringName = &""
## A status a plain attack may inflict, with this chance (0..1).
@export var attack_status: StringName = &""
@export var attack_status_chance: float = 0.0

## The skill ids known at `level`, sorted by the level they are learned at, then by id.
func skills_at(level: int) -> Array[StringName]:
	var known: Array = []
	for skill_id: Variant in skills.keys():
		var learned := RpgUtil.to_int(skills[skill_id])
		if learned <= level:
			known.append([learned, str(skill_id)])
	known.sort()
	var out: Array[StringName] = []
	for pair: Array in known:
		out.append(StringName(str(pair[1])))
	return out
