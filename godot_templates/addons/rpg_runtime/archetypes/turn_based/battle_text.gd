class_name RpgBattleText
extends RefCounted
## Battle text. Every sentence is a translation key; the English text in RpgBattleStrings.KEYS is the
## fallback, so the battle also reads correctly where translations are not registered yet (tests).

static func t(key: String, args: Array = []) -> String:
	var text := TranslationServer.translate(key)
	if text == key and RpgBattleStrings.KEYS.has(key):
		text = RpgBattleStrings.KEYS[key]
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
