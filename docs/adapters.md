# Adapters

An **adapter** teaches rpggen about one pack format (Tiled maps, Aseprite exports, RPG Maker
sheets, ...). It reads the pack's inventory and returns *fragments*: partial descriptions of
assets (usage, grid, animations, collision, objects). The catalog builder merges fragments, the
classifier fills the rest, and the audit lets the user correct anything.

You usually do **not** need an adapter. If one pack is misdetected, fix it in the audit and export
a [profile](profiles.md) instead (no Python needed). Write an adapter when a whole *format* is
unsupported.

## Built-in adapters

| Name | Priority | Reads |
|------|----------|-------|
| `profile` | 0 | an installed [profile](profiles.md) whose fingerprint matches |
| `tiled` | 10 | `.tsx`/`.tsj` tile sets and `.tmx`/`.tmj` maps: collision, custom data, wang terrains, animated tiles |
| `aseprite` | 20 | Aseprite JSON (hash and array formats), frame tags, durations |
| `ldtk` | 30 | LDtk tile set definitions |
| `rpgmaker` | 40 | RPG Maker MV/MZ tilesets (A1-A5, B-E), character sheets, faces |
| `lpc` | 50 | Liberated Pixel Cup / Universal LPC character sheets |
| `strips` | 60 | horizontal animation strips (incl. GIF) |
| `generic_grid` | 100 | everything else: grid detection, strips, character sheets, small sprites |

Lower priority runs first. A fragment with `claim="full"` makes later adapters skip that file.

## The interface

`rpggen/core/adapters/base.py`:

```python
class Adapter(Protocol):
    name: str
    priority: int  # lower runs first

    def match(self, inv: Inventory, root: Path) -> float: ...  # 0..1; run when >= 0.5
    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult: ...
```

* `inv` lists every file with `kind`, hashes and (for images) `w`/`h`. `root` is the folder with
  the pack's files. **Never write into `root`.**
* `AdapterResult.assets` holds `AssetFragment(path, facets, confidence, claim)`. `facets` is a
  partial *Facets* object (`02_SCHEMAS.md` §4.4): `usage`, `grid`, `animations`, `collision`, ...
  Use `claim="full"` only when the classifier must not change usage, grid or animations.
* Also available: `objects` (sheet objects), `tilesets` (tile set definitions), `pack_warnings`,
  `issues`, `consumed` (files merged into another asset), `generated` (files you wrote to the work
  dir, e.g. GIF strips).
* `ctx.analyze(path)` returns the cached image analysis; `ctx.claimed` is what earlier adapters
  claimed; `ctx.results` are the earlier results.
* An exception inside an adapter is caught and reported as `ADAPT-001`; the others still run.

## Adding one, step by step

1. Create `rpggen/core/adapters/<name>.py` with a class implementing the interface. Keep
   `match` cheap (look at file names and extensions) and deterministic. Put tuning numbers in a
   module-level constants dict, as `generic_grid.py` does.
2. Register it in `register_defaults()` in `rpggen/core/adapters/__init__.py` with a priority that
   fits the table above.
3. Add a **synthetic pack** to `tools/make_synthetic_packs.py` (pure Pillow drawing, no real
   art, deterministic, with an `expected.json` listing the tile sizes, roles and animation
   sets). Run `python tools/make_synthetic_packs.py --out test_packs/synthetic` and commit the
   output.
4. Write unit tests in `tests/unit/test_adapter_<name>.py`: `match` on your pack and on others,
   the fragments for each file, and the edge cases (broken files must not raise).
5. Update the golden catalogs with `python -m rpggen.dev update-goldens` and check the diff.
6. Run `python -m rpggen analyze --corpus test_packs/synthetic`; the accuracy thresholds (grid
   0.95, usage 0.95, role 0.85, animations 0.90) must still pass.
7. If you need a new message, follow the error-code process in
   [CONTRIBUTING.md](../CONTRIBUTING.md#error-codes).
8. Add the format to the table above and a line to `docs/dev/implementation_notes.md`.
