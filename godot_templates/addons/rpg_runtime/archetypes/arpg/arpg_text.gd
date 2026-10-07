class_name RpgArpgText
extends RefCounted
## Text of the action-RPG archetype. Every sentence is a translation key; the English text in
## RpgArpgStrings.KEYS is the fallback, so the text also reads correctly where the translations are
## not registered yet (tests).

static func t(key: String, args: Array = []) -> String:
	var text := TranslationServer.translate(key)
	if text == key and RpgArpgStrings.KEYS.has(key):
		text = RpgArpgStrings.KEYS[key]
	if args.is_empty() or not text.contains("%"):
		return text
	return text % args

## Display name of an item: its translated name key, else the id made readable.
static func item_name(def: RpgItemDefinition, item_id: StringName) -> String:
	if def != null and def.display_name != "":
		var text := TranslationServer.translate(def.display_name)
		if text != def.display_name:
			return text
		if not def.display_name.to_upper() == def.display_name:
			return def.display_name
	return String(item_id).capitalize()
