# Changelog

## 1.0.0

* First stable release. The runtime is unchanged in behavior from 0.3.0; the version number now
  matches rpggen 1.0.0, the diagnostic bundle and the Windows export preset that ship with it.
* Regenerating a project made with 0.x asks for confirmation once (`--accept-runtime-upgrade`
  or the dialog in the wizard) because the major version changed.
* Before the release (M11): the action-RPG **heavy attack** (`secondary_attack`: 1.75x damage,
  1.5x knockback, slower swing); chests built from a two-frame strip, sheet or an `open`
  animation show their open picture; the action-RPG HUD uses a nine-sliced UI bar from the pack
  when there is one and sits on the project theme's panel.
* Sound slots: a sound bank (`rpggen/sound_bank.json`), `RpgAudio.play`, `play_ui_slot` and
  `play_music_slot` (silent no-ops for an unset slot), sounds for pick-ups, hits, attacks,
  level-ups, saving, chests, doors, menus (cursor, confirm, cancel) and footsteps, the map music
  of the map root, the battle music and the title music. New events: `chest_opened`,
  `door_used` and `attack_started`.
* A game-over screen (`RpgGameOver`, `RpgDefeatPolicy` shared by both archetypes): continue from
  the newest save, try the map again or quit to the title; smoke runs skip it.
* Autosave: a fourth save slot 0 beside slots 1 to 3, written when a map is entered (never during
  a battle, dialogue or fade, and at most every 10 s), listed first in the load menu; the
  Settings menu can turn it off. Slot numbers 1 to 3 are unchanged, save version stays 1.
* A second outdoor map `field_1.tscn` behind a gap in the east wall of a new starter map; screen
  shake and hit-stop on a landed heavy attack (Settings > Screen shake); a key prompt over what the
  player can interact with; the game version on the title screen; the map and play time in the
  pause menu.
* Review follow-ups (M12): a save over a **damaged** slot file no longer replaces the last good
  backup with it (the backup is made only from a file that verifies, and the new save is moved
  into place by renaming it over the old one); four messages that bypassed translation (a damaged
  save, a save from a newer version, "cannot use that now" and the chest text) now use the keys
  `UI_SAVE_DAMAGED_LOADED_BACKUP`, `UI_SAVE_FROM_NEWER_VERSION`, `UI_CANNOT_USE_NOW`,
  `UI_CHEST_FOUND` and `UI_CHEST_EMPTY`. Projects made earlier fall back to the English text.
* Fixed while running M11 against Godot 4.7.2: the interact prompt shows `E`, not
  `E - Physical`; `RpgAudio` lets go of its streams when it leaves the tree.
