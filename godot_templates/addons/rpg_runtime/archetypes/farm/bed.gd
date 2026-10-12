class_name RpgBed
extends StaticBody2D
## The farmer's bed (T17.08). `interact` with it ends the day (RpgDayEnd.sleep): the night
## passes, the energy is full, the game is saved and the morning shows what the bin earned.
## Layers: world (1) + interactables (5).
##
## The bed is also where a farmer who stayed up to 2:00 wakes: the map and the place are kept
## in the flags of the game state (`farm_bed`), written by the first bed a game sees and by
## every bed that is slept in, so the farmer can pass out on any map.

const FLAG_ENTITY := "farm_bed"

## Where the farmer stands when it wakes, from the bed's origin (its foot), and where it looks:
## away from the bed, so that the key that closes the morning's summary does not sleep again.
@export var wake_offset: Vector2 = Vector2(0.0, 8.0)
@export var wake_facing: String = "down"
## The cells the bed lies on, wide and long, its foot on the lowest row (what a map recipe
## keeps free for it; the game does not read it).
@export var footprint: Vector2i = Vector2i(1, 2)

func _ready() -> void:
	if home(RpgUtil.state()).is_empty():
		remember()

func wake_position() -> Vector2:
	return RpgUtil.world_position(self) + wake_offset

## The scene file of the map the bed stands in ("" in a scene that was never saved).
func map_path() -> String:
	var node := get_parent()
	while node != null:
		if node is RpgMapRoot:
			return node.scene_file_path
		node = node.get_parent()
	return ""

## Makes this bed the one the farmer wakes at.
func remember() -> void:
	var state := RpgUtil.state()
	if state == null:
		return
	var at := wake_position()
	state.set_flag(FLAG_ENTITY, "map", map_path())
	state.set_flag(FLAG_ENTITY, "x", at.x)
	state.set_flag(FLAG_ENTITY, "y", at.y)
	state.set_flag(FLAG_ENTITY, "facing", wake_facing)
	state.set_flag(FLAG_ENTITY, "known", true)

## Where the farmer wakes: `{map, position, facing}`, or {} in a game that has seen no bed.
static func home(state: RpgGameState) -> Dictionary:
	if state == null or not RpgUtil.to_bool(state.get_flag(FLAG_ENTITY, "known", false)):
		return {}
	return {
		"map": RpgUtil.to_str(state.get_flag(FLAG_ENTITY, "map", "")),
		"position": Vector2(RpgUtil.to_float(state.get_flag(FLAG_ENTITY, "x", 0.0)), RpgUtil.to_float(state.get_flag(FLAG_ENTITY, "y", 0.0))),
		"facing": RpgUtil.to_str(state.get_flag(FLAG_ENTITY, "facing", "down")),
	}

## `interact` (RpgInteraction calls this): the farmer goes to sleep.
func interact(_actor: Node = null) -> void:
	var day_end := RpgDayEnd.current()
	if day_end != null:
		day_end.sleep(self)
