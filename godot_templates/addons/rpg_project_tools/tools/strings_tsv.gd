@tool
extends RefCounted
## The project's texts, game/i18n/strings.tsv (the dock's Items tab, 1.5.0): a header `keys<TAB>en`
## (more locales after it), then one row a key. Read the English of a key; add rows for new keys
## without touching the others (the translations recipe turns the file into Translations at the
## next build).

const PATH := "res://game/i18n/strings.tsv"

## {"locales": [..], "rows": {key: [cells after the key]}, "order": [keys in file order]}.
static func read(path: String = PATH) -> Dictionary:
	var out := {"locales": ["en"], "rows": {}, "order": []}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return out
	var header := f.get_csv_line("\t")
	var locales: Array = []
	for i in range(1, header.size()):
		locales.append(header[i].strip_edges())
	out["locales"] = locales if not locales.is_empty() else ["en"]
	var rows: Dictionary = out["rows"]
	var order: Array = out["order"]
	while not f.eof_reached():
		var line := f.get_csv_line("\t")
		if line.size() == 0 or line[0].strip_edges() == "":
			continue
		var key := line[0].strip_edges()
		rows[key] = Array(line.slice(1))
		if not order.has(key):
			order.append(key)
	f.close()
	return out

## The English (first column) text of `key`, or "" when the file has no row for it.
static func english(key: String, path: String = PATH) -> String:
	var row: Array = RpgUtil.to_dict(read(path)["rows"]).get(key, [])
	return str(row[0]) if not row.is_empty() else ""

static func _cell(text: String) -> String:
	if text.contains("\t") or text.contains("\"") or text.contains("\n"):
		return '"%s"' % text.replace('"', '""')
	return text

## Appends a row for each key of `texts` ({key: English text}) the file does not have yet (the
## other locales empty). The file is made when it is missing. Returns the keys added.
static func add(texts: Dictionary, path: String = PATH) -> Array[String]:
	var added: Array[String] = []
	var known := read(path)
	var rows: Dictionary = known["rows"]
	var locales: Array = known["locales"]
	var lines: PackedStringArray = []
	for key: Variant in texts:
		if str(key) == "" or rows.has(str(key)):
			continue
		var cells: PackedStringArray = [str(key), _cell(str(texts[key]))]
		for i in range(1, locales.size()):
			cells.append("")
		lines.append("\t".join(cells))
		added.append(str(key))
	if lines.is_empty():
		return added
	var existed := FileAccess.file_exists(path)
	var text := FileAccess.get_file_as_string(path) if existed else "keys\t%s\n" % "\t".join(PackedStringArray(locales))
	if text != "" and not text.ends_with("\n"):
		text += "\n"
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return [] as Array[String]
	f.store_string(text + "\n".join(lines) + "\n")
	f.close()
	return added