* Save and load screens (M12): a slot reads "Slot 2 — Village · Lv 3 · 1:12 played · 12 Oct 14:05"
  (the map's name, level, play time and the local time of saving); the header gained the optional
  fields `saved_unix` and `map_name` (a translation key from the new `RpgMapRoot.display_name`
  export, default `MAP_<ID>`; a map without a translation shows its file name), so
  `save_version` stays 1 and older saves still read (they show no date). Saving over a used slot
  asks for confirmation with the focus on "No"; a 160x90 picture of the screen is kept beside the
  slot (`slot_N.png`, not when headless) and shown on its button; the slot loops use
  `SaveManager.SLOTS`. New keys: `UI_LV`, `UI_PLAYED`, `UI_OVERWRITE_SAVE`, `UI_YES`, `UI_NO` and
  `UI_MONTH_1` to `UI_MONTH_12`. Fixed: a toast that was dropped to make room no longer logs an
  error when its timer ends.
* Equipment (M12): `GameState.equipment` ({actor id: {weapon, armor, accessory}}, keyed by actor for
  party members), `equip`, `unequip`, `equipped_modifiers`, `stat_of` / `effective_stat` and
  `equip_preview`. Items of the categories WEAPON, ARMOR and ACCESSORY go to their slot; the old
  piece returns to the inventory. Both combat systems read attack, defense (and, turn-based,
  speed) through `get_stat` with the worn modifiers (`RpgBattleActor.stat`, the hitbox and the
  hurtbox); enemies wear nothing. The inventory menu has an Equip button and the status menu lists
  the slots; both open `RpgEquipPicker`, which shows the stat changes (green gain, red loss) of
  the focused choice before it is confirmed. The save has the optional key `equipment` (an older
  save loads with empty slots; `save_version` stays 1). New keys: `UI_EQUIP`, `UI_EQUIPMENT`,
  `UI_TAKE_OFF`, `UI_SLOT_WEAPON`, `UI_SLOT_ARMOR`, `UI_SLOT_ACCESSORY`, `UI_NO_CHANGE`,
  `UI_NOTHING_TO_EQUIP`, `UI_CANNOT_EQUIP` and `UI_MOVE_SPEED`.
* Party members (M12, turn-based): `GameState.join_party` / `leave_party` (at most `MAX_PARTY` = 4
  characters, the player included; a member is built from `game/data/actors/<id>.tres`),
  `party_ids`, `in_party`, `actor_definition` / `actor_name`, `give_experience_to`, `revive_party`
  and `heal_party_full`. Dialogue events `join_party:<id>` and `leave_party:<id>`, the condition
  `party:<id>`, and the new event `party_changed`. In battle every member acts (the controller
  already built the party from `GameState.party`; it now uses their names and art), experience is
  shared (`give_experience` now grants it to the whole party), and a fallen member stands up at
  1 HP after a victory or an escape; the defeat policy revives or heals the whole party. The
  battle UI marks whose turn it is. The status menu pages through the members with its own
  equipment. `heal_full` heals everyone. The party was already in the save. The action RPG has no
  followers in 1.0. New keys: `UI_PARTY_JOINED` and `UI_PARTY_LEFT`. New turn-based projects get the
  actor "Mira" (`companion.tres`) and a villager choice that brings her along.
* Quest journal (M12): `RpgQuestDefinition` (`game/data/quests/<id>.tres`: a title key, ordered
  `stages` [{id, description key, complete_when condition}] and `rewards` {gold, experience,
  items}). `GameState.quests[id]` holds the current stage id, or `"done"`, so saves are unchanged
  (and the older `set_quest:` / `quest:` still work on the same dictionary). `quest_start`,
  `quest_set_stage`, `quest_complete` (rewards once), `refresh_quests` (a stage whose
  `complete_when` holds moves on by itself, and the last one completes the quest; it runs on flag,
  item, gold, level-up, dialogue and load events) and `journal_ids`. Dialogue events
  `quest_start:<id>`, `quest_stage:<id>:<stage>` and `quest_complete:<id>`; conditions
  `quest_active:<id>`, `quest_done:<id>` and `quest_stage:<id>:<stage>`; a toast for every
  start, stage change and completion; new event `quest_changed`. The pause menu has a Journal
  button (`journal_menu.tscn`: Active and Completed tabs, the stages of the quest in focus).
  New keys: `UI_JOURNAL`, `UI_QUESTS_ACTIVE`, `UI_QUESTS_DONE`, `UI_NO_QUESTS_ACTIVE`,
  `UI_NO_QUESTS_DONE`, `UI_QUEST_NEW`, `UI_QUEST_UPDATED` and `UI_QUEST_DONE`. New projects get the
  quest "The villager's errand" (talk, open the chest if the map has one, tell the villager).
* Shops (M12): `RpgShopDefinition` (`game/data/shops/<id>.tres`: `stock` = [{item_id, price}] where
  a price below 0 means the item's `value`, and `sell_ratio`, default 0.5) with all-or-nothing
  `buy` / `sell` that return `""` or why they were refused (not enough gold, no room in the bag,
  not held, worthless; key and quest items are never bought). The dialogue event `open_shop:<id>`
  sends `Events.shop_requested`; `RpgUiController` opens `RpgShopMenu` (a new generated scene
  `shop_menu.tscn`) when the dialogue closes, with the game paused. The menu has Buy and Sell tabs,
  one button per item, the gold you have and the item's description, and one focus ring for the
  gamepad. `RpgInventory.room_for(item_id)`. New keys: `UI_SHOP`, `UI_BUY`, `UI_SELL`,
  `UI_GOLD_SHORT`, `UI_BOUGHT`, `UI_SOLD`, `UI_NOT_ENOUGH_GOLD`, `UI_NO_ROOM`, `UI_CANNOT_TRADE`,
  `UI_NOTHING_FOR_SALE` and `UI_NOTHING_TO_SELL`. New projects get a `village_shop` and a villager
  who offers it after the first talk.
* An item's `max_hp` modifier raises the cap everywhere (`RpgUtil.max_hp(stats)`: the status menu,
  both HUDs, healing items and heals, full refills, the level-up refill); wearing it does not heal,
  and taking it off pulls the current hp down to the smaller cap (never to 0). A `move_speed`
  modifier scales the player's walk (`RpgMovement.walk_speed()`; it is a factor on the base
  `move_speed`, so the dodge is scaled too). New event `equipment_changed(actor_id, slot)`, which
  the action-RPG HUD listens to; it was emitted before the signal existed, so nobody saw it.

## 0.3.0

* Action-RPG archetype (`archetypes/arpg/`): hitboxes that are live only on attack frames, hurtboxes
  with invulnerability windows, health, knockback and crits; the player's combat state machine
  (idle, move, attack with an input buffer, hurt, dodge, dead); enemies with a component-based AI
  (detection with line of sight, chase, wander, telegraphed attacks, loot pickups); the HUD; the
  generic swing effect for characters without attack animations; optional tile-based navigation.
* Shared code: `RpgActor` gained `move_locked`, `facing_locked` and `animation_locked` (set by an
  archetype's combat code), `RpgAnimationDriver` gained `has_animation` / `play_exact`, the
  inventory menu has an extension point for archetype buttons, and boot takes the archetype's HUD.
## 0.2.0

* Turn-based archetype (`archetypes/turn_based/`): battle commands (attack, defend, item, skill
  placeholder, run), the battle controller and turn manager, the battle scene and interface,
  overworld enemies that start encounters, and the combat mode that returns the result to the map.
* A defeated enemy stays defeated across saves; escaping gives a short grace period; losing sends
  the player back to the newest save, or to the map's default spawn with full health.

## 0.1.0

* First release of the shared RPG runtime: events bus, game state, scene routing, saving,
  stats, items, inventory, dialogue, interaction, settings, audio, UI and translation-ready text.
