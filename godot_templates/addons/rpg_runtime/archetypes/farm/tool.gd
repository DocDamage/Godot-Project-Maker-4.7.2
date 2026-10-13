class_name RpgFarmTool
extends RefCounted
## A tool of the farm (T17.04): a name, what it costs, how long its use takes and what cells it
## acts on. The four tools (tools/) say the last two; the farmer does the rest: it asks
## `can_use` (a tool that would do nothing costs nothing), calls `apply` and pays the energy.

## The item this tool is.
var id: StringName = &""
var energy_cost: int = 2
var use_time_s: float = 0.35
## The animation of the farmer's sheet that shows its use (`hoe_down`, ...), when it has one.
var animation: String = ""
## The sound slot a use that did something plays (RpgFarmSounds); none by default.
var sound: StringName = &""
## The states of a cell (RpgField.state_of) the tool works on.
var acts_on: Array[String] = []
## What it clears away (RpgField.CLEAR_META).
var clears: Array[String] = []

## True when using the tool on `cell` would change something.
func can_use(field: RpgField, cell: Vector2i) -> bool:
	if field == null:
		return false
	return acts_on.has(field.state_of(cell)) or (not clears.is_empty() and field.clearable_at(cell, clears) != null)

## The energy using the tool on `cell` costs.
func cost(_field: RpgField, _cell: Vector2i) -> int:
	return energy_cost

## Uses the tool on `cell`. False when nothing changed.
func apply(_field: RpgField, _cell: Vector2i) -> bool:
	return false
