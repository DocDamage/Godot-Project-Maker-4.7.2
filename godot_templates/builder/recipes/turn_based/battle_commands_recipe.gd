extends RefCounted
## Seeds the five battle commands as resources under game/data/battle_commands/ and the starter
## skills under game/data/skills/ (user_seed: written once, then yours to retune: label, priority,
## targets; MP cost, power, element, status). The battle also runs without them.

const RECIPE_VERSION := 2

const SeedUtil := preload("../../lib/seed_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const DIR := "res://game/data/battle_commands/"
const SCRIPT_DIR := "res://addons/rpg_runtime/archetypes/turn_based/commands/"
const COMMANDS: Array[String] = ["attack", "defend", "item", "skill", "run"]
const SKILLS_DIR := "res://game/data/skills/"
const SKILL_DEF := "res://addons/rpg_runtime/archetypes/turn_based/skill_definition.gd"

## The starter skills (RpgSkillDefinition fields; kind 0 physical, 1 magic, 2 heal, 3 status;
## targets 1 one enemy, 2 one ally). The hero knows fire, the companion cure, sleep and fire; venom
## is for enemies. Their names are SKILL_<ID>_NAME keys (RpgBattleStrings has the English text).
const SKILLS := {
	"fire": {"kind": 1, "targets": 1, "mp_cost": 3, "power": 8, "element": "fire"},
	"cure": {"kind": 2, "targets": 2, "mp_cost": 3, "power": 8, "cures": ["poison"]},
	"sleep": {"kind": 3, "targets": 1, "mp_cost": 4, "status": "sleep", "status_chance": 0.75},
	"venom": {"kind": 0, "targets": 1, "mp_cost": 0, "power": 0, "status": "poison", "status_chance": 0.5},
}

static func path_of(command_id: String) -> String:
	return DIR + command_id + ".tres"

static func skill_path(skill_id: String) -> String:
	return SKILLS_DIR + skill_id + ".tres"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for c in COMMANDS:
		out.append(path_of(c))
	for skill_id: String in SKILLS:
		out.append(skill_path(skill_id))
	return SeedUtil.missing(out)

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "commands": COMMANDS, "skills": SKILLS})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	for command_id in COMMANDS:
		var path := path_of(command_id)
		if FileAccess.file_exists(path):
			continue
		var command := SeedUtil.make("%s%s_command.gd" % [SCRIPT_DIR, command_id])
		var err := SeedUtil.save(command, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	for skill_id: String in SKILLS:
		var path := skill_path(skill_id)
		if FileAccess.file_exists(path):
			continue
		var err := SeedUtil.save(make_skill(skill_id), path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

static func make_skill(skill_id: String) -> Resource:
	var fields: Dictionary = SKILLS[skill_id]
	var skill := SeedUtil.make(SKILL_DEF)
	skill.set("id", StringName(skill_id))
	skill.set("display_name", "SKILL_%s_NAME" % skill_id.to_upper())
	skill.set("description", "SKILL_%s_DESC" % skill_id.to_upper())
	for key: String in fields:
		var value: Variant = fields[key]
		match key:
			"element", "status":
				skill.set(key, StringName(str(value)))
			"cures":
				var cures: Array[StringName] = []
				for status: Variant in value:
					cures.append(StringName(str(status)))
				skill.set(key, cures)
			_:
				skill.set(key, value)
	return skill
