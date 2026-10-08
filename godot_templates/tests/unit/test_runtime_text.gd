extends RefCounted
## Player-facing text of the runtime goes through tr() (T12.08): no literal in a notify() call.

const RUNTIME := "res://addons/rpg_runtime"

func _scripts(dir_path: String, out: Array) -> void:
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return
	for sub in dir.get_directories():
		_scripts(dir_path + "/" + sub, out)
	for f in dir.get_files():
		if f.ends_with(".gd"):
			out.append(dir_path + "/" + f)

func test_no_notify_call_takes_a_string_literal(t) -> void:
	var scripts := []
	_scripts(RUNTIME, scripts)
	t.ok(scripts.size() > 20, "the runtime scripts were found")
	var re := RegEx.new()
	# notify( followed by optional blanks and a quote character (double or single)
	re.compile("notify[(][ ]*[" + String.chr(34) + String.chr(39) + "]")
	var offenders := []
	for path in scripts:
		var text := FileAccess.get_file_as_string(path)
		for line in text.split("\n"):
			if line.strip_edges().begins_with("#") or line.contains("func notify"):
				continue
			if re.search(line) != null:
				offenders.append("%s: %s" % [path, line.strip_edges()])
	t.eq(offenders, [], "use tr() with a UI_ key for what the player reads")

func test_the_keys_of_the_messages_have_english_text(t) -> void:
	for key in ["UI_SAVE_DAMAGED_LOADED_BACKUP", "UI_SAVE_FROM_NEWER_VERSION", "UI_CANNOT_USE_NOW", "UI_CHEST_FOUND", "UI_CHEST_EMPTY"]:
		t.ok(RpgStrings.KEYS.has(key), key)
		t.ok(String(RpgStrings.english(key)) != key, key)
