extends RefCounted
## Builds the audio bus layout (Master, Music, SFX, UI -> Master) and the audio index that maps
## catalog audio asset ids to their files (res://rpggen/audio_index.json).

const RECIPE_VERSION := 1

const JsonUtil := preload("../lib/json_util.gd")

const LAYOUT_PATH := "res://generated/audio/default_bus_layout.tres"
const INDEX_PATH := "res://rpggen/audio_index.json"
const BUSES := ["Music", "SFX", "UI"]

func outputs(_ctx) -> PackedStringArray:
	return PackedStringArray([LAYOUT_PATH, INDEX_PATH])

func _audio_assets(ctx) -> Array:
	var out: Array = []
	for a in ctx.catalog.assets():
		var eff: Dictionary = ctx.catalog.effective(a)
		if eff.get("usage", "") == "audio" and not (a.get("status", "") in ["UNUSED", "MISSING"]):
			out.append(a)
	return out

func input_hash(ctx) -> String:
	var parts: Array = []
	for a in _audio_assets(ctx):
		parts.append([a["id"], a["path"], a.get("sha256", "")])
	return ctx.stable_hash({"v": RECIPE_VERSION, "audio": parts})

func build(ctx) -> Array:
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
		index[a["id"]] = "res://" + String(a["path"])
	var werr := JsonUtil.write(INDEX_PATH, index)
	if werr != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": INDEX_PATH, "err": werr}, INDEX_PATH))
	return issues
