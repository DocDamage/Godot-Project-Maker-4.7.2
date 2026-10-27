@tool
class_name RpgItemSet
extends Resource
## A set of gear (1.5.0): pieces that name it in their `set_id` give `bonuses` when enough of them
## are worn at once by the same actor. Files live in game/data/item_sets/<id>.tres.

@export var id: StringName
@export var title: String  # a tr() key
## [{pieces: int, modifiers: [{stat, add, mul}]}]: every row whose `pieces` the actor wears
## counts (two pieces give the row of 2; three give the rows of 2 and 3).
@export var bonuses: Array[Dictionary] = []

## The modifiers `worn` pieces give: those of every row with `pieces` up to `worn`.
func modifiers_for(worn: int) -> Array:
	var out: Array = []
	for row in bonuses:
		if worn >= RpgUtil.to_int(row.get("pieces", 0)) and RpgUtil.to_int(row.get("pieces", 0)) > 0:
			out.append_array(RpgUtil.to_array(row.get("modifiers", [])))
	return out

## The smallest number of pieces that gives a bonus (0 for a set without bonuses).
func first_bonus_at() -> int:
	var least := 0
	for row in bonuses:
		var pieces := RpgUtil.to_int(row.get("pieces", 0))
		if pieces > 0 and (least == 0 or pieces < least):
			least = pieces
	return least

## What is wrong with the set, one sentence each.
func problems() -> Array[String]:
	var out: Array[String] = []
	if id == &"":
		out.append("the set has no id")
	if first_bonus_at() == 0:
		out.append("the set gives no bonus: give a row of bonuses a number of pieces, 1 or more")
	for row in bonuses:
		for raw: Variant in RpgUtil.to_array(row.get("modifiers", [])):
			if str(RpgUtil.to_dict(raw).get("stat", "")) == "":
				out.append("a bonus of %d pieces names no stat" % RpgUtil.to_int(row.get("pieces", 0)))
	return out

## The set as plain data, and back (the dock's JSON export and import).
func to_dict() -> Dictionary:
	return {"id": String(id), "title": title, "bonuses": bonuses.duplicate(true)}

static func from_dict(data: Dictionary) -> RpgItemSet:
	var made := RpgItemSet.new()
	made.id = StringName(str(data.get("id", "")))
	made.title = str(data.get("title", ""))
	for raw: Variant in RpgUtil.to_array(data.get("bonuses", [])):
		if raw is Dictionary:
			made.bonuses.append(RpgUtil.to_dict(raw).duplicate(true))
	return made
