extends RefCounted
## Translation-ready text. Seeds game/i18n/strings.tsv once (user_seed: tab-separated, header `keys<TAB>en`, one row
## per UI key plus the seeded content keys) and, on every build, turns the CSV into one Translation
## resource per locale under res://generated/i18n/ (registered by RpgStrings at boot).
##
## A .tsv (not .csv) so Godot does not import it as a translation and litter the project with
## .import/.translation files. CSV import is not used: Translation resources are written directly (T6.13 fallback, see
## docs/godot_api_verified.md), so a headless build needs no second import phase.

const RECIPE_VERSION := 2

const SeedUtil := preload("../lib/seed_util.gd")
const DataRecipe := preload("data_recipe.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const CSV_PATH := "res://game/i18n/strings.tsv"
const OUT_DIR := "res://generated/i18n/"
const STRINGS_SCRIPT := "res://addons/rpg_runtime/ui/strings.gd"
const ITEMS_DIR := "res://game/data/items"
const ARCHETYPE_STRINGS := {
	"turn_based": "res://addons/rpg_runtime/archetypes/turn_based/battle_strings.gd",
	"arpg": "res://addons/rpg_runtime/archetypes/arpg/arpg_strings.gd",
	"metroidvania": "res://addons/rpg_runtime/archetypes/metroidvania/metroidvania_strings.gd",
}

## [[locale, path]] for the locales in the CSV header (every column after `keys`).
func _locales() -> Array:
	var out: Array = []
	var csv := _read_csv()
	var locales: Array = csv.get("locales", ["en"])
	for loc: Variant in locales:
		out.append([loc, OUT_DIR + "strings_%s.tres" % JsonUtil.to_str(loc).replace("-", "_")])
	return out

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	if not FileAccess.file_exists(CSV_PATH):
		out.append(CSV_PATH)
	for pair: Array in _locales():
		var locale_path: String = pair[1]
		out.append(locale_path)
	return out

func input_hash(ctx: BuildContext) -> String:
	# While the CSV is missing, hash the text that will be written, so the hash is the same before
	# and after the seeding and the next build skips this recipe.
	var text := FileAccess.get_file_as_string(CSV_PATH) if FileAccess.file_exists(CSV_PATH) else _csv_text(_seed_rows(ctx))
	return ctx.stable_hash({"v": RECIPE_VERSION, "csv": text.sha256_text(), "seed_strings": DataRecipe.SEED_STRINGS, "keys": _ui_keys(), "archetype_keys": _archetype_keys(ctx)})

## Text keys of the archetype's runtime folder (archetypes/<name>/<prefix>_strings.gd with a KEYS table).
func _archetype_keys(ctx: BuildContext) -> Dictionary:
	var path: String = ARCHETYPE_STRINGS.get(JsonUtil.to_str(ctx.config.get("archetype", "")), "")
	if path == "" or not ResourceLoader.exists(path):
		return {}
	var script := load(path) as GDScript
	return script.get_script_constant_map().get("KEYS", {}) if script != null else {}

func _ui_keys() -> Dictionary:
	var script := load(STRINGS_SCRIPT) as GDScript
	return script.get_script_constant_map().get("KEYS", {}) if script != null else {}

## Rows to seed: UI keys, the data recipe's content keys, then item name/description keys found in
## game/data/items/ that look like translation keys (humanized when unknown).
func _seed_rows(ctx: BuildContext) -> Dictionary:
	var rows: Dictionary = _ui_keys().duplicate()
	rows.merge(_archetype_keys(ctx))
	for key: Variant in DataRecipe.SEED_STRINGS.keys():
		rows[key] = DataRecipe.SEED_STRINGS[key]
	var dir := DirAccess.open(ITEMS_DIR)
	if dir != null:
		var files := dir.get_files()
		files.sort()
		for f in files:
			var item := load(ITEMS_DIR + "/" + f.trim_suffix(".remap")) as Resource
			if item == null:
				continue
			for prop: String in ["display_name", "description"]:
				var key := JsonUtil.to_str(item.get(prop))
				if key != "" and not rows.has(key) and _looks_like_key(key):
					rows[key] = key.trim_prefix("ITEM_").trim_suffix("_NAME").trim_suffix("_DESC").replace("_", " ").capitalize()
	return rows

static func _looks_like_key(text: String) -> bool:
	var re := RegEx.new()
	re.compile("^[A-Z][A-Z0-9_]*$")
	return re.search(text) != null

## {"locales": [...], "rows": {key: {locale: text}}} from the CSV, or {} when it does not exist.
func _read_csv() -> Dictionary:
	if not FileAccess.file_exists(CSV_PATH):
		return {}
	var f := FileAccess.open(CSV_PATH, FileAccess.READ)
	if f == null:
		return {}
	var header := f.get_csv_line("\t")
	var locales: Array = []
	for i in range(1, header.size()):
		if String(header[i]).strip_edges() != "":
			locales.append(String(header[i]).strip_edges())
	var rows := {}
	while not f.eof_reached():
		var line := f.get_csv_line("\t")
		if line.size() == 0 or String(line[0]).strip_edges() == "":
			continue
		var entry := {}
		for i in locales.size():
			entry[locales[i]] = String(line[i + 1]) if i + 1 < line.size() else ""
		rows[String(line[0]).strip_edges()] = entry
	f.close()
	return {"locales": locales, "rows": rows}

func _csv_text(rows: Dictionary) -> String:
	var lines: PackedStringArray = ["keys\ten"]
	var keys: Array = rows.keys()
	keys.sort()
	for key: Variant in keys:
		var cell := JsonUtil.to_str(rows[key])
		if cell.contains("\t") or cell.contains("\"") or cell.contains("\n"):
			cell = '"%s"' % cell.replace('"', '""')
		lines.append("%s\t%s" % [key, cell])
	return "\n".join(lines) + "\n"

func _write_csv(rows: Dictionary) -> int:
	DirAccess.make_dir_recursive_absolute(CSV_PATH.get_base_dir())
	var f := FileAccess.open(CSV_PATH, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(_csv_text(rows))
	f.close()
	return OK

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if not FileAccess.file_exists(CSV_PATH):
		var werr := _write_csv(_seed_rows(ctx))
		if werr != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": CSV_PATH, "err": werr}, CSV_PATH))
			return issues
	var data := _read_csv()
	DirAccess.make_dir_recursive_absolute(OUT_DIR)
	var locales: Array = data.get("locales", [])
	for loc: Variant in locales:
		var trans := Translation.new()
		trans.locale = JsonUtil.to_str(loc)
		var rows: Dictionary = data["rows"]
		for key: Variant in rows.keys():
			var row: Dictionary = rows[key]
			var text := JsonUtil.to_str(row.get(loc, ""))
			if text != "":
				trans.add_message(JsonUtil.to_name(key), text)
		var path: String = OUT_DIR + "strings_%s.tres" % JsonUtil.to_str(loc).replace("-", "_")
		var err := ResourceSaver.save(trans, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	# Not registered in the project settings: a .tres translation fails to load that early (probe,
	# docs/godot_api_verified.md). RpgStrings.register_translations() adds them when the game boots.
	ProjectSettings.set_setting("internationalization/locale/fallback", "en")
	var save_err := ProjectSettings.save()
	if save_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": "project.godot", "err": save_err}, "project.godot"))
	return issues
