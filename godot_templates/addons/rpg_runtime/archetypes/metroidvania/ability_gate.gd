class_name RpgAbilityGate
extends Marker2D
## A marker on a place that needs an ability to pass: a ledge too high, a gap too wide, a wall of
## breakable blocks, a shaft. The gate itself is only the room's geometry; the marker says what the
## world planner put there (the room map shows its letter, and a person editing the room can see
## why the ledge is where it is). It does nothing at run time.

## The ability that passes this place.
@export var ability: StringName = &""
## What the place is: "ledge", "gap", "wall" or "shaft".
@export var kind: String = "ledge"

func is_passable() -> bool:
	var state := RpgUtil.state()
	return ability == &"" or (state != null and state.has_ability(ability))
