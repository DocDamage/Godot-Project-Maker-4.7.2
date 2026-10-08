extends RefCounted
## The Credits screen's data (T12.51). Every build writes res://generated/data/credits.tres from the
## licences of the catalog's packs (what the licence files say, with the Audit page's corrections)
## and the lines of game/data/credits_extra.tsv, which it seeds once (user_seed: yours to fill in).
## The licence rules mirror rpggen/core/licenses.py (effective, label, license_url).

const RECIPE_VERSION := 1

const JsonUtil := preload("../lib/json_util.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const OUT_PATH := "res://generated/data/credits.tres"
const EXTRA_PATH := "res://game/data/credits_extra.tsv"
const CREDITS_SCRIPT := "res://addons/rpg_runtime/data/credits.gd"
const EXTRA_SEED := "section\ttext\n# Your own credits: a section, a tab, then the line. The Credits screen shows them before\n# the asset packs, in this order. Lines that start with # are notes; remove the # to use one.\n# Made by\tYour name\n# Music\tA composer\n# Thanks\tEveryone who played the demo\n"

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([OUT_PATH])
	if not FileAccess.file_exists(EXTRA_PATH):
		out.append(EXTRA_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "packs": pack_entries(ctx.catalog.catalog), "extra": _extra_text()})

func _extra_text() -> String:
	return FileAccess.get_file_as_string(EXTRA_PATH) if FileAccess.file_exists(EXTRA_PATH) else EXTRA_SEED

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if not FileAccess.file_exists(EXTRA_PATH):
		DirAccess.make_dir_recursive_absolute(EXTRA_PATH.get_base_dir())
		var f := FileAccess.open(EXTRA_PATH, FileAccess.WRITE)
		if f == null:
			issues.append(ctx.make_issue("BUILD-004", {"file": EXTRA_PATH, "err": FileAccess.get_open_error()}, EXTRA_PATH))
			return issues
		f.store_string(EXTRA_SEED)
		f.close()
	var credits := SeedUtil.make(CREDITS_SCRIPT)
	var script: GDScript = credits.get_script()
	credits.set("packs", SeedUtil.dict_array(pack_entries(ctx.catalog.catalog)))
	credits.set("extra", script.call("parse_extra", _extra_text()))
	var err := SeedUtil.save(credits, OUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": OUT_PATH, "err": err}, OUT_PATH))
	return issues

## One entry per pack of the catalog, sorted by pack id.
static func pack_entries(catalog: Dictionary) -> Array:
	var packs: Array = catalog.get("packs", [])
	var out: Array = []
	for raw: Variant in packs:
		if not (raw is Dictionary):
			continue
		var pack: Dictionary = raw
		var found := effective(pack.get("license", {}), pack.get("license_overrides", {}))
		var license_id := JsonUtil.to_str(found.get("license_id", ""))
		out.append({
			"pack_id": JsonUtil.to_str(pack.get("pack_id", "")),
			"name": display_name(JsonUtil.to_str(pack.get("pack_id", ""))),
			"author": JsonUtil.to_str(found.get("author", "")).strip_edges(),
			"url": JsonUtil.to_str(found.get("url", "")).strip_edges(),
			"license": label(license_id),
			"license_url": license_url(license_id),
			"attribution_required": JsonUtil.to_bool(found.get("attribution_required", false)),
		})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return str(a["pack_id"]) < str(b["pack_id"]))
	return out

## "forest_tiles" -> "Forest Tiles".
static func display_name(pack_id: String) -> String:
	return pack_id.replace("_", " ").replace("-", " ").capitalize()

## The detected licence with the corrections; a licence chosen without "credit required" brings
## its own (licenses.effective).
static func effective(detected: Variant, overrides: Variant) -> Dictionary:
	var out := {"license_id": "", "author": "", "url": "", "attribution_required": false}
	if detected is Dictionary:
		var found: Dictionary = detected
		out.merge(found, true)
	var over: Dictionary = overrides if overrides is Dictionary else {}
	out.merge(over, true)
	if over.has("license_id") and not over.has("attribution_required"):
		var required: Variant = requires_attribution(JsonUtil.to_str(over["license_id"]))
		if required != null:
			out["attribution_required"] = required
	return out

## true / false when the licence decides whether the game must credit the pack, null when its
## wording does (licenses.requires_attribution).
static func requires_attribution(license_id: String) -> Variant:
	if license_id.begins_with("CC-BY") or license_id.begins_with("OGA-BY") or license_id == "MIT":
		return true
	if license_id == "CC0-1.0" or license_id == "rpgmaker":
		return false
	return null

## "CC-BY-SA-4.0" -> "CC BY-SA 4.0" (licenses.label).
static func label(license_id: String) -> String:
	match license_id:
		"":
			return "Unknown licence"
		"commercial":
			return "Commercial licence"
		"rpgmaker":
			return "RPG Maker terms"
	var cut := license_id.rfind("-")
	var version := license_id.substr(cut + 1) if cut >= 0 else ""
	var re := RegEx.new()
	re.compile("^\\d\\.\\d$")
	if re.search(version) == null:
		return license_id
	var head := license_id.substr(0, cut)
	if head.begins_with("CC-"):
		return "CC %s %s" % [head.substr(3), version]
	return "%s %s" % [head, version]

## The licence's own page (licenses.license_url).
static func license_url(license_id: String) -> String:
	var re := RegEx.new()
	re.compile("^CC-(BY(?:-NC)?(?:-SA|-ND)?)-(\\d\\.\\d)$")
	var m := re.search(license_id)
	if m != null:
		return "https://creativecommons.org/licenses/%s/%s/" % [m.get_string(1).to_lower(), m.get_string(2)]
	if license_id == "CC0-1.0":
		return "https://creativecommons.org/publicdomain/zero/1.0/"
	if license_id.begins_with("OGA-BY"):
		return "https://opengameart.org/content/oga-by-30-faq"
	if license_id == "MIT":
		return "https://opensource.org/license/mit"
	return ""
