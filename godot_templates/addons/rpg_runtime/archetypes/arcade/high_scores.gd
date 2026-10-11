class_name RpgArcadeHighScores
extends RefCounted
## The ten best runs of an arcade game: name, score and the stage the run ended in. Kept in the
## shared section of the save manager (not in a slot: every saved game sees the same table).

const MAX_ENTRIES := 10
const KEY := "high_scores"
const NAME_LENGTH := 8
const DEFAULT_NAME := "AAA"

## A name as the table keeps it: trimmed, without line breaks, at most NAME_LENGTH long.
static func clean_name(raw: String) -> String:
	var text := raw.replace("\n", " ").replace("\t", " ").strip_edges()
	return text.left(NAME_LENGTH) if text != "" else DEFAULT_NAME

## A table read from anywhere, as the game uses it: only real entries, the best first, ten at most.
static func clean(raw: Variant) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for entry: Variant in RpgUtil.to_array(raw):
		if not (entry is Dictionary):
			continue
		var d: Dictionary = entry
		var points: Variant = d.get("score")
		if not (points is int or points is float):
			continue
		var score := RpgUtil.to_int(points)
		if score <= 0:
			continue
		out.append({
			"name": clean_name(RpgUtil.to_str(d.get("name", ""))),
			"score": score,
			"stage": maxi(1, RpgUtil.to_int(d.get("stage", 1), 1)),
		})
	_sort(out)
	return out.slice(0, MAX_ENTRIES)

## The best first; of two equal scores the one that was there first stays in front.
static func _sort(table: Array[Dictionary]) -> void:
	var order: Array[int] = []
	for i in table.size():
		order.append(i)
	var scores: Array[int] = []
	for entry in table:
		scores.append(RpgUtil.to_int(entry["score"]))
	order.sort_custom(func(a: int, b: int) -> bool:
		return scores[a] > scores[b] if scores[a] != scores[b] else a < b)
	var sorted: Array[Dictionary] = []
	for i in order:
		sorted.append(table[i])
	table.assign(sorted)

## The place `score` would take in `table` (0 is the best), or -1 when it does not make the table.
static func rank_of(table: Array[Dictionary], score: int) -> int:
	if score <= 0:
		return -1
	for i in table.size():
		if score > RpgUtil.to_int(table[i]["score"]):
			return i
	return table.size() if table.size() < MAX_ENTRIES else -1

## Puts a run into `table` when it is good enough. Returns its place, or -1.
static func insert(table: Array[Dictionary], player_name: String, score: int, stage: int) -> int:
	var rank := rank_of(table, score)
	if rank < 0:
		return -1
	table.insert(rank, {"name": clean_name(player_name), "score": score, "stage": maxi(1, stage)})
	while table.size() > MAX_ENTRIES:
		table.pop_back()
	return rank

## The table of this game (empty when nothing was ever written, or without a save manager).
static func read() -> Array[Dictionary]:
	var save := RpgUtil.save_manager()
	if save == null:
		return []
	return clean(save.shared_value(KEY, []))

static func write(table: Array[Dictionary]) -> bool:
	var save := RpgUtil.save_manager()
	return save != null and save.set_shared_value(KEY, table)

## A finished run: into the table of the game when it is good enough. Returns its place, or -1.
static func submit(player_name: String, score: int, stage: int) -> int:
	var table := read()
	var rank := insert(table, player_name, score, stage)
	if rank >= 0:
		write(table)
	return rank
