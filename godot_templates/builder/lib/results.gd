extends RefCounted
## Collects issues and items for one phase and writes the results JSON (02_SCHEMAS.md §6).

const ErrorCodes := preload("error_codes.gd")
const JsonUtil := preload("json_util.gd")

var phase: String = "build"
var issues: Array[Dictionary] = []
var items: Array[Dictionary] = []
var _start_ms: int = 0

func _init(p_phase: String = "build") -> void:
	phase = p_phase
	_start_ms = Time.get_ticks_msec()

## Replaces {key} placeholders in a template with values from detail. Unknown keys stay as-is.
static func format_template(template: String, detail: Dictionary) -> String:
	var out := template
	for key: Variant in detail.keys():
		out = out.replace("{%s}" % str(key), str(detail[key]))
	return out

func add_issue(code: String, detail: Dictionary = {}, file: String = "") -> void:
	var info: Variant = ErrorCodes.CODES.get(code)
	var issue := {}
	if info == null:
		push_error("[RPG-RESULTS] unknown error code %s" % code)
		issue = {"code": code, "severity": "error", "message": "Unknown error code %s." % code, "fix": ""}
	else:
		var entry: Dictionary = info
		var d := detail.duplicate()
		if file != "" and not d.has("file"):
			d["file"] = file
		issue = {
			"code": code,
			"severity": entry["severity"],
			"message": format_template(JsonUtil.to_str(entry["message"]), d),
			"fix": entry["fix"],
		}
	if file != "":
		issue["file"] = file
	issues.append(issue)

## Adds issue dictionaries produced by recipes ({code, severity, message, file?, fix?}).
func add_issues(list: Array) -> void:
	for issue: Dictionary in list:
		issues.append(issue)

func add_item(item: Dictionary) -> void:
	items.append(item)

func has_errors() -> bool:
	for issue in issues:
		if issue.get("severity", "") == "error":
			return true
	return false

var ok: bool:
	get:
		return not has_errors()

func to_dict() -> Dictionary:
	return {
		"results_version": 1,
		"phase": phase,
		"ok": ok,
		"started_ms": 0,
		"elapsed_ms": Time.get_ticks_msec() - _start_ms,
		"issues": issues,
		"items": items,
	}

func write(path: String) -> int:
	return JsonUtil.write(path, to_dict())
