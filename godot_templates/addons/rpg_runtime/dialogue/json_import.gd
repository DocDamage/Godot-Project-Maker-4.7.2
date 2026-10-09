class_name RpgDialogueJson
extends RefCounted
## Editor convenience: builds a dialogue resource from JSON text, and back (to_json, T12.61).
##
## {"lines": [{"id": "a", "speaker": "Ana", "text": "Hi", "condition": "gold>=1",
##             "events": ["give_gold:5"], "next": "b",
##             "choices": [{"text": "Yes", "next": "b", "condition": ""}]}]}
## A bare top-level array of lines is accepted too. Returns null for invalid JSON.

static func from_json(text: String) -> RpgDialogueResource:
	var parsed: Variant = JSON.parse_string(text)
	var raw_lines: Array = []
	var table: Dictionary = {}
	if parsed is Dictionary:
		table = parsed
	if table.get("lines") is Array:
		raw_lines = table["lines"]
	elif parsed is Array:
		raw_lines = parsed
	else:
		push_error("[RPG-DLG] dialogue JSON must be an array or an object with a 'lines' array")
		return null
	var res := RpgDialogueResource.new()
	for raw_line: Variant in raw_lines:
		if not (raw_line is Dictionary):
			continue
		var raw: Dictionary = raw_line
		var line := RpgDialogueLine.new()
		line.id = StringName(str(raw.get("id", "")))
		line.speaker = str(raw.get("speaker", ""))
		line.text = str(raw.get("text", ""))
		line.condition = str(raw.get("condition", ""))
		line.next = StringName(str(raw.get("next", "")))
		var portrait := str(raw.get("portrait", ""))
		if portrait != "" and ResourceLoader.exists(portrait):
			line.portrait = load(portrait) as Texture2D
		var events := PackedStringArray()
		var raw_events: Array = raw.get("events", [])
		for e: Variant in raw_events:
			events.append(str(e))
		line.events = events
		var raw_choices: Array = raw.get("choices", [])
		for raw_choice_value: Variant in raw_choices:
			if not (raw_choice_value is Dictionary):
				continue
			var raw_choice: Dictionary = raw_choice_value
			var choice := RpgDialogueChoice.new()
			choice.text = str(raw_choice.get("text", ""))
			choice.next = StringName(str(raw_choice.get("next", "")))
			choice.condition = str(raw_choice.get("condition", ""))
			line.choices.append(choice)
		res.lines.append(line)
	return res

## The resource as JSON (T12.61), the format from_json() reads: one object per line with the keys
## that hold something; a portrait is its resource path.
static func to_json(res: RpgDialogueResource) -> String:
	return JSON.stringify(to_dict(res), "  ", false) + "\n"

static func to_dict(res: RpgDialogueResource) -> Dictionary:
	var lines: Array = []
	for line in res.lines:
		var raw := {"text": line.text}
		if line.id != &"":
			raw["id"] = String(line.id)
		if line.speaker != "":
			raw["speaker"] = line.speaker
		if line.portrait != null and line.portrait.resource_path != "":
			raw["portrait"] = line.portrait.resource_path
		if line.condition != "":
			raw["condition"] = line.condition
		if not line.events.is_empty():
			raw["events"] = Array(line.events)
		if line.next != &"":
			raw["next"] = String(line.next)
		if not line.choices.is_empty():
			var choices: Array = []
			for choice in line.choices:
				var c := {"text": choice.text, "next": String(choice.next)}
				if choice.condition != "":
					c["condition"] = choice.condition
				choices.append(c)
			raw["choices"] = choices
		lines.append(raw)
	return {"lines": lines}

