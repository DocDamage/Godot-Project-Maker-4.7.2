class_name RpgDialogueJson
extends RefCounted
## Editor convenience: builds a dialogue resource from JSON text.
##
## {"lines": [{"id": "a", "speaker": "Ana", "text": "Hi", "condition": "gold>=1",
##             "events": ["give_gold:5"], "next": "b",
##             "choices": [{"text": "Yes", "next": "b", "condition": ""}]}]}
## A bare top-level array of lines is accepted too. Returns null for invalid JSON.

static func from_json(text: String) -> RpgDialogueResource:
	var parsed: Variant = JSON.parse_string(text)
	var raw_lines: Array = []
	if parsed is Dictionary and parsed.get("lines") is Array:
		raw_lines = parsed["lines"]
	elif parsed is Array:
		raw_lines = parsed
	else:
		push_error("[RPG-DLG] dialogue JSON must be an array or an object with a 'lines' array")
		return null
	var res := RpgDialogueResource.new()
	for raw in raw_lines:
		if not (raw is Dictionary):
			continue
		var line := RpgDialogueLine.new()
		line.id = StringName(str(raw.get("id", "")))
		line.speaker = str(raw.get("speaker", ""))
		line.text = str(raw.get("text", ""))
		line.condition = str(raw.get("condition", ""))
		line.next = StringName(str(raw.get("next", "")))
		var events := PackedStringArray()
		for e in raw.get("events", []):
			events.append(str(e))
		line.events = events
		for raw_choice in raw.get("choices", []):
			if not (raw_choice is Dictionary):
				continue
			var choice := RpgDialogueChoice.new()
			choice.text = str(raw_choice.get("text", ""))
			choice.next = StringName(str(raw_choice.get("next", "")))
			choice.condition = str(raw_choice.get("condition", ""))
			line.choices.append(choice)
		res.lines.append(line)
	return res
