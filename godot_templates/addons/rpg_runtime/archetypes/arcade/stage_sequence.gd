class_name RpgArcadeStageSequence
extends RefCounted
## The stages of an arcade run, in order: game/data/stages.json, written by the recipe of the kind
## from its plan. Each stage is a dictionary: `scene` (the stage's scene), `title`, `axis`,
## `speed`, `length`, `exit`, `par_time_s`, `waves` (see RpgArcadeWave) and `boss`.

var stages: Array[Dictionary] = []
var index := 0

static func from_array(raw: Array) -> RpgArcadeStageSequence:
	var sequence := RpgArcadeStageSequence.new()
	for entry: Variant in raw:
		if entry is Dictionary:
			var stage: Dictionary = entry
			sequence.stages.append(stage)
	return sequence

## The sequence of `path` (empty when the file is missing or is not a list of stages).
static func load_file(path: String) -> RpgArcadeStageSequence:
	if path == "" or not FileAccess.file_exists(path):
		return RpgArcadeStageSequence.new()
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Dictionary:
		var d: Dictionary = parsed
		parsed = d.get("stages", [])
	if not (parsed is Array):
		push_warning("[RPG-ARCADE] %s is not a list of stages" % path)
		return RpgArcadeStageSequence.new()
	var list: Array = RpgUtil.restore_numbers(parsed)
	return from_array(list)

## The stages of `listed` and, after them, those of `planned` whose scene `listed` does not
## have: what a list says of a stage is never changed by the plan.
static func merged(listed: Array[Dictionary], planned: Array[Dictionary]) -> Array[Dictionary]:
	var out: Array[Dictionary] = listed.duplicate()
	var have := {}
	for entry in listed:
		have[RpgUtil.to_str(entry.get("scene", ""))] = true
	for entry in planned:
		if not have.has(RpgUtil.to_str(entry.get("scene", ""))):
			out.append(entry)
	return out

func size() -> int:
	return stages.size()

func stage_at(i: int) -> Dictionary:
	return stages[i] if i >= 0 and i < stages.size() else {}

func current() -> Dictionary:
	return stage_at(index)

func scene_of(i: int) -> String:
	return RpgUtil.to_str(stage_at(i).get("scene", ""))

## Which stage has the scene `path`, or -1.
func index_of_scene(path: String) -> int:
	for i in stages.size():
		if scene_of(i) == path:
			return i
	return -1

func is_last() -> bool:
	return index >= stages.size() - 1

## On to the next stage. False when the current one was the last.
func advance() -> bool:
	if is_last():
		return false
	index += 1
	return true
