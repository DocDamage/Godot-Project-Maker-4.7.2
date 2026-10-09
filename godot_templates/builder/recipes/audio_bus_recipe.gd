extends RefCounted
## Builds the audio bus layout (Master, Music, SFX, UI -> Master), the audio index that maps
## catalog audio asset ids to their files (res://rpggen/audio_index.json), the sound bank (slot ->
## file, custom slots included) and the surfaces table (ground asset id -> surface, from the tag
## `surface:<name>`; the footstep slot `sfx_step_<name>` plays on that ground, T13.16).

const RECIPE_VERSION := 3

const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const LAYOUT_PATH := "res://generated/audio/default_bus_layout.tres"
const INDEX_PATH := "res://rpggen/audio_index.json"
const BANK_PATH := "res://rpggen/sound_bank.json"
const SURFACES_PATH := "res://rpggen/surfaces.json"
const SURFACE_TAG := "surface:"
const BUSES: Array[String] = ["Music", "SFX", "UI"]

func outputs(_ctx: BuildContext) -> PackedStringArray:
	return PackedStringArray([LAYOUT_PATH, INDEX_PATH, BANK_PATH, SURFACES_PATH])

## {asset id: surface} of the active assets tagged `surface:<name>`.
func surfaces(ctx: BuildContext) -> Dictionary:
	var out := {}
	for a in ctx.catalog.assets():
		if a.get("status", "") in ["UNUSED", "MISSING"]:
			continue
		var eff: Dictionary = ctx.catalog.effective(a)
		var tags: Array = eff.get("tags", [])
		for tag: Variant in tags:
			var text := JsonUtil.to_str(tag)
			if text.begins_with(SURFACE_TAG) and text.length() > SURFACE_TAG.length():
				out[a["id"]] = text.substr(SURFACE_TAG.length())
				break
	return out

func _audio_assets(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for a in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(a)
		if eff.get("usage", "") == "audio" and not (a.get("status", "") in ["UNUSED", "MISSING"]):
			out.append(a)
	return out

func input_hash(ctx: BuildContext) -> String:
	var parts: Array = []
	for a in _audio_assets(ctx):
		parts.append([a["id"], a["path"], a.get("sha256", "")])
	return ctx.stable_hash({"v": RECIPE_VERSION, "audio": parts, "sounds": ctx.config.get("sounds", {}), "surfaces": surfaces(ctx)})

## {slot: res:// path} of the configured sound slots whose asset is still active ("" = cleared).
func sound_bank(ctx: BuildContext) -> Dictionary:
	var by_id := {}
	for a in _audio_assets(ctx):
		by_id[a["id"]] = "res://" + JsonUtil.to_str(a["path"])
	var bank := {}
	var sounds: Dictionary = ctx.config.get("sounds", {})
	for slot: Variant in sounds.keys():
		var asset_id := JsonUtil.to_str(sounds[slot])
		if asset_id != "" and by_id.has(asset_id):
			bank[slot] = by_id[asset_id]
	return bank

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	# The layout is made with the live AudioServer, then written out.
	while AudioServer.bus_count > 1:
		AudioServer.remove_bus(AudioServer.bus_count - 1)
	AudioServer.set_bus_name(0, "Master")
	for bus_name in BUSES:
		AudioServer.add_bus()
		var idx := AudioServer.bus_count - 1
		AudioServer.set_bus_name(idx, bus_name)
		AudioServer.set_bus_send(idx, "Master")
	var layout := AudioServer.generate_bus_layout()
	DirAccess.make_dir_recursive_absolute(LAYOUT_PATH.get_base_dir())
	var err := ResourceSaver.save(layout, LAYOUT_PATH)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": LAYOUT_PATH, "err": err}, LAYOUT_PATH))
	var index := {}
	for a in _audio_assets(ctx):
		index[a["id"]] = "res://" + JsonUtil.to_str(a["path"])
	var werr := JsonUtil.write(INDEX_PATH, index)
	if werr != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": INDEX_PATH, "err": werr}, INDEX_PATH))
	var bank_err := JsonUtil.write(BANK_PATH, sound_bank(ctx))
	if bank_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": BANK_PATH, "err": bank_err}, BANK_PATH))
	var surfaces_err := JsonUtil.write(SURFACES_PATH, surfaces(ctx))
	if surfaces_err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": SURFACES_PATH, "err": surfaces_err}, SURFACES_PATH))
	return issues
