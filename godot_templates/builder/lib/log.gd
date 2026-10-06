extends RefCounted
## Console logging. The Python side parses lines that start with "[rpggen]".

static func info(msg: String) -> void:
	print("[rpggen] INFO %s" % msg)

static func warn(msg: String) -> void:
	print("[rpggen] WARN %s" % msg)

static func error(msg: String) -> void:
	print("[rpggen] ERROR %s" % msg)
