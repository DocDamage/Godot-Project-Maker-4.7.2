extends RefCounted
## Console logging. The Python side parses lines that start with "[rpggen]".

static func info(msg: String) -> void:
	print("[rpggen] INFO %s" % msg)

static func warn(msg: String) -> void:
	print("[rpggen] WARN %s" % msg)

static func error(msg: String) -> void:
	print("[rpggen] ERROR %s" % msg)

## Progress for the Python side (T12.19): one line per recipe or check. It is not forwarded as a
## log line; the generator shows "<phase> <label> (i of n)" under the running phase.
static func step(phase: String, i: int, n: int, label: String) -> void:
	print("@rpggen step %s %d/%d %s" % [phase, i, n, label])
