extends RefCounted
## Seeds the five battle commands as resources under game/data/battle_commands/ (user_seed: written
## once, then yours to retune: label, priority, targets). The battle also runs without them.

const RECIPE_VERSION := 1

const SeedUtil := preload("../../lib/seed_util.gd")
const BuildContext := preload("../../lib/build_context.gd")

const DIR := "res://game/data/battle_commands/"
const SCRIPT_DIR := "res://addons/rpg_runtime/archetypes/turn_based/commands/"
const COMMANDS: Array[String] = ["attack", "defend", "item", "skill", "run"]

static func path_of(command_id: String) -> String:
	return DIR + command_id + ".tres"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	for c in COMMANDS:
		out.append(path_of(c))
	return SeedUtil.missing(out)

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "commands": COMMANDS})

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
	return issues
