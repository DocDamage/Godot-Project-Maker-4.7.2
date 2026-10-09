extends RefCounted
## The `ctx` of a custom recipe (T12.60): what a script in res://game/builder_recipes/ may use.
## This API is stable for rpggen 1.x; RECIPE_API_VERSION changes only when it breaks (a recipe can
## check `ctx.api_version`). Everything else in the builder is internal.
##
## A recipe writes under res://game/ (yours: rpggen never rewrites it) or res://generated/custom/
## (rpggen's: rewritten on every build, so build it from your inputs each time). The write
## helpers refuse any other place and report it. See docs/recipes.md.

const BuildContext := preload("build_context.gd")
const CatalogReader := preload("catalog_reader.gd")
const SceneUtil := preload("scene_util.gd")
const JsonUtil := preload("json_util.gd")
const Log := preload("log.gd")

const RECIPE_API_VERSION := 1
const GAME_DIR := "res://game/"
const CUSTOM_DIR := "res://generated/custom/"

## The API version this builder offers (RECIPE_API_VERSION).
var api_version: int = RECIPE_API_VERSION
## The file name of the running recipe, without ".gd".
var recipe_name: String = ""
## A copy of rpggen/generator_config.json (project_name, archetype, base_tile_size, features, ...).
var config: Dictionary = {}
## The project's seed: use it for any random choice so that a rebuild makes the same result.
var rng_seed: int = 0

var _build: BuildContext = null
var _written: PackedStringArray = []
var _problems: PackedStringArray = []

func _init(build: BuildContext, p_recipe_name: String) -> void:
	_build = build
	recipe_name = p_recipe_name
	config = build.config.duplicate(true)
	rng_seed = JsonUtil.to_int(config.get("seed", 12345))

## The project's name.
func project_name() -> String:
	return JsonUtil.to_str(config.get("project_name", ""))

## The base tile size in pixels.
func tile_size() -> int:
	return JsonUtil.to_int(config.get("base_tile_size", 16))

## Every asset of the catalog (copies): id, path, kind, status and "facets" (the effective ones:
## role, usage, grid, frame, animations, collision, ...).
func assets() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for asset in _build.catalog.assets():
		out.append(_public(asset))
	return out

## One asset by id ({} when there is none).
func asset(id: String) -> Dictionary:
	var found := _build.catalog.asset(id)
	return _public(found) if not found.is_empty() else {}

## The assets with this role ("NPC", "DECORATION", ...).
func assets_with_role(role: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for asset in _build.catalog.assets_by_role(role):
		out.append(_public(asset))
	return out

## The file of an asset inside the project ("res://assets/packs/..."), or "".
func asset_file(id: String) -> String:
	var found := _build.catalog.asset(id)
	return "res://" + JsonUtil.to_str(found.get("path", "")) if not found.is_empty() else ""

static func _public(asset: Dictionary) -> Dictionary:
	return {
		"id": asset.get("id", ""),
		"path": asset.get("path", ""),
		"kind": asset.get("kind", ""),
		"status": asset.get("status", ""),
		"facets": CatalogReader.effective(asset).duplicate(true),
	}

## True for a path a recipe may write.
static func allowed(path: String) -> bool:
	var clean := path.simplify_path()
	if clean.contains(".."):
		return false
	return clean.begins_with(GAME_DIR) or clean.begins_with(CUSTOM_DIR)

func _check(path: String) -> bool:
	if allowed(path):
		return true
	fail("%s is outside res://game/ and res://generated/custom/" % path)
	return false

## Saves `root` (and its children) as a scene; `root` is freed. False when it failed.
func save_scene(root: Node, path: String) -> bool:
	if not _check(path):
		root.free()
		return false
	var err := SceneUtil.save_scene(root, path)
	if err != OK:
		fail("could not save %s (error %d)" % [path, err])
		return false
	_written.append(path)
	return true

## Saves a resource (.tres). False when it failed.
func save_resource(resource: Resource, path: String) -> bool:
	if not _check(path):
		return false
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var err := ResourceSaver.save(resource, path)
	if err != OK:
		fail("could not save %s (error %d)" % [path, err])
		return false
	_written.append(path)
	return true

## Writes a text file (UTF-8, LF). False when it failed.
func write_text(path: String, text: String) -> bool:
	if not _check(path):
		return false
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		fail("could not write %s (error %d)" % [path, FileAccess.get_open_error()])
		return false
	f.store_string(text)
	f.close()
	_written.append(path)
	return true

## A line in the build log.
func say(message: String) -> void:
	Log.info("[%s] %s" % [recipe_name, message])

## Stops the build with BUILD-002 naming this recipe (the recipe should return after it).
func fail(reason: String) -> void:
	_problems.append(reason)

## What the recipe wrote, and what went wrong (for the builder).
func written() -> PackedStringArray:
	return _written

func problems() -> PackedStringArray:
	return _problems
