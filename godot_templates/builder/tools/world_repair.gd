extends SceneTree
## Headless world repair (T13.24), run by rpggen after a generation and by `rpggen-cli
## repair-world`:
##
##   godot --headless --path <project> --script res://generated/builder/tools/world_repair.gd -- [--dry-run] [--only=<maps>]
##
## It plans the repairs of addons/rpg_project_tools/tools/world_repair.gd for every map under
## res://game/maps and applies those whose map it may write: every map, or with `--only` the
## listed ones (project-relative paths, comma separated: the maps nobody edited). The result is
## printed as one line, "[rpggen] WORLD_REPAIR {json}", and (unless `--dry-run`) written to
## res://rpggen/world_repair.json: {repairs, skipped, unfixable}, each a list of
## {kind, map, node, what}. `skipped` are repairs of maps the run may not write.

const Repair := preload("res://addons/rpg_project_tools/tools/world_repair.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")

const RESULT_PATH := "res://rpggen/world_repair.json"
const MARK := "[rpggen] WORLD_REPAIR "

func _init() -> void:
	var dry_run := false
	var limited := false
	var only: Array[String] = []
	for arg in OS.get_cmdline_user_args():
		if arg == "--dry-run":
			dry_run = true
		elif arg.begins_with("--only="):
			limited = true
			for rel in arg.trim_prefix("--only=").split(",", false):
				only.append("res://" + rel)
	var result := run(ContentChecks.MAPS_DIR, Repair.read_plan(), dry_run, limited, only)
	print(MARK + JSON.stringify(result))
	if not dry_run:
		var f := FileAccess.open(RESULT_PATH, FileAccess.WRITE)
		if f != null:
			f.store_string(JSON.stringify(result, "  ") + "\n")
			f.close()
	quit(0)

## Plans and (unless `dry_run`) applies the repairs of the maps under `maps_dir`. With `limited`
## only the maps in `only` are written; a repair of another map is listed under "skipped".
static func run(maps_dir: String, plan: Dictionary, dry_run: bool, limited: bool, only: Array[String], start: String = Repair.START) -> Dictionary:
	var maps := ContentChecks.list_files(maps_dir, ["tscn"])
	var roots := {}
	var instance_of := func(path: String) -> Node:
		if not roots.has(path):
			var packed := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
			roots[path] = packed.instantiate(PackedScene.GEN_EDIT_STATE_MAIN) if packed != null else null
		return roots[path]
	var actions := Repair.plan_repairs(maps, plan, instance_of, start)
	var repairs: Array = []
	var skipped: Array = []
	var unfixable: Array = []
	var changed: Array[String] = []
	for action in actions:
		var map := str(action["map"])
		if str(action["kind"]) == "unfixable":
			unfixable.append(Repair.line(action))
		elif limited and not only.has(map):
			skipped.append(Repair.line(action))
		else:
			repairs.append(Repair.line(action))
			if not dry_run:
				var root: Node = instance_of.call(map)
				if root != null:
					Repair.apply(action, root)
					if not changed.has(map):
						changed.append(map)
	for map in changed:
		var packed := PackedScene.new()
		var root: Node = roots[map]
		if packed.pack(root) == OK:
			ResourceSaver.save(packed, map)
	for path: String in roots.keys():
		var root: Node = roots[path]
		if root != null:
			root.free()
	return {"repairs": repairs, "skipped": skipped, "unfixable": unfixable}
