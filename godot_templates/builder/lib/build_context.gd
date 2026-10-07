extends RefCounted
## Shared state for one builder run: parsed config/catalog, results, build state, helpers.

const Paths := preload("paths.gd")
const JsonUtil := preload("json_util.gd")
const Results := preload("results.gd")
const CatalogReader := preload("catalog_reader.gd")
const Log := preload("log.gd")

var builder_dir: String = ""
var config: Dictionary = {}
var catalog: RefCounted = null  # CatalogReader
var results: RefCounted = null  # Results
var build_state: Dictionary = {"build_state_version": 1, "outputs": {}}

func _init(p_builder_dir: String, phase: String = "build") -> void:
	builder_dir = p_builder_dir
	results = Results.new(phase)
	catalog = CatalogReader.new({})

## Reads CONFIG and CATALOG. On failure adds CAT-001 and returns false.
func load_inputs() -> bool:
	var cfg: Variant = JsonUtil.read(Paths.CONFIG)
	if not (cfg is Dictionary):
		results.add_issue("CAT-001", {"file": Paths.CONFIG, "reason": "missing or not a JSON object"}, Paths.CONFIG)
		return false
	var cat: Variant = JsonUtil.read(Paths.CATALOG)
	if not (cat is Dictionary):
		results.add_issue("CAT-001", {"file": Paths.CATALOG, "reason": "missing or not a JSON object"}, Paths.CATALOG)
		return false
	config = cfg
	catalog = CatalogReader.new(cat)
	return true

func load_build_state() -> void:
	var state: Variant = null
	if FileAccess.file_exists(Paths.BUILD_STATE):
		state = JsonUtil.read(Paths.BUILD_STATE)
	if state is Dictionary and state.get("outputs") is Dictionary:
		build_state = state
		# JSON parsing returns numbers as floats; keep the version an int so a rebuild without
		# changes writes the same bytes.
		build_state["build_state_version"] = 1
	else:
		build_state = {"build_state_version": 1, "outputs": {}}

func save_build_state() -> int:
	return JsonUtil.write(Paths.BUILD_STATE, build_state)

## True when the output was built from the same inputs last time and still exists.
func should_skip(out_path: String, input_hash: String) -> bool:
	var outputs: Dictionary = build_state["outputs"]
	return outputs.get(out_path, "") == input_hash and FileAccess.file_exists(out_path)

func record_output(out_path: String, input_hash: String) -> void:
	var outputs: Dictionary = build_state["outputs"]
	outputs[out_path] = input_hash

## Builds one issue dictionary (code, severity, message, fix, file) without adding it anywhere.
func make_issue(code: String, detail: Dictionary = {}, file: String = "") -> Dictionary:
	var scratch := Results.new("scratch")
	scratch.add_issue(code, detail, file)
	return scratch.issues[0]

## Stable hash of any JSON-like value (dictionary keys are sorted).
static func stable_hash(v: Variant) -> String:
	return JSON.stringify(v, "", true).sha256_text()

## Vector2i from a [x, y] array parsed from JSON (numbers arrive as floats).
static func vec2i(a: Variant) -> Vector2i:
	return Vector2i(int(a[0]), int(a[1]))
