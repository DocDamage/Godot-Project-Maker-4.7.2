# Changelog

All notable changes to the rpggen application. The generated game's runtime has its own
changelog in `godot_templates/addons/rpg_runtime/CHANGELOG.md`.

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
* Tooltips and accessible names on every control, `Alt+N` / `Alt+B`, a tab order, and status
  colours that keep a 3:1 contrast on both themes.

### The generated game

* Music and sound effects wired to the slots; autosave (slot 0); a game-over screen with
  continue, try again and quit; the action-RPG heavy attack with screen shake and hit-stop; a
  second outdoor map behind the east wall; chests that show their open picture; a key prompt over
  what you can interact with.

### Under the hood

* The targeted Godot version lives in one file (`rpggen/godot_target.py`); `tools/bump_godot.py`
  moves the app, the workflows and the texts to a new release.
* A deterministic starter-map planner shared by the preview (Python) and the builder (GDScript),
  checked against one fixture.
* Diagnostic bundles, export presets for Windows, Web, Linux and macOS with a test export per
  target, the community profile registry client,
  and packaging (PyInstaller, Inno Setup, a release workflow).
