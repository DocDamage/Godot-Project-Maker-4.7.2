extends RefCounted
## Assertion helper handed to every test method. Records failures; never throws.

var failures: Array[String] = []

func fail(msg: String) -> void:
	failures.append(msg)

func ok(cond: bool, msg: String = "") -> void:
	if not cond:
		fail("expected true%s" % (": " + msg if msg != "" else ""))

func eq(a: Variant, b: Variant, msg: String = "") -> void:
	if typeof(a) != typeof(b) and not (_is_number(a) and _is_number(b)):
		fail("expected %s == %s (types differ)%s" % [var_to_str(a), var_to_str(b), (": " + msg) if msg != "" else ""])
		return
	if a != b:
		fail("expected %s == %s%s" % [var_to_str(a), var_to_str(b), (": " + msg) if msg != "" else ""])

func near(a: float, b: float, eps: float = 0.001) -> void:
	if absf(a - b) > eps:
		fail("expected %s ~= %s (eps %s)" % [a, b, eps])

static func _is_number(v: Variant) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT
