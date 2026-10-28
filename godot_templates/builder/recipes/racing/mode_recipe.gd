extends RefCounted
## The combat mode's scene of a racing game: boot adds it under SceneRouter as `combat`. It is
## RpgRacingMode with the paths of the lists of tracks and whether a player can be put out of
## the championship.
##
## With the option *Racers and spectators* (T18.19) it also writes who drives which car
## (`generated/data/drivers.json`, read by RpgRacePeople): a name and a face for every driver,
## the packs' people chosen by the seed (no one twice while there are enough), and the people
## who stand along the tracks. A race without the option writes nothing more.

const RECIPE_VERSION := 2

const BuildContext := preload("../../lib/build_context.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const Paths := preload("../../lib/paths.gd")
const ArcadeBuild := preload("../arcade/arcade_build.gd")
const RaceBuild := preload("racing_build.gd")

const DRIVERS_PATH := "res://generated/data/drivers.json"
## The names of the rivals' drivers, shuffled by the seed.
const DRIVER_NAMES: Array[String] = ["Ada", "Bram", "Cleo", "Dario", "Edda", "Finn", "Greta", "Hugo", "Iris", "Jules", "Kit", "Lena", "Milo", "Nell", "Otto", "Pia"]
const PEOPLE_ROLES: Array[String] = ["PLAYER", "NPC"]

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([ArcadeBuild.MODE_PATH])
	if RaceBuild.racers(ctx):
		out.append(DRIVERS_PATH)
	return out

func input_hash(ctx: BuildContext) -> String:
	var key := {"v": RECIPE_VERSION, "kind": "racing", "elimination": RaceBuild.elimination(ctx)}
	if RaceBuild.racers(ctx):
		key["racers"] = drivers(ctx)
	return ctx.stable_hash(key)

func build(ctx: BuildContext) -> Array:
	var properties := {"elimination": RaceBuild.elimination(ctx)}
	if not RaceBuild.racers(ctx):
		return ArcadeBuild.save_mode(ctx, RaceBuild.MODE_SCRIPT, properties)
	properties["racers"] = true
	var issues := ArcadeBuild.save_mode(ctx, RaceBuild.MODE_SCRIPT, properties)
	var err := JsonUtil.write(DRIVERS_PATH, drivers(ctx))
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": DRIVERS_PATH, "err": err}, DRIVERS_PATH))
	return issues

## The packs' people (players and villagers that have sprite frames), by id.
static func people(ctx: BuildContext) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for role in PEOPLE_ROLES:
		for asset in ArcadeBuild.assets(ctx, role):
			var eff := ctx.catalog.effective(asset)
			if JsonUtil.to_str(eff.get("usage", "")) == "sprite" and not JsonUtil.to_dict(eff.get("animations", {})).is_empty():
				out.append(asset)
	return out

## The face of a person: the pack's PORTRAIT of it (`portrait_of:<id>`), {} without one.
static func portrait(ctx: BuildContext, person_id: String) -> Dictionary:
	for asset in ArcadeBuild.assets(ctx, "PORTRAIT"):
		var tags := JsonUtil.to_array(ctx.catalog.effective(asset).get("tags", []))
		if tags.has("portrait_of:" + person_id):
			var frame := ArcadeBuild.frame_size(ctx, asset)
			return {"path": "res://" + JsonUtil.to_str(asset.get("path", "")), "region": [0, 0, frame.x, frame.y]}
	return {}

## What drivers.json holds: {"drivers": [{id, name, frames, portrait, colour}], "people":
## [frames, ...]}. The player's driver is the player's person when the packs have one; every
## rival's is one of the others, by the seed; a driver without a person is drawn in the colour
## of its car (`frames` "").
static func drivers(ctx: BuildContext) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = JsonUtil.to_int(ctx.config.get("seed", 12345)) + 1819
	var everyone := people(ctx)
	var pool: Array[Dictionary] = []
	var player: Dictionary = {}
	for asset in everyone:
		if player.is_empty() and JsonUtil.to_str(ctx.catalog.effective(asset).get("role", "")) == "PLAYER":
			player = asset
		else:
			pool.append(asset)
	# shuffled by the seed (Array.shuffle uses the global generator)
	for i in range(pool.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var swap := pool[i]
		pool[i] = pool[j]
		pool[j] = swap
	var names: Array[String] = DRIVER_NAMES.duplicate()
	for i in range(names.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var swap: String = names[i]
		names[i] = names[j]
		names[j] = swap
	var list: Array = [_driver(ctx, "player", "", player, Color(1.0, 0.85, 0.3))]
	for n in RaceBuild.rivals(ctx):
		var person: Dictionary = pool[n % pool.size()] if not pool.is_empty() else {}
		list.append(_driver(ctx, "rival_%d" % (n + 1), names[n % names.size()], person, RaceBuild.TINTS[n % RaceBuild.TINTS.size()]))
	var crowd: Array = []
	for asset in everyone:
		crowd.append(Paths.SPRITE_FRAMES_DIR + "%s.tres" % JsonUtil.to_str(asset["id"]))
	return {"drivers": list, "people": crowd}

static func _driver(ctx: BuildContext, id: String, driver_name: String, person: Dictionary, colour: Color) -> Dictionary:
	var person_id := JsonUtil.to_str(person.get("id", ""))
	return {
		"id": id,
		"name": driver_name,
		"frames": Paths.SPRITE_FRAMES_DIR + "%s.tres" % person_id if person_id != "" else "",
		"portrait": portrait(ctx, person_id) if person_id != "" else {},
		"colour": [snappedf(colour.r, 0.01), snappedf(colour.g, 0.01), snappedf(colour.b, 0.01)],
	}
