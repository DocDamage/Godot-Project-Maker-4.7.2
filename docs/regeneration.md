# Regenerating a project safely

You can run rpggen again on a project it generated: after you changed the project in Godot, after
you updated an asset pack, or after you changed options in the wizard. Regeneration never throws
your work away. Three rules hold every time, and each one has its own automated test
(`tests/integration/test_regeneration.py`).

## The three invariants

1. **Tile invariant.** For every `TileMapLayer` in every map under `game/`, the cells
   `(cell, source_id, atlas_coords, alternative)` are the same before and after regeneration. Tile
   set sources keep their ids, tiles are never removed, and ids are never reused.
2. **Ownership invariant.** Nothing under `game/` is changed, and no file you modified or created
   is changed. A generated file you edited is left as it is; the new version is written next to it
   as `<name>.rpggen-new`.
3. **Atomicity invariant.** If generation fails at any point, the project folder is byte-identical
   to what it was before. Everything is built in `.rpggen_staging/` first and only a validated
   result is copied in.

## A regeneration with nothing changed

Since 1.3.0 a regeneration first asks whether anything it is made from changed since the last
run that succeeded: the packs (every file's content), the audit, the mapping, the options, the
seed, rpggen itself (its version, the runtime and the build recipes) and the Godot that builds.
When nothing did, and no file of the project was changed or deleted since then, a generated
one or one of your own, the run is
**a repeat**: the import, the build, the validation, the smoke test and the export check are
not run again, nothing is written and the project is left exactly as it is. The Generate page
shows those phases with a dash and *skipped: nothing changed since the last run*, the command
line's `--json` lists them under `skipped` with the note `REGEN-011`, and `--dry-run` says
*A regeneration would skip the checks: nothing changed.*

A run is **not** a repeat, and does everything, when

* anything in the list above changed, or the project was made by a version before 1.3.0 (its
  ledger does not say what it was made from; the first regeneration with 1.3 records it);
* a generated file was edited or deleted (the run has a conflict to find or a deletion to
  respect);
* a file of your own changed since the last run: anything under `game/`, or `project.godot`.
  rpggen never rewrites those, but the validator and the smoke test are what a run has to say
  about a map you painted or a door you removed, and the world repair acts on what they find.
  What your files were at the last run is noted in rpggen's data folder, not in the project,
  so the first regeneration on another computer is a full one;
* the world repair was switched off for the last run and is on for this one, or the other way
  round;
* the last run into the folder failed or was cancelled;
* you ask for it: `rpggen generate ... --full` for one run, or **Run every check again on
  every regeneration** in the regeneration preview for a project (the choice is kept in the
  project's `rpggen/ownership_ledger.json` as `run_every_check`).

`--full` is for when you want every check again although nothing changed, for example after
an update of the export templates.

## Before you regenerate

**Close the Godot editor.** An open editor can save its own copy of a scene over the regenerated
one. rpggen looks for a Godot process that has the project open and stops with a warning. In the
wizard you can close the editor and press Retry; on the command line add `--force-while-open` to
go on anyway.

## What belongs to whom

rpggen keeps a ledger, `rpggen/ownership_ledger.json`, with the hash of every file it wrote.

| Where | Owner | On regeneration |
|-------|-------|-----------------|
| `game/` | you (created once, `user_seed`) | never rewritten, never deleted. If you delete a seed file it is not recreated. |
| `generated/`, `addons/rpg_runtime/`, `rpggen/`, `assets/packs/` | rpggen | rewritten when unchanged since the last run; a file you modified is kept and the new version goes to `.rpggen-new`. |
| `project.godot` | shared | never a conflict: only the settings rpggen owns are applied on top of your file. |
| `rpggen/asset_catalog.json`, `rpggen/generator_config.json` | shared | rebuilt from the previous file, so your overrides survive. |
| Anything else you added | you | never touched. |

Text files are hashed with line endings normalized, so git rewriting `CRLF` does not look like an
edit.

A file you deleted on purpose is listed in `deleted_by_user` and is not brought back
(message REGEN-002).

## Pack updates

On the first page choose **Update pack…** for a project that already exists, and pick the new
release of one of its packs. The dialog counts added, removed, renamed, changed and resized files.

* Files are matched by path. A file that moved but has the same content is a rename: its asset
  keeps its overrides and its tile set source id (`renamed_from` is recorded in the catalog).
* A sheet that changed size becomes `CONFLICT`. Its tile set source is left completely untouched
  (TILE-004) so painted tiles cannot shift. Review it in the audit.
* A sheet that disappeared keeps its tile set source and its image file (REGEN-003) until you
  confirm the removal in the audit, which sets `remove_source`.
* New sheets get the next free source id.
* Collision you edited in the Godot editor is kept (TILE-007); collision is only replaced where
  the catalog's collision changed and you did not touch that tile.

The audit opens on the **Changed in update** filter (added, resized and missing assets).

## Backups and restore

Before anything in the project is overwritten or deleted, the old files and the old ledger are
copied to `.rpggen_backups/<date-time>/`. The three newest backups are kept. A run that changes
nothing makes no backup.

To go back to the version before the last regeneration use **Restore previous** on the results
page, or:

```
rpggen restore --target <project> [--backup <name>]
```

The default is the newest backup. What a restore replaces is saved first, so a restore can be
undone too. Files the undone generation created are removed if you did not touch them.

## Resolving conflicts

When you changed a generated file and a regeneration produces a different version of it, your
file stays and the new version is written beside it as `<file>.rpggen-new` (`REGEN-001`).
**Resolve conflicts…** on the results page (also *File > Resolve conflicts…*, and the button on a
`REGEN-001` row) lists those files and shows, side by side:

* **Last generated** — the version rpggen wrote before you changed it. It is found in the
  backups (newest first) or, for a project under git, in its history; when neither has it the
  pane is hidden and only two versions are shown.
* **Yours** and **New**, with the lines that differ highlighted.

For each file choose:

| Action | What it does |
|--------|--------------|
| **Keep mine** | Deletes the `.rpggen-new` file and remembers that you declined that version (the ledger entry's `declined_sha256`). Regenerating does not raise the conflict again while rpggen still makes exactly that content; a different version is offered again. |
| **Take new** | Replaces your file with the new version. Later regenerations update the file as usual. |
| **Merge** | Text files only. A line-based three-way merge: what only one side changed is taken, and where both changed the same lines (or neighbouring lines) the file gets markers to edit by hand: `<<<<<<< yours`, `\|\|\|\|\|\|\| last generated`, `=======`, `>>>>>>> rpggen`. Without the last generated version every difference is marked. The new version then counts as what rpggen last wrote, and it is not offered again. Open a merged `.tscn` or `.tres` in Godot to check that it still loads. |

Every action first copies the file, its `.rpggen-new` and the ledger to a new backup folder, so
**Restore previous** undoes it (restoring brings the conflict back). These backups count towards
the three that are kept, at the next regeneration.

From a terminal:

```
rpggen conflicts --target <project>                         # list
rpggen conflicts --target <project> --keep-mine <file>      # or --take-new, --merge
```

`<file>` is the project path with forward slashes (a trailing `.rpggen-new` is accepted). With
`--json` the list or the result is a JSON document; `REGEN-009` means the file has no
`.rpggen-new`, `REGEN-010` that a binary file cannot be merged.

## The world of areas and its repair

A project made with *Make a world of several areas* keeps its world plan in
`rpggen/world_plan.json`. The plan is **stored and reused**: once the map of an area exists, a new
seed or a changed row of the Areas table changes nothing; a new row adds an area, joined to the
one you pick. To have an area built again, delete its `game/maps/<area>.tscn`.

The validator warns when a map cannot be reached from the starter map through doors (`VAL-027`)
and when a door of the world leads to a map or a spawn point that does not exist (`VAL-028`). Both
are warnings: you may want an island. **rpggen mends the maps it made; yours it mends when you
ask.** After a generation it adds the missing spawn point or door to the area maps that are still
exactly as it built them (it knows them by the hash it recorded), after saving them to
`.rpggen_backups`, so **Restore previous** takes a repair back; the report lists every change
under *World repairs*, and `rpggen/world_repair.json` has the same list. A map you changed is
never touched by itself: its warning has **Repair the world…** on the Results page, which shows
what it would do before it writes (`rpggen-cli repair-world --target <project> [--dry-run]` does
the same from a script), and the dock's *Validate* tab has **Fix** and **Fix all**, which you can
undo with Ctrl+Z. A repair only adds: it never moves or deletes what you placed, never changes a
door that has its partner, and does nothing while the Godot editor has the project open. Turn the
automatic part off with *Options → Advanced → Repair generated maps after a build*, or
`--no-repair-world` for one run.

## Rooms and the stored plan

A metroidvania keeps the plan of its rooms in the same file, `rpggen/world_plan.json` (the
`rooms` section: which room lies where, its exits, its tiles and what stands in it). The rule is
the one of the areas: **the plan is stored and reused.** Once one room of the plan exists,

* a new seed, another number of rooms, another room size or other abilities change nothing: the
  *Starter world* box says so and shows the stored world;
* a room that exists is never built again, whatever you painted or placed in it;
* a row under **Added rooms** adds one room beside the room it names (or beside the nearest room
  with a free side). The new room is built with its exit; the exit on the other side is added to
  the neighbour by the repair below, because the neighbour is not rebuilt;
* to have a room built again from the plan, delete its `game/maps/rooms/<room>.tscn`.

The validator treats an exit like a door: a room no exit leads to is `VAL-027`, and an exit whose
target room or arrival point does not exist is `VAL-028`, both warnings. The repair is the same
as for areas, with the same promise. After a generation rpggen adds the missing exit and its
spawn point to the rooms that are still exactly as it built them (by the recorded hash), after
a backup, and lists the change in the report; a room you changed is not touched by itself, and
**Repair the world…** on the Results page, `rpggen-cli repair-world` and the dock's **Fix** do
it when you ask. A repair only adds an exit on a wall that has floor beside it; it never moves
or removes anything.

Saved games of a metroidvania have three more keys (`abilities`, `broken_cells`, `room_fog`),
written only when they hold something, so a save made by a top-down project is unchanged.

## Git

New projects get a `.gitignore` (the `.godot/` cache, logs and results, `.rpggen_*` working
folders) and a `.gitattributes` (LF text, binary assets, optional Git LFS lines). The options page
has **Initialize git repository**; on a regeneration it is **Commit regeneration** (off by
default). rpggen never pushes. If git has no identity configured, the commit uses
`rpggen <rpggen@localhost>`.

A regeneration that changes nothing leaves `git status` empty.

**What a commit contains.**

* A repository that rpggen creates (a new project) gets everything the first generation wrote.
* In a repository that **already exists** (yours, or the one rpggen made earlier) rpggen stages and
  commits **exactly the files it wrote or deleted**: the promoted files, the `.rpggen-new`
  conflict copies, the ownership ledger and the two reports. Your own staged or unstaged changes,
  and files you have not added, stay where they are and are not part of the commit. If there were
  any, the result says so (`REGEN-008`, information).
* If the commit fails (a pre-commit hook, a lock, a missing identity) the project is still
  generated and the result shows `REGEN-007` with the reason; commit by hand when it is fixed.

**Purchased art.** By default the pack art in `assets/packs/` is committed, which is the safest
copy for yourself and the riskiest for a public repository: most pack licences do not allow
redistribution. Under **Options > Version control** you can instead *leave the pack art out of
git* (`assets/packs/` is added to the generated `.gitignore`; art that is already tracked stays
tracked until you remove it with `git rm --cached`) or *use Git LFS* (the pack's image and audio
files are routed through LFS in `.gitattributes`; without git-lfs installed rpggen commits the art
as it is and warns with `ENV-013`). The choice is the optional `git.pack_art` key of
`generator_config.json`, and the generated README explains it.

## Troubleshooting

* *REGEN-001* — you changed a generated file. Use **Resolve conflicts…** (see
  [Resolving conflicts](#resolving-conflicts)), or compare it with the `.rpggen-new` file next to
  it yourself, merge what you want and delete the `.rpggen-new` file.
* *REGEN-004* — a file could not be written (often antivirus or the Godot editor holding it). The
  project was restored from the backup; close the other program and run again.
* *REGEN-005* — the Godot editor seems to be open.
