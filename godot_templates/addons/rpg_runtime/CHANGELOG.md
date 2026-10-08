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
