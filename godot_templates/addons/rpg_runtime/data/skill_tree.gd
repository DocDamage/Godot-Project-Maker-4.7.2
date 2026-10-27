@tool
class_name RpgSkillTree
extends Resource
## A skill tree (1.5.0): skills on a grid of rows and columns, each with ranks bought with skill
## points. Files live in game/data/skill_trees/<id>.tres; GameState keeps what each actor learned
## (skill_ranks) and the points it has (skill_points), and adds the bonuses of what is learned to
## the actor's stats.
##
## The rules: a rank costs `cost` points; a skill needs the ranks its `requires` names; row r
## opens once `points_per_row` * r points are spent in the rows above it. Unlearning a rank gives
## its points back, and is refused when another learned skill needs it or a learned row would
## close.

const OK := ""
const UNKNOWN := "unknown"
const MAX_RANK := "max_rank"
const NO_POINTS := "no_points"
const NEEDS := "needs"  # a requirement is missing
const ROW_LOCKED := "row_locked"
const NOT_LEARNED := "not_learned"
const NEEDED := "needed"  # another learned skill, or a learned row, needs this rank

@export var id: StringName
@export var title: String  # a tr() key
## [{id, title (a tr() key), description (a tr() key), cell: [column, row], max_rank (1),
## cost (points a rank, 1), requires: {skill id: rank}, bonuses: [{stat, add, mul}] (each rank
## gives them once more: add * rank, mul ^ rank), skill: a battle skill id learned with the
## first rank ("" for none)}].
@export var skills: Array[Dictionary] = []
## Points spent in the rows above that open each next row (0: every row is open).
@export var points_per_row: int = 0
## The gold a reset of the tree costs (0: free; -1: it cannot be reset).
@export var reset_gold: int = 0

func skill(skill_id: StringName) -> Dictionary:
	for row in skills:
		if StringName(str(row.get("id", ""))) == skill_id:
			return row
	return {}

func skill_ids() -> Array[StringName]:
	var out: Array[StringName] = []
	for row in skills:
		out.append(StringName(str(row.get("id", ""))))
	return out

static func cell_of(row: Dictionary) -> Vector2i:
	var cell := RpgUtil.to_array(row.get("cell", [0, 0]))
	return Vector2i(RpgUtil.to_int(cell[0]) if cell.size() > 0 else 0, RpgUtil.to_int(cell[1]) if cell.size() > 1 else 0)

static func max_rank_of(row: Dictionary) -> int:
	return maxi(1, RpgUtil.to_int(row.get("max_rank", 1)))

static func cost_of(row: Dictionary) -> int:
	return maxi(0, RpgUtil.to_int(row.get("cost", 1)))

static func requires_of(row: Dictionary) -> Dictionary:
	return RpgUtil.to_dict(row.get("requires", {}))

## The rank of a skill in `ranks` ({skill id: rank}, what an actor learned of this tree).
static func rank_in(ranks: Dictionary, skill_id: StringName) -> int:
	return RpgUtil.to_int(ranks.get(String(skill_id), 0))

## The points spent in the tree (each rank at its skill's cost).
func spent(ranks: Dictionary) -> int:
	var total := 0
	for row in skills:
		total += rank_in(ranks, StringName(str(row.get("id", "")))) * cost_of(row)
	return total

## The points spent in the rows above `row`.
func spent_above(ranks: Dictionary, row: int) -> int:
	var total := 0
	for skill_row in skills:
		if cell_of(skill_row).y < row:
			total += rank_in(ranks, StringName(str(skill_row.get("id", "")))) * cost_of(skill_row)
	return total

## The points that must be spent in the rows above `row` before it opens.
func row_needs(row: int) -> int:
	return maxi(0, points_per_row * row)

## True when row `row` is open with `ranks`.
func row_open(ranks: Dictionary, row: int) -> bool:
	return spent_above(ranks, row) >= row_needs(row)

## Why one more rank of `skill_id` cannot be learned with `points`, or "".
func learn_problem(ranks: Dictionary, points: int, skill_id: StringName) -> String:
	var row := skill(skill_id)
	if row.is_empty():
		return UNKNOWN
	if rank_in(ranks, skill_id) >= max_rank_of(row):
		return MAX_RANK
	if not missing(ranks, skill_id).is_empty():
		return NEEDS
	if not row_open(ranks, cell_of(row).y):
		return ROW_LOCKED
	if points < cost_of(row):
		return NO_POINTS
	return OK

