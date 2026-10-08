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

* *REGEN-001* — you changed a generated file. Compare it with the `.rpggen-new` file next to it,
  merge what you want and delete the `.rpggen-new` file.
* *REGEN-004* — a file could not be written (often antivirus or the Godot editor holding it). The
  project was restored from the backup; close the other program and run again.
* *REGEN-005* — the Godot editor seems to be open.
