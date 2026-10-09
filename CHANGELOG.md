# Changelog

All notable changes to the rpggen application. The generated game's runtime has its own
changelog in `godot_templates/addons/rpg_runtime/CHANGELOG.md`.

## 1.1.0 (in progress, on the branch `m13`)

* Tiled map layers saved with **Zstandard** compression are imported (TILE-009 is now only for a
  compression rpggen does not know).

* The validator and the Dialogue tab check the **shop, quest and party member ids** a dialogue
  names (`open_shop:`, `quest_start:`, `quest_stage:`, `quest_complete:`, `join_party:`); a typo
  is marked on its line while you type.

* **Shops**: left / right on a row sets how many to buy or sell (the row shows the total), and
  the Sell tab has **Sell all**. A shop can list the item categories it buys.

* **Audit review mode** (View → Review mode, `F7`, or the button beside the progress line): one
  asset at a time with a large preview and the same panel and keys; `Esc` returns to the grid.

* **Audit: Group by folder** (on the filter bar, remembered): a header per folder with its counts
  and **Confirm all**, **Select all** and **Make rule…**; click a header to fold its folder.

* **Audit: live preview**: the picture shows an object's footprint and origin and the frames
  where an attack hits; a sprite with animations has a small transport (animation, Play, frame)
  that plays it in the preview, in the panel or large in review mode.

## 1.0.0

The first release. It turns a 2D RPG asset pack into a Godot 4.7.2 project (tile sets with
collision and terrain, animated characters, a starter map with a house and a second area, dialogue,
inventory, saving, menus, and a turn-based or action-RPG combat system), checks the result by
loading and playing it headless, and regenerates it later without touching your work.

### The wizard

* A **welcome view**: try the sample, start with your own pack, or open an existing project;
  recent projects; the Godot that was found, or a **Download Godot** button that fetches the
  official 4.7.2 after you confirm the source, size and destination and verifies its checksum.
* A menu bar (File, Edit, View, Help): recent projects, undo and redo, a dark and a light theme,
  the thumbnail size, the user guide at the page you are on (F1), an error-code lookup, the
  keyboard shortcuts, *Report a problem…*, *Check for updates…* (only when you click) and *About*.
* **Project page**: the output folder is checked as you type, with a plain explanation of what
  is wrong; Next stays enabled and shows the missing fields instead of leaving you stuck.
* **Archetype page**: two large cards with a drawn preview of each game, what is generated and
  the controls.
* **Audit page**: a queue of the assets that need attention (`N` / `Shift+N`), a corner glyph on
  every thumbnail so status is not colour-only, bulk actions, folder rules, the grid editor,
  the animation editor, the object cutter, terrain proposals, and profiles.
* **Mapping page**: roles and, new, **sound slots** (map, battle and title music; menu, hit,
  attack, pick-up, chest, door, footstep, save and level-up sounds) filled from the audio of your
  packs by file name, with a preview and the length of every file.
* **Options page**: presets, and the starter map's size, counts and seed with a **live preview**
  of the real plan drawn from your assets.
* **Generate and Results pages**: each phase with its time and an estimate of the time left,
  cancel, a desktop notification when the window is in the background, and a results page that
  leads with a picture of the generated starter map and a *What next* list.
* **Resolve conflicts**: generated files you changed and rpggen remade (`.rpggen-new`) side by
  side with the version rpggen last wrote; keep yours, take the new one or merge them line by
  line, each backed up first (also `rpggen conflicts`).
* **Project page** pack cards (licence, size, what was found); **Archetype cards** drawn with
  your pack's own art; a **sidebar** with each step's status and jumps forward to any step that
  is ready; the Mapping page's candidates inline; an Options **summary panel**; the map preview's
  legend.
* **Audit**: the detail panel opens as wide as its form needs (it no longer scrolls sideways at
  the default window size), audio and font cards with playback, role badges, a filter bar that fits, a **change
  history**, frame sequences (one numbered image per frame) read as animations, eight-direction
  characters, **learned rules** (rpggen remembers your fixes and proposes them for the next pack;
  *Edit → Learned rules…*), and a printable **contact sheet** (PDF or PNG).
* **Options**: **imported Tiled and LDtk maps** (any of them can be the starter map), **export
  targets** (Windows, Web, Linux, macOS), and what git does with the purchased **pack art**
  (commit, leave out, Git LFS).
* **Before a regeneration** the changes are listed for you to confirm; **Results** has *Play*,
  *Open starter map*, warnings grouped with **one-click fixes**, and the checks that were
  skipped, with the reason.
* The wizard **follows the system theme**, fits laptop screens, and can be shown in **French**
  (*View → Language*; more languages can be added).
* **Storage** (*Edit → Storage…*): settings, your data and a size-limited cache in the system's
  usual folders.
* Tooltips and accessible names on every control, `Alt+N` / `Alt+B`, a tab order, and status
  colours that keep a 3:1 contrast on both themes.

### The generated game

* **Equipment** (weapon, armor, accessory, with a preview of the stat change), **shops**, a
  **quest journal**, **party members** who fight together and walk behind you (turn-based), and a
  **credits** screen built from the packs' licences.
* **Random-encounter zones** and deeper turn-based battles: **skills, MP, elements, statuses**,
  hit and evade, and enemy tactics.
* Action RPG: **bows and projectiles**, and **shooter, turret and charger** enemies.
* **Cutscenes** (an event sequencer started from trigger areas or dialogue), **keys, switches and
  gates**, locked doors.
* **Lighting** (ambient day and interior light, torches and lamps, an optional day/night cycle),
  a **minimap** and a **world map** with fog of war.
* **Save and load screens**, safe save rotation, key prompts that follow the device (keyboard,
  Xbox, PlayStation, Nintendo), and an in-game **language** setting.
* In the Godot editor: a **Dialogue** tab to write and test conversations, and **your own build
  steps** (`game/builder_recipes/`), which rpggen runs on every build.
* Music and sound effects wired to the slots; autosave (slot 0); a game-over screen with
  continue, try again and quit; the action-RPG heavy attack with screen shake and hit-stop; a
  second outdoor map behind the east wall; chests that show their open picture; a key prompt over
  what you can interact with.

### Under the hood

* A **scriptable CLI**: `--json`, documented exit codes, `--dry-run`, `--confirm`, `--tile-size`,
  and `conflicts`; unknown arguments are an error.
* Faster and safer analysis: each pack is hashed once, images are analysed in parallel with real
  progress and a Cancel that cancels, folder inventories are cached, archives are extracted with
  one size budget and no links; the base tile size is read from the packs.
* Generation shows Godot's live output and build progress; a failed run keeps a lean folder;
  logs live in one place, rotated, with run ids; unexpected errors get a report.
* A Godot download with a pinned checksum, resume and retry; git commits only the files rpggen
  wrote; the editor-open check matches exact project paths.
* The template project's GDScript is strict (typed), and a test that logs a script error fails.

* The targeted Godot version lives in one file (`rpggen/godot_target.py`); `tools/bump_godot.py`
  moves the app, the workflows and the texts to a new release.
* A deterministic starter-map planner shared by the preview (Python) and the builder (GDScript),
  checked against one fixture.
* Diagnostic bundles, export presets for Windows, Web, Linux and macOS with a test export per
  target, the community profile registry client,
  and packaging for Windows (installer and portable zip), Linux (AppImage and tar.gz) and macOS
  (an unsigned `.app`), each smoke-tested frozen, with one `SHA256SUMS.txt`.