## The requirements of `skill_id` that `ranks` does not meet: {skill id: rank needed}.
func missing(ranks: Dictionary, skill_id: StringName) -> Dictionary:
	var out := {}
	var needs := requires_of(skill(skill_id))
	for other: Variant in needs:
		if rank_in(ranks, StringName(str(other))) < RpgUtil.to_int(needs[other]):
			out[str(other)] = RpgUtil.to_int(needs[other])
	return out

## Why one rank of `skill_id` cannot be unlearned, or "": it is not learned, another learned skill
## needs the rank, or a row with learned skills would no longer be open.
func unlearn_problem(ranks: Dictionary, skill_id: StringName) -> String:
	var row := skill(skill_id)
	if row.is_empty():
		return UNKNOWN
	var rank := rank_in(ranks, skill_id)
	if rank <= 0:
		return NOT_LEARNED
	var after := ranks.duplicate()
	after[String(skill_id)] = rank - 1
	for other in skills:
		var other_id := StringName(str(other.get("id", "")))
		if rank_in(after, other_id) > 0 and not missing(after, other_id).is_empty():
			return NEEDED
	for other in skills:
		var other_id := StringName(str(other.get("id", "")))
		if rank_in(after, other_id) > 0 and not row_open(after, cell_of(other).y):
			return NEEDED
	return OK

## The modifiers of what `ranks` learned: each skill's `bonuses` once a rank.
func bonuses_of(ranks: Dictionary) -> Array:
	var out: Array = []
	for row in skills:
		var rank := rank_in(ranks, StringName(str(row.get("id", ""))))
		if rank <= 0:
			continue
		for raw: Variant in RpgUtil.to_array(row.get("bonuses", [])):
			var bonus := RpgUtil.to_dict(raw)
			var scaled := {"stat": str(bonus.get("stat", ""))}
			if bonus.has("add"):
				scaled["add"] = RpgUtil.to_float(bonus["add"]) * rank
			if bonus.has("mul"):
				scaled["mul"] = pow(RpgUtil.to_float(bonus["mul"]), rank)
			out.append(scaled)
	return out

## The battle skills `ranks` learned (a skill's `skill`, from its first rank), in tree order.
func battle_skills_of(ranks: Dictionary) -> Array[StringName]:
	var out: Array[StringName] = []
	for row in skills:
		var battle_skill := StringName(str(row.get("skill", "")))
		if battle_skill != &"" and rank_in(ranks, StringName(str(row.get("id", "")))) > 0 and not out.has(battle_skill):
			out.append(battle_skill)
	return out

## What is wrong with the tree, one sentence each: no id, skills without an id or with the id or
## the cell of another, a requirement that names no skill or one that is not on an earlier row.
func problems() -> Array[String]:
	var out: Array[String] = []
	if id == &"":
		out.append("the tree has no id")
	var seen: Array[String] = []
	var cells: Dictionary = {}  # cell -> where the first skill on it was
	for i in skills.size():
		var row := skills[i]
		var skill_id := str(row.get("id", ""))
		var where := "skill %d (%s)" % [i + 1, skill_id if skill_id != "" else "no id"]
		if skill_id == "":
			out.append("%s needs an id" % where)
		elif seen.has(skill_id):
			out.append("%s repeats the id of an earlier skill" % where)
		seen.append(skill_id)
		var cell := cell_of(row)
		if cells.has(cell):
			out.append("%s is on the cell of %s" % [where, cells[cell]])
		else:
			cells[cell] = where
	for i in skills.size():
		var row := skills[i]
		var needs := requires_of(row)
		for other: Variant in needs:
			var needed := skill(StringName(str(other)))
			if needed.is_empty():
				out.append("skill %d (%s) requires the unknown skill '%s'" % [i + 1, str(row.get("id", "")), str(other)])
			elif cell_of(needed).y >= cell_of(row).y:
				out.append("skill %d (%s) requires '%s', which is not on an earlier row" % [i + 1, str(row.get("id", "")), str(other)])
	return out

## The tree as plain data, and back (the dock's JSON export and import).
func to_dict() -> Dictionary:
	return {"id": String(id), "title": title, "skills": skills.duplicate(true), "points_per_row": points_per_row, "reset_gold": reset_gold}

static func from_dict(data: Dictionary) -> RpgSkillTree:
	var tree := RpgSkillTree.new()
	tree.id = StringName(str(data.get("id", "")))
	tree.title = str(data.get("title", ""))
	for raw: Variant in RpgUtil.to_array(data.get("skills", [])):
		if raw is Dictionary:
			tree.skills.append(RpgUtil.to_dict(raw).duplicate(true))
	tree.points_per_row = RpgUtil.to_int(data.get("points_per_row", 0))
	tree.reset_gold = RpgUtil.to_int(data.get("reset_gold", 0))
	return tree
