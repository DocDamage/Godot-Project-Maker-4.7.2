class_name RpgSkillDefinition
extends Resource
## A skill of the turn-based battle (one .tres per skill in the project's skills folder, which
## RpgBattleController.SKILLS_DIR names). Actors list the skills they know
## (RpgActorDefinition.skills); enemies use them through their behavior.
##
##   PHYSICAL  damage from attack + power against defense: the hit roll, crits
##   MAGIC     damage power + magic x 2 - resistance: always hits
##   HEAL      restores power + magic x 2 HP
##   STATUS    no damage: only the status and the cures
##
## Every kind may also inflict `status` (with `status_chance`) and remove `cures`.

enum Kind { PHYSICAL, MAGIC, HEAL, STATUS }

@export var id: StringName
@export var display_name: String  # a tr() key or plain text
@export var description: String
@export var kind: Kind = Kind.MAGIC
## RpgBattleCommand.TARGET_*: self, one enemy, one ally, all enemies, all allies.
@export_enum("Self", "One enemy", "One ally", "All enemies", "All allies") var targets: int = 1
@export var mp_cost: int = 0
@export var power: int = 0
## Free name (fire, ice, ...): the targets' element_rates scale the damage.
@export var element: StringName = &""
## A status (RpgBattleStatus name) inflicted on each target, with this chance (0..1).
@export var status: StringName = &""
@export var status_chance: float = 1.0
## Statuses removed from each target ("all" = every harmful one).
@export var cures: Array[StringName] = []

## The shown name: the translated display name, else the id made readable (also for a key such as
## SKILL_FIRE_NAME that has no translation yet).
func label() -> String:
	if display_name != "":
		var text := String(TranslationServer.translate(display_name))
		if text != display_name or display_name.to_upper() != display_name:
			return text
	return String(id).capitalize()

## Problems of a skill as text (an empty list when it is fine); the content check reports them.
func problems() -> PackedStringArray:
	var out := PackedStringArray()
	if id == &"":
		out.append("no id")
	if targets < 0 or targets > 4:
		out.append("targets %d is not 0..4" % targets)
	if status != &"" and not RpgBattleStatus.is_known(status):
		out.append("unknown status '%s'" % status)
	for cured in cures:
		if cured != &"all" and not RpgBattleStatus.is_known(cured):
			out.append("cures the unknown status '%s'" % cured)
	if kind == Kind.STATUS and status == &"" and cures.is_empty():
		out.append("a status skill with no status and nothing to cure")
	if mp_cost < 0:
		out.append("mp_cost is negative")
	return out

## Every skill in `dir_path`: {id: RpgSkillDefinition}. The file name is the id when the skill has none.
static func load_dir(dir_path: String) -> Dictionary:
	var out: Dictionary = {}
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return out
	var files := dir.get_files()
	files.sort()
	for f in files:
		var file := f.trim_suffix(".remap")
		if not file.ends_with(".tres"):
			continue
		var skill := load(dir_path + "/" + file) as RpgSkillDefinition
		if skill == null:
			continue
		if skill.id == &"":
			skill.id = StringName(file.get_basename())
		if not out.has(skill.id):
			out[skill.id] = skill
	return out
