# M2 — Asset Intelligence

**Goal:** turn any reasonable pack (zip, 7z or folder) into a full catalog automatically. Adapters handle the packs that describe themselves, and heuristics handle the rest. A measured accuracy metric guards against regressions. At the end of M2, `build_minimal_catalog` is deleted.

**Module boundaries:**

```text
archive.py   → produces a pack_dir on disk (read-only from here on)
inventory.py → Inventory (files, hashes, image facts)
cache.py     → analysis cache by sha256
analyzer/*   → ImageAnalysis per image (pure functions, numpy)
adapters/*   → AdapterResult (catalog fragments) per pack
classifier.py→ roles/usage for assets no adapter fully described
catalog.py   → assemble(): merges everything into a Catalog
```

Every analyzer function is **pure**: it takes an array and returns a dataclass, and never touches disk or global state. This makes the unit tests trivial.

---

## T2.01 — Extend the synthetic pack generator

**Depends on:** T1.04
**Files:** `tools/make_synthetic_packs.py`, `test_packs/synthetic/**`, `test_packs/synthetic/*.expected.json`

Add these packs. Each one has an `expected.json` giving the facts the pipeline must find. Use the same deterministic drawing rules as T1.04.

| Pack | Content | Tests what |
|------|---------|------------|
| `gutter32` | `tiles/world.png`: 32px tiles, 1px transparent separation, 1px margin, 6×5 grid | gutter detection, margin/separation |
| `gutterless48` | `Tilesets/ground.png`: 48px tiles, seamless textures (gradients that continue across tiles inside 2×2 groups) plus clear borders between groups | smallest-divisor trap (24 must lose to 48) |
| `mixed` | 16px tiles + 32px tiles + a 512×288 opaque background + 12 item icons (16×16 individual files) | multiple tilesets, background, items |
| `strips` | `hero_walk_down.png` … `hero_walk_right.png` (4 frames 16×16 each) + `hero_attack_down.png` (3 frames) + `slime_idle.png` (strip of 4) | per-file strips, partial animation sets |
| `rpgmaker_like` | `img/tilesets/Outside_A2.png` (768×576), `Outside_B.png` (768×768 48px), `img/characters/Actor1.png` (576×384 = 8 chars × 3×4 frames of 48×48), `img/characters/$Big.png` (single 3×4), `img/faces/Actor1.png` (576×288 = 8 faces 144×144) | RPG Maker adapter |
| `lpc_like` | `characters/body.png` 832×1344 (13 cols × 21 rows of 64×64), drawing filled frames only in the standard LPC used cells | LPC adapter |
| `tiled_meta` | `tiles.png` 16px with 1px spacing + `tiles.tsx` (Tiled XML) with spacing="1", margin="0", collision objects on 3 tiles, a Wang set "ground" with 2 colors, a tile property `footstep=grass` | Tiled adapter |
| `aseprite_meta` | `knight.png` packed (non-grid, frames of different sizes) + `knight.json` (Aseprite "hash" format) with frameTags `idle_down`, `walk_down`, `walk_side` | Aseprite adapter |
| `objects_in_sheet` | `town.png` 16px: a 5×4-tile house, a 2×3 tree, scattered single tiles | region detection |
| `weird_names` | `Árbol Grande.png`, `tree.png` + `Tree.PNG` (case collision), nested `extra.zip` containing `sign.png`, a `__MACOSX/` folder, a `.DS_Store` | archive safety, Unicode |
| `zipped` | `basic16` zipped (zip version of T1.04's pack) | zip input |

Expected-file format example (extend as needed; this is what T2.16 scores against):

```json
{
  "tiles/world.png": { "usage": "tiles", "role": "GROUND", "cell": [32,32], "margin": [1,1], "separation": [1,1] },
  "hero_walk_down.png": { "usage": "sprite", "role": "PLAYER", "anims": ["walk_down"] }
}
```

The Tiled `.tsx` and Aseprite `.json` files are written as text by the script. **Write them exactly as the respective tools would export them.** Use the format references in T2.09 and T2.10.

**Done when:** every pack is regenerated deterministically (the CI diff check passes) and the expected files are committed.

---

## T2.02 — Safe archive extraction and inventory

**Depends on:** T1.03
**Files:** `rpggen/core/archive.py`, `rpggen/core/inventory.py`, `tests/unit/test_archive.py`, `tests/unit/test_inventory.py`

### archive.py

```python
LIMITS = dict(max_files=200_000, max_total_bytes=4 * 1024**3, max_entry_bytes=1024**3,
              max_ratio=200, ratio_min_bytes=10 * 1024**2)
JUNK = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}   # any path part equal to these

@dataclass(frozen=True)
class OpenedPack:
    pack_id: str
    kind: Literal["zip", "7z", "rar", "folder"]
    root: Path              # directory to read files from (extracted cache dir or the folder)
    source_sha256: str      # sha256 of the archive file; for folders: sha256 of sorted "path:sha256" lines
    issues: list[Issue]

def open_pack(source: Path, existing_ids: set[str]) -> OpenedPack
```

Rules:
1. **Folder:** `root = source`. Never write into it. Compute `source_sha256` from the inventory hashes after inventory runs (two-step; that's fine).
2. **zip:** hash the file. The extraction target is `local_cache_dir()/extracted/<sha256>/`. If that directory exists and contains `.complete`, reuse it. Otherwise extract into `<target>.partial/`, then rename it and write `.complete`.
3. For each entry:
   * Decode the name. If flag bit 11 is set, the name is already UTF-8. Otherwise Python has decoded it as cp437; try `name.encode("cp437").decode("utf-8")` and use the result if it succeeds, otherwise keep the cp437 text.
   * Normalize the name with `unicodedata.normalize("NFC", ...)` and replace `\` with `/`.
   * Reject the whole archive with ARCH-003 if the name is absolute (starts with `/`, or has a drive letter such as `C:`) or any part is `..`.
   * Skip directories, and skip junk entries with ARCH-008.
   * Enforce LIMITS using the declared sizes before extracting, and the actual bytes while streaming. Breaches → ARCH-004.
   * Case collision: keep a dict of `casefold(path) → path`. On a collision, keep the entry whose path sorts first (01_CONVENTIONS §5), skip the other, and emit ARCH-005.
   * Write with `shutil.copyfileobj` from `zf.open(info)` into the target path. Create parents as needed.
4. **Encrypted entries** (`info.flag_bits & 0x1`) → ARCH-002.
5. **Nested archives:** after extraction, every `.zip` or `.7z` file at any depth is extracted one level into a sibling folder named `<name>_extracted/` (ARCH-006), then removed from the extracted cache copy. Do not recurse further.
6. **7z:** `py7zr.SevenZipFile(...)`. Get the names list and sizes with `list()`, check them against the rules above, then use `extract(path=partial, targets=allowed_names)`.
7. **rar:** look for `7z.exe` in `C:\Program Files\7-Zip\` and on `PATH`. If found, list entries with `7z l -slt` and check them against the rules, then run `7z x -o<partial> -y`. If 7z is not found → ARCH-007 error.
8. `pack_id` = `ids.pack_id_from_name(source.stem or folder name, existing_ids)`.

### inventory.py

```python
EXT_KIND = {".png":"image",".jpg":"image",".jpeg":"image",".webp":"image",".bmp":"image",".gif":"image",
            ".wav":"audio",".ogg":"audio",".mp3":"audio",
            ".ttf":"font",".otf":"font",".fnt":"font",
            ".txt":"doc",".md":"doc",".pdf":"doc",".html":"doc",
            ".tsx":"metadata",".tmx":"metadata",".tsj":"metadata",".tmj":"metadata",".json":"metadata",
            ".ldtk":"metadata",".aseprite":"metadata",".ase":"metadata",".xml":"metadata"}

def build_inventory(pack: OpenedPack) -> Inventory
```

* Walk `pack.root` recursively and sort the results. Skip junk.
* For each file: compute sha256 in 1 MB chunks, then size, extension (lowercased), kind (`02_SCHEMAS.md` §2 rules; license names override the extension).
* For images, open with Pillow (`Image.open`, without calling `load()`), read `size`, `mode` and frame count (`getattr(img, "n_frames", 1)`). Set `has_alpha` true if the mode is one of `RGBA`, `LA` or `PA`, or if the mode is `P` with `"transparency"` in `img.info`. Decode errors → ASSET-002 (warning); the file keeps kind `image` with no `image` block.
* Hash and image work runs in a `concurrent.futures.ProcessPoolExecutor(max_workers=min(8, os.cpu_count()))`. Results are re-sorted afterwards.
* Save the inventory to the cache (`02_SCHEMAS.md` §2), keyed by `source_sha256`. If a cached inventory exists, reuse it.

**Tests (use `weird_names`, `zipped` and handcrafted zips built inside the tests):**
* Zip-slip entries (`../evil.png`, `/abs.png`, `C:/x.png`) → ARCH-003, and nothing is written outside the cache.
* A zip bomb (a 50 MB entry of zeros compressed into about 50 KB) → ARCH-004.
* Case collision → one file kept, ARCH-005.
* Nested zip → `extra_extracted/sign.png` present, ARCH-006.
* `__MACOSX` skipped.
* Unicode name preserved in NFC.
* The same zip opened twice → the second open reuses the cache (patch zipfile to raise if called).
* Inventory sorting and kinds are correct for every file in `mixed`.

**Done when:** all tests pass and both `zipped` and `basic16` give identical inventories (same relative paths and hashes).

---

## T2.03 — Analysis cache

**Depends on:** T2.02
**Files:** `rpggen/core/cache.py`, `tests/unit/test_cache.py`

* `get(sha256: str, version: int) -> dict | None` and `put(sha256, version, data)`.
* The layout follows `02_SCHEMAS.md` §3. Writes use `jsonio.write`.
* A version mismatch counts as a miss.
* `clear()` is used by the CLI flag `--no-cache`.
* Corrupt JSON counts as a miss, and the corrupt file is deleted.

---

## T2.04 — Image facts

**Depends on:** T2.03
**Files:** `rpggen/core/analyzer/image_facts.py`, `tests/unit/test_image_facts.py`

```python
def load_rgba(path: Path) -> np.ndarray:
    """Pillow open → convert("RGBA") → np.asarray(dtype=uint8), shape (h, w, 4).
    GIF: first frame only here (animated GIFs are handled by the strips adapter)."""

def occupancy(a: np.ndarray) -> np.ndarray:
    """bool (h, w). If any alpha < 255: alpha > 0.
    Else (fully opaque image): background = most common color among the 4 corner pixels
    (ties → top-left); occupied = any channel differs from background by > 8."""

def opaque_bbox(mask) -> tuple[int,int,int,int] | None   # x, y, w, h of True pixels
def dominant_colors(a, k=3) -> list[str]                 # quantize to 5 bits/channel, top-k by count, among occupied pixels
def is_fully_opaque(a) -> bool
```

**Tests:** synthetic arrays built in the test (no files needed): a transparent image with one opaque pixel → bbox of 1×1; an opaque image with a uniform border → occupancy excludes the border.

---

## T2.05 — Grid detection

**Depends on:** T2.04
**Files:** `rpggen/core/analyzer/grid.py`, `tests/unit/test_grid.py`

### Output

```python
@dataclass(frozen=True)
class GridCandidate:
    cell: tuple[int, int]
    margin: tuple[int, int]
    separation: tuple[int, int]
    score: float               # 0..1
    nonempty_cells: int
    total_cells: int

def detect_grid(a: np.ndarray, mask: np.ndarray, *, square: bool = True,
                pack_prior: dict[int, float] | None = None) -> list[GridCandidate]
    """Returns up to 5 candidates sorted by score desc (ties: larger cell first)."""
```

### Algorithm (implement exactly; the constants live in `GRID_CONSTANTS` at the top of the module)

```text
SIZES = [8, 12, 16, 24, 32, 48, 64, 96, 128]
MARGINS = [0, 1, 2]       SEPARATIONS = [0, 1, 2]

for each axis independently (x uses columns, y uses rows):
  L = length of axis
  empty_line[i] = not mask.any() along line i
  for c in SIZES, m in MARGINS, s in SEPARATIONS:
      if c > L: continue
      n = (L - 2*m + s) // (c + s)           # number of cells
      if n < 1: continue
      remainder = (L - 2*m + s) - n*(c + s)
      if remainder > c // 4: continue          # too much left over → reject
      gutter_ok:
          if s > 0: gutter lines = [m + k*(c+s) + c + j for k in 0..n-2 for j in 0..s-1]
                    require mean(empty_line[gutters]) >= 0.98, else reject
          if m > 0: margin lines (0..m-1) must be >= 0.98 empty, else reject
      boundary = boundary_strength(a, mask, axis, c, m, s)     # see below, 0..1
      half     = half_boundary_penalty(a, mask, axis, c, m, s) # 0..1, see below
      axis_score[c,m,s] = 0.55*boundary + 0.15*(1 if remainder==0 else 0.5)
                        + 0.15*(1 if s>0 else 0) + 0.15*(1 - half)

combine axes:
  if square: candidates are (c, mx, sx, my, sy) with the same c on both axes,
             score = (axis_x + axis_y) / 2
  else:      top 3 per axis, all pairs, score = (axis_x + axis_y) / 2
  cell_term  = empty_cell_alignment(mask, grid)               # 0..1
  prior_term = pack_prior.get(c, 0) if pack_prior else 0      # 0..1
  size_term  = {16: 1, 32: 1, 48: 0.9, 24: 0.7, 64: 0.7, 8: 0.5, 12: 0.4, 96: 0.4, 128: 0.4}[c]
  final = 0.60*score + 0.20*cell_term + 0.12*prior_term + 0.08*size_term
```

**boundary_strength:** for the boundary positions `p_k` (the first line of each cell after the first), compute the mean absolute RGBA difference between line `p_k - 1` and line `p_k`, restricted to positions where either line is occupied: `B`. Compute the same quantity for all non-boundary line pairs inside cells: `I`. Result: `clip((B - I) / (B + I + 1e-6) * 2, 0, 1)`. If there are no occupied pixels, return 0.

**half_boundary_penalty:** only applies when `2c` is also a valid size for this axis. Take the boundaries of size `c` at **odd** multiples (the ones that `2c` would not have). If their boundary strength is less than 0.35 × the strength at even multiples, return 1 (strong evidence that `c` is too small); otherwise return 0. This is what makes 48 beat 24 in `gutterless48`.

**empty_cell_alignment:** count the cells that are fully empty or fully occupied (`all` or `none` of their mask). Return `count / total_cells`. Real grids align with content, so mixed cells mean the grid is misaligned.

**Confidence for the catalog:** `top.score * min(1, 0.5 + (top.score - second.score) * 2)`.

**Tests:** for every synthetic pack's tile sheets, the top candidate equals the expected values; `gutterless48` → 48 (not 24); `gutter32` → margin [1,1] and separation [1,1]; a fully opaque 64×64 noise image returns candidates with scores below 0.5.

**Done when:** all synthetic expectations pass. Record any constant tuning in `IMPLEMENTATION_NOTES.md`.

---

## T2.06 — Frames, strips and baseline

**Depends on:** T2.05
**Files:** `rpggen/core/analyzer/frames.py`, `tests/unit/test_frames.py`

```python
@dataclass(frozen=True)
class StripInfo:
    axis: Literal["x", "y"]
    frames: int
    frame: tuple[int, int]

@dataclass(frozen=True)
class SheetLayout:           # directional character sheet
    frame: tuple[int, int]
    cols: int
    rows: int
    row_directions: list[str] | None   # e.g. ["down","left","right","up"] when inferable

def detect_strip(mask) -> StripInfo | None
def detect_character_sheet(a, mask, grid: GridCandidate | None) -> SheetLayout | None
def baseline_y(mask, frame_rects: list[tuple[int,int,int,int]]) -> int
def frame_bboxes(mask, frame_rects) -> list[tuple[int,int,int,int] | None]
```

**detect_strip:**
* Horizontal: `w % h == 0` and `2 <= w // h <= 32` → candidate frames of `h × h`.
* Vertical: the same with the axes swapped.
* Also try non-square frames: for each grid candidate with exactly one row (or one column), use `frame = cell`.
* Accept only if at least 75% of frames are non-empty, and the width and height of the non-empty bounding boxes vary by at most 40% of the frame size.

**detect_character_sheet:**
* Requires a grid with 3–12 columns and 4 or 8 rows, or a multiple of 4 rows (RPG Maker style 8-character sheets are handled by the adapter, not here).
* Every row must have at least 2 non-empty frames, and the counts must be consistent (all equal, ±1).
* `row_directions`: if there are 4 rows, compare each row's frame-0 mask with the others:
  * The row whose mirror image (`np.fliplr`) best matches another row → those two are left and right.
  * Among the remaining two rows, the one with more occupied pixels in the upper-middle region (face area) is `down`; the other is `up`. This is a weak heuristic.
  * Confidence 0.5 at most. Mark the asset `NEEDS_REVIEW` unless a filename token says otherwise.
  * Default order if inconclusive: `["down","left","right","up"]` (RPG Maker order), confidence 0.4.

**baseline_y:** the median over non-empty frames of the lowest occupied row inside the frame, relative to the frame's top.

**Tests:** `basic16` hero → 4×4 sheet with baseline 23; `strips` files → strips of 4 or 3 frames; `slime_idle` → a strip.

---

## T2.07 — Region detection (objects inside sheets)

**Depends on:** T2.05
**Files:** `rpggen/core/analyzer/regions.py`, `tests/unit/test_regions.py`

```python
def detect_regions(mask: np.ndarray, grid: GridCandidate,
                   min_cells: int = 2) -> list[tuple[int,int,int,int]]
    """Returns pixel rects [x,y,w,h] of multi-cell objects."""
```

Algorithm:
1. Build `occ[r][c]`: true when a cell has any occupied pixel.
2. Build `join_h[r][c]`, true when cells (r,c) and (r,c+1) are both occupied **and** art continues across the shared border. "Continues" means that in the last pixel column of the left cell and the first pixel column of the right cell, at least 25% of rows are occupied on both sides at the same y. With separation > 0, compare the columns on either side of the gutter. Build `join_v` the same way for vertical neighbors.
3. Union-find over cells, using only the joins.
4. Each component with at least `min_cells` cells whose bounding box (in cells) is at least 2 in one dimension → a region. The rect is the component's cell bounding box converted to pixels, then tightened to the occupied pixel bbox inside it.
5. Sort by `(y, x)`.

Tiles that tile seamlessly also "continue" across borders. Therefore: discard a component when **more than 60%** of the sheet's occupied cells belong to it, because it's probably a terrain area. Also discard components whose cell content is fully opaque in every cell (terrain fill).

**Tests:** `objects_in_sheet` → exactly 2 regions (the house and the tree), with the correct pixel rects; `basic16` terrain → 0 regions.

---

## T2.08 — Adapter framework

**Depends on:** T2.02
**Files:** `rpggen/core/adapters/base.py`, `rpggen/core/adapters/__init__.py`, `tests/unit/test_adapter_registry.py`

```python
@dataclass
class AssetFragment:
    path: str                      # posix path inside the pack
    facets: dict[str, Any]         # partial Facets (02_SCHEMAS §4.4)
    confidence: float
    claim: Literal["full", "partial"]   # full: classifier must not change usage/grid/anims

@dataclass
class AdapterResult:
    adapter: str
    assets: list[AssetFragment]
    objects: list[dict]            # SheetObject dicts with "sheet_path" instead of "sheet"
    tilesets: list[dict]           # TileSetDef dicts without source_id; sources by path
    pack_warnings: list[str]
    issues: list[Issue]

class Adapter(Protocol):
    name: str
    priority: int                  # lower runs first
    def match(self, inv: Inventory, root: Path) -> float: ...   # 0..1
    def extract(self, inv: Inventory, root: Path, ctx: AdapterContext) -> AdapterResult: ...
```

* The registry holds adapters ordered by priority: `profile`(0), `tiled`(10), `aseprite`(20), `ldtk`(30), `rpgmaker`(40), `lpc`(50), `strips`(60), `generic_grid`(100).
* `run_adapters(inv, root, ctx) -> list[AdapterResult]` runs `extract` for each adapter whose `match >= 0.5`, in priority order. `ctx.claimed: set[str]` tracks paths with `claim == "full"`; **later adapters must skip claimed paths.** `generic_grid` always runs last, on everything unclaimed.
* An adapter raising an exception → ADAPT-001 warning for that adapter; continue with the others. This is the **only** place broad `except Exception` is allowed, and it must log the traceback at DEBUG.

---

## T2.09 — Tiled adapter

**Depends on:** T2.08
**Files:** `rpggen/core/adapters/tiled.py`, `tests/unit/test_adapter_tiled.py`

**Inputs:** `.tsx` (XML tileset), `.tsj` (JSON tileset), `.tmx`/`.tmj` maps (read only for the tilesets they embed).

**Parsing `.tsx`** (use `xml.etree.ElementTree`; never `eval` anything):
```xml
<tileset name="ground" tilewidth="16" tileheight="16" spacing="1" margin="0" tilecount="64" columns="8">
  <image source="tiles.png" width="135" height="135"/>
  <tile id="5">
    <properties><property name="footstep" value="grass"/></properties>
    <objectgroup><object x="0" y="8" width="16" height="8"/></objectgroup>
  </tile>
  <tile id="9"><objectgroup><object x="0" y="0"><polygon points="0,0 16,0 16,16"/></object></objectgroup></tile>
  <wangsets>
    <wangset name="ground" type="corner" tile="-1">
      <wangcolor name="grass" color="#00ff00" tile="-1" probability="1"/>
      <wangcolor name="dirt" color="#aa5500" tile="-1" probability="1"/>
      <wangtile tileid="0" wangid="0,1,0,1,0,1,0,1"/>
    </wangset>
  </wangsets>
</tileset>
```

Produce:
* An AssetFragment for the image (resolved relative to the `.tsx` folder and normalized): `usage tiles`, grid from `tilewidth/height`, `margin` and `spacing` (Tiled's margin and spacing are the same on both axes), claim `full`, confidence 1.0.
* Tile id → coords: `(id % columns, id // columns)`.
* Collision objects → `tile_overrides["x,y"].collision = {profile: "CUSTOM", polygon: [...]}`. A rectangle object becomes 4 points `(x,y),(x+w,y),(x+w,y+h),(x,y+h)`. A polygon object's points are offset by the object's `x,y`. **Several objects on one tile:** take the convex hull of all points and add an ADAPT-001 info note to the detail (multi-polygon support comes in M8).
* Properties → `tile_overrides["x,y"].custom = {name: value}`, but only for names matching one of the custom data layers (`footstep`, `move_cost`). Ignore other property names, and list them in pack warnings once.
* Wang sets → a TileSetDef `terrain_sets` entry: `type="corner"` → mode `corners`; `"edge"` → `sides`; `"mixed"` → `corners_and_sides`. Colors map to terrains in order. Store the per-tile wang ids in `tile_overrides["x,y"].terrain = {"set": name, "wangid": [8 ints]}`. M8 converts these to peering bits; M2 only records them.
* Tile animations (`<animation><frame tileid tileduration>`) → `tile_overrides["x,y"].anim = {frames: [[x,y]...], durations_ms: [...]}`. These are recorded for M8 (TileSet animated tiles).
* `.tsj` uses the same mapping from JSON keys (`tilewidth`, `spacing`, `tiles[].objectgroup.objects`, `wangsets`).
* An image path that doesn't exist → ADAPT-002.

**match:** 1.0 if any `.tsx` or `.tsj` file exists; 0.6 if only `.tmx` maps with embedded tilesets exist (parse their `<tileset>` children the same way; external `source=` references point to `.tsx` files already covered).

**Tests:** `tiled_meta` produces the exact grid, 3 collision overrides (check their polygons), the terrain set and the footstep property.

---

## T2.10 — Aseprite adapter

**Depends on:** T2.08
**Files:** `rpggen/core/adapters/aseprite.py`, `tests/unit/test_adapter_aseprite.py`

* Match JSON files that have both `frames` and `meta.app` containing `"aseprite"`. Support both the hash format (`frames` is an object) and the array format (`frames` is an array).
* The image is `meta.image`, resolved relative to the JSON file.
* Frames: each has `frame {x,y,w,h}`, `duration` (ms), and optionally `spriteSourceSize` and `sourceSize`.
* Frame order: array order, or for the hash format, insertion order of keys (Python dicts preserve it).
* `meta.frameTags[]`: `{name, from, to, direction}` with direction `forward`, `reverse`, `pingpong` or `pingpong_reverse`. Expand the frame index list according to the direction.
* Because frames may not lie on a grid, the AnimSpec uses **explicit rects**. Add an optional AnimSpec field `"rects": [[x,y,w,h], …]`, which takes precedence over `frames`. Update `02_SCHEMAS.md` §4.4, the JSON schema and `sprite_frames_recipe.gd`: when `rects` is present, use `Rect2(rect)` directly as the AtlasTexture region. Also add `"offsets": [[ox, oy], …]` from `spriteSourceSize.x/y`; the recipe sets `AtlasTexture.margin = Rect2(ox, oy, sourceW - w, sourceH - h)` so trimmed frames stay aligned. ⚠ VERIFY the AtlasTexture margin semantics with a probe.
* Durations: `durations[i] = duration_ms / base_ms`, where `base_ms` is the most common duration in the tag. `fps = 1000 / base_ms`.
* Tag-name normalization: lowercase, then apply the synonyms table:

```python
SYNONYMS = {"run": "walk", "move": "walk", "walking": "walk", "stand": "idle", "idling": "idle",
            "atk": "attack", "attacking": "attack", "hit": "hurt", "damage": "hurt", "die": "death",
            "dead": "death", "dying": "death",
            "s": "down", "south": "down", "front": "down", "n": "up", "north": "up", "back": "up",
            "e": "right", "east": "right", "w": "left", "west": "left", "side": "right"}
```

  Split the name on `_`, `-` and spaces, map each token, and recombine as `<action>_<direction>` when both are known.
  * A `side` tag becomes `<action>_right`, plus a generated `<action>_left` with `flip_h: true` (ANIM-002 info).
  * A tag with an action but no direction → `<action>_down`, plus a pack warning that the direction was assumed.
  * Unknown actions are kept as-is (users may use them).
* Facets: usage `sprite`, role unset (the classifier decides from names), origin = `[frame_w // 2, baseline]`, where the baseline is computed from the first frame via `frames.baseline_y`. Claim `full`; confidence 1.0 for usage and animations.

**Tests:** `aseprite_meta` → `idle_down` and `walk_down`, `walk_right` plus a mirrored `walk_left`, correct durations, and rects equal to the JSON.

---

## T2.11 — RPG Maker adapter

**Depends on:** T2.06
**Files:** `rpggen/core/adapters/rpgmaker.py`, `tests/unit/test_adapter_rpgmaker.py`

**match:** score +0.5 if folders `img/tilesets` or `img/characters` exist (case-insensitive, at any depth); +0.3 if files match `^(.*_)?(A[1-5]|B|C|D|E)\.png$`; +0.2 if character sheets have dimensions that are multiples of `(3*48*4, 4*48*2)` or `(3*32*4, 4*32*2)`. Cap at 1.0.

**Tile size:** 48 if most matching images are multiples of 48 and not of 96; 32 for VX Ace dimensions (A2 sheets are 512×384 in VX Ace and 768×576 in MV/MZ). Record the decision in pack warnings.

**Tilesets:**
* `B`–`E` sheets → usage tiles, grid = tile size, no margin or separation. Role DECORATION, unless the file name contains `Outside`/`Inside`/`Dungeon`/`World`, which only selects the tileset name (`overworld`, `interior`, `dungeon` → a tileset named `dungeon`, `world`).
* `A1`–`A5` sheets: usage tiles with the same grid, but **mark these as autotile sheets**: role `AUTOTILE`, and `tags: ["rpgmaker_autotile", "A2"]` (etc.). They are placed in the TileSet as plain atlases in M2. M8 (T8.06) converts them into terrains. A5 is a plain tileset and gets role GROUND, not AUTOTILE.

**Characters (`img/characters/*.png`):**
* Name prefix `$` → a single character: frame = `(w/3, h/4)`.
* Otherwise → 8 characters in a 4×2 grid of blocks, each block 3 frames wide and 4 high: frame = `(w/12, h/8)`.
* Prefix `!` → an object (doors, chests). Its usage is still sprite, and it gets the tag `rpgmaker_object` with role DECORATION.
* For each character block `i` (0–7) that is not fully empty, create a **separate asset fragment** with the same path, `character_index = i` and the asset id suffix `#c<i>`. Catalog assembly (T2.14) turns fragments with `character_index` into distinct assets whose ids are `<asset_id>#c<i>`.
* Animations per block: row order `down, left, right, up`; columns 0,1,2. Walk = frames `[1, 0, 1, 2]` (pingpong around the standing middle frame) at 6 fps, looping. Idle = `[1]`, looping.
* Origin = `(frame_w/2, frame_h - 1)`. Character art in RPG Maker sheets is bottom-aligned, so this is correct.
* Role: PLAYER if the name contains `Actor` and the block index is 0; NPC for other `Actor`/`People` sheets; ENEMY for `Monster`/`Evil` sheets; otherwise NPC with confidence 0.6.

**Faces (`img/faces/*.png`):** 4×2 blocks of 144×144 (or 96×96 for VX Ace). Each block becomes a PORTRAIT asset `#f<i>`, with `usage portrait`, an AnimSpec-free facet `region` (add a `region` facet [x,y,w,h] to 02_SCHEMAS and the schema), confidence 0.95.

**RTP detection:** if a file name matches the known default RTP names (`Actor1.png`, `Actor2.png`, `Actor3.png`, `People1.png`…, `Outside_A1.png`…, `Inside_A1.png`…, `Dungeon_A1.png`…, `Monster.png`, `Evil.png`, `Nature.png`, `Damage1.png`), add ASSET-020 per file and the pack warning `rpgmaker_rtp_detected`. This is a name heuristic only. The message says "may be RTP"; it never blocks.

**Tests:** `rpgmaker_like` → 8 actor characters from `Actor1.png` plus 1 from `$Big.png`; frame 48×48; faces 144×144; tile size 48; A2 tagged `rpgmaker_autotile`.

---

## T2.12 — LPC, strips, LDtk and generic-grid adapters

**Depends on:** T2.06, T2.07
**Files:** `rpggen/core/adapters/lpc.py`, `strips.py`, `ldtk.py`, `generic_grid.py`, plus tests.

### LPC
* match: any image 832 px wide with height that is a multiple of 64 and at least 1344 (the standard LPC sheet), or containing `lpc` in its path.
* Standard row layout (64×64 frames, 13 columns). Each row lists its frame count:

| Rows | Action | Frames |
|------|--------|--------|
| 0–3 | spellcast up/left/down/right | 7 |
| 4–7 | thrust up/left/down/right | 8 |
| 8–11 | walk up/left/down/right | 9 (frame 0 = standing) |
| 12–15 | slash up/left/down/right | 6 |
| 16–19 | shoot up/left/down/right | 13 |
| 20 | hurt | 6 |

* Generated animations: `walk_<dir>` = frames 1–8 at 10 fps; `idle_<dir>` = frame 0; `attack_<dir>` = slash frames at 12 fps, with `active_frames [3, 4]`; `hurt` = row 20; `death` = row 20 played once (loop false).
* Origin `[32, 60]`. Verify it with `baseline_y`; if the measured baseline differs by more than 4 px, use the measured value.
* Taller sheets (expanded LPC with more rows) → use only these rows and add a pack warning.

### Strips
* Groups per-file strips by stem pattern: `^(?P<name>.+?)[_\- ](?P<action>idle|walk|run|attack|hurt|death|die|hit|move)(?:[_\- ](?P<dir>down|up|left|right|front|back|side|s|n|e|w))?$`, case-insensitive, with SYNONYMS applied.
* Each group (same `name` and folder) becomes **one asset** whose primary path is the first file sorted. Each AnimSpec has `source` set to its file, frames are `[[i,0] …]` along the strip, and the grid is the strip's frame size.
* Animated GIFs → one strip per GIF. Frames are extracted by `analysis` into the cache as a generated PNG strip at `local_cache_dir()/gif_strips/<sha>.png`. That PNG is installed into `generated/gif_strips/` in the project (never under `assets/packs`), and `source` points there.

### LDtk
* match: a `.ldtk` file exists. Parse JSON `defs.tilesets[]`: `relPath`, `tileGridSize`, `spacing`, `padding` (padding = margin).
* IntGrid layers in `defs.layers[]` with a value named `wall`, `solid` or `collision` (case-insensitive) → recorded as pack warning `ldtk_intgrid_collision_available`. M2 does not convert maps; that is deferred.
* Produce tiles fragments with a full claim for each tileset image.

### Generic grid
* Runs on every unclaimed image. Uses `detect_grid` with a `pack_prior` built from adapter results so far (tile sizes from claimed assets, weighted by count and normalized to 0..1).
* Decision tree:
  1. `detect_strip` passes → usage sprite (one row of frames), confidence 0.7.
  2. `detect_character_sheet` passes → usage sprite with directional animations (`walk_<dir>` = all frames of a row, `idle_<dir>` = frame 0), confidence `0.5 + 0.3 * grid.conf`.
  3. Grid top score ≥ 0.6 and image ≥ 2×2 cells → usage tiles, plus `detect_regions` → objects with `source: "auto"`.
  4. Image ≤ 64×64 with alpha and no grid → usage sprite (single frame), with likely role ITEM or DECORATION left to the classifier.
  5. Fully opaque and ≥ 256 px on both sides → usage background.
  6. Otherwise → usage sprite (single frame), confidence 0.3 (NEEDS_REVIEW).

**Tests:** for each relevant synthetic pack, the expected usage, grid and animation names.

---

## T2.13 — Classifier

**Depends on:** T2.12
**Files:** `rpggen/core/classifier.py`, `tests/unit/test_classifier.py`

```python
def tokens(posix_path: str) -> tuple[list[str], list[str]]:
    """Returns (folder_tokens, file_tokens). Split on non-alphanumerics and camelCase
    boundaries; lowercase; drop tokens of length 1 except direction letters; drop pure numbers."""

def classify(fragment_facets: dict, path: str, analysis: dict | None) -> tuple[str, float, list]:
    """Returns (role, confidence, roles_alt)."""
```

Keyword table (`ROLE_KEYWORDS`, weight 1.0 unless noted):

| Role | Keywords |
|------|----------|
| GROUND | grass, ground, dirt, floor, terrain, soil, tile, tiles, tileset (0.5) |
| ROAD | road, path, pavement, cobble |
| WATER | water, sea, lake, river, ocean, pond |
| WALL | wall, walls, fence |
| CLIFF | cliff, cliffs, mountain, ledge |
| BUILDING | house, building, buildings, home, shop, inn, castle, tower, barn, church, hut, tent, store |
| DECORATION | tree, trees, bush, rock, rocks, stone, flower, plant, prop, props, deco, decor, decoration, decorations, barrel, crate, sign, lamp, statue, well, object, objects |
| INTERIOR | interior, inside, indoor, room, furniture, inner |
| PLAYER | player, hero, heroine, protagonist, main (0.5) |
| NPC | npc, npcs, villager, merchant, townsfolk, people, citizen, shopkeeper, guard, character (0.5), characters (0.5) |
| ENEMY | enemy, enemies, monster, monsters, mob, mobs, slime, skeleton, goblin, bat, orc, zombie, bandit, wolf, spider |
| BOSS | boss, bosses |
| ITEM | item, items, icon, icons, potion, loot, pickup, gem, coin, key, food, consumable |
| WEAPON | weapon, weapons, sword, bow, axe, spear, staff, dagger |
| EFFECT | fx, effect, effects, vfx, explosion, slash, magic, spell, particle, smoke, impact |
| PROJECTILE | projectile, arrow, bullet, fireball, bolt |
| UI | ui, gui, hud, button, panel, frame, window, cursor, bar, dialog, dialogue, menu |
| PORTRAIT | portrait, portraits, face, faces, bust |
| BACKGROUND | background, backgrounds, bg, parallax, sky, title |

Scoring:
```text
score[role] = Σ weight * (1.0 if token in folder_tokens of the deepest 2 folders
                          else 0.6 if in other folders else 0.9 if in file tokens)
structure bonuses (added after keywords):
  usage == tiles      → GROUND +0.6, DECORATION +0.2, WALL +0.1
  usage == sprite with directional anims → NPC +0.5 (character default), PLAYER +0.1
  usage == sprite single frame ≤ 32px    → ITEM +0.4
  usage == background → BACKGROUND +1.0
  usage == portrait   → PORTRAIT +1.0
  nine_slice detected → UI +0.8
kind == audio → AUDIO_MUSIC if duration ≥ 20 s or name has music/bgm/theme/song, else AUDIO_SFX (conf 0.9)
kind == font  → FONT (conf 1.0)
role = argmax (ties: order of the table above)
confidence = s1 / (s1 + s2 + 0.5) where s1,s2 are top two scores; clip to [0, 0.95]
roles_alt = next 3 roles with their normalized scores
```

* Audio duration comes from `wave` for WAV files and `mutagen` for OGG/MP3 (add `mutagen>=1.47` as a dependency). Without mutagen, rely on the name only.
* Adapter-set roles are kept unless the adapter left the role empty.
* `nine_slice` detection lives in `analyzer/image_facts.py`: `detect_nine_slice(a) -> [l,t,r,b] | None`. A UI-like image (≥ 24 px both sides, has alpha) where the center region rows are identical to each other and the center columns are identical to each other → margins are the extents of the non-uniform border.

**Tests:** a table-driven test with about 40 path cases (write them in `tests/unit/classifier_cases.json`), including tricky ones such as `characters/enemies/bat.png` → ENEMY and `Tilesets/Interior/furniture.png` → INTERIOR.

---

## T2.14 — Catalog assembly (replaces the minimal catalog)

**Depends on:** T2.13
**Files:** `rpggen/core/catalog.py` (add `assemble`, `recompute_status`, `assign_tilesets`, `apply_folder_rules`), delete `build_minimal_catalog` and its golden test, `tests/unit/test_assemble.py`, golden files `tests/golden/<pack>.catalog.json` for every synthetic pack.

```python
def assemble(packs: list[tuple[OpenedPack, Inventory]], previous: Catalog | None,
             profiles: list[PackProfile]) -> tuple[Catalog, IssueList]
```

Steps:
1. For each pack, run the adapters (T2.08) and collect the AdapterResults.
2. For each image file in the inventory, sorted:
   * Merge all fragments for that path. Facets from `full` claims win. Otherwise, a fragment with higher confidence wins key-by-key.
   * Fragments with `character_index` or face index become separate assets (`#c<i>`, `#f<i>`).
   * If the role is unset, run `classify`.
   * Set `detected`, `detected_by` (the first adapter that contributed) and `confidence` (minimum of usage, grid and role confidence when present).
   * Set `path` to the project-relative path `assets/packs/<pack_id>/<pack path>`.
3. Audio and font files become assets with usage audio/font. License and doc files go into `CatalogPack.license_files` (doc files are not listed). Metadata files are not assets.
4. `apply_folder_rules(catalog)`: apply the rules from `previous` (if present) and from profiles.
5. **Carry overrides forward:** for each asset whose id exists in `previous`, copy `overrides` and keep any `CONFIRMED` status. If the sha256 changed, or the grid-relevant dimensions changed for an asset with usage tiles that is used in a tileset → `CONFLICT` plus TILE-004.
6. Assets in `previous` but not found now → keep them with status `MISSING` (CAT-004).
7. `assign_tilesets(catalog, previous)`:
   * Group usage=tiles assets by `(cell size, interior?)`. The interior flag is set when the role is INTERIOR or the path tokens include interior/inside.
   * Name the groups: `overworld`, `overworld_<size>`, `interior`, `interior_<size>`. The pack-wide most common size gets the plain name.
   * Group by the effective `tileset` facet if the user overrode it.
   * For each source asset, reuse `source_id` from `previous` when the asset id matches. Otherwise call `allocate_source_id`.
   * Never renumber. Removed sources go to `retired`.
   * The TileSetDef gets the default physics layer, the 3 custom data layers and the terrain sets from adapter tileset dicts (merged by name).
8. `recompute_status` for every asset.
9. Sort everything. Validate against the schema.

**Tests:** a golden catalog for every synthetic pack. Then run assemble again with the previous catalog plus an override on one asset → the override is kept and source ids are unchanged. Removing a file → MISSING, and the source id stays allocated.

**Orchestrator:** replace the `catalog` phase so it opens packs, builds inventories and calls `assemble`. `install_pack` now copies only inventory files (it skips junk) and also copies `generated/gif_strips/` outputs.

---

## T2.15 — Required roles and placeholders

**Depends on:** T2.14
**Files:** `rpggen/core/requirements.py`, `rpggen/core/placeholders.py`, `tests/unit/test_requirements.py`

* `REQUIRED = {"turn_based": ["PLAYER", "GROUND"], "arpg": ["PLAYER", "GROUND"]}`.
* `RECOMMENDED = ["NPC", "ENEMY", "BUILDING", "WALL", "ITEM", "UI", "PORTRAIT"]`.
* `check(catalog, cfg) -> IssueList`: ASSET-010 for missing required roles (error) and missing recommended roles (warning). ASSET-014 when there is more than one PLAYER and none is CONFIRMED.
* `make_placeholder(role, size: tuple[int,int], out: Path) -> Path`:
  * Generates a PNG with a magenta (#FF00FF)/black 4px checkerboard, a 1px white border, and the text `MISSING\n<ROLE>\n<w>x<h>` drawn with Pillow's default bitmap font, centered, in white with a black outline.
  * For PLAYER, NPC and ENEMY, it generates a 4×4 sheet (rows down/left/right/up) with the arrow direction drawn in each frame, so movement is visible.
  * Default sizes: characters 16×24 × base_tile_size/16; GROUND a 4×1 tiles strip.
* The orchestrator calls this in the `catalog` phase **only for roles the user chose to placeholder** (CLI flag `--placeholder ROLE` repeated; the GUI sets this in M3). The placeholder becomes an asset in pack `debug_placeholders`, with path `generated/debug_placeholders/<role>.png`, tag `debug_placeholder` and status CONFIRMED.
* If a required role is still missing → the error stops generation before Godot runs.

---

## T2.16 — `rpggen analyze` and the accuracy metric

**Depends on:** T2.14
**Files:** `rpggen/cli.py` (`analyze`), `rpggen/core/accuracy.py`, `tests/unit/test_accuracy.py`, `.github/workflows/ci.yml` (add the accuracy step)

* `rpggen analyze <pack> [--out catalog.json] [--expected expected.json]` prints a table: path, usage, role, grid/frame, confidence, status. With `--expected`, it also prints the accuracy.
* `accuracy.score(catalog, expected) -> dict`: per field (usage, role, cell, margin, separation, frame, anims), `correct/total`, plus an overall value. Counts only paths present in `expected`.
* `rpggen analyze --corpus test_packs/synthetic` runs every pack that has an expected file and writes `accuracy_report.json`.
* CI fails if the synthetic corpus accuracy falls below: **grid 0.95, usage 0.95, role 0.85, anims 0.90**. Store the thresholds in `accuracy.py`.

---

## T2.17 — Milestone Gate M2

- [ ] All synthetic packs generate end-to-end (validation and smoke pass for packs that have a PLAYER and GROUND; others are tested with `analyze` only).
- [ ] Accuracy thresholds are met in CI.
- [ ] `build_minimal_catalog` no longer exists anywhere (grep for it).
- [ ] Generation of `zipped` equals generation of `basic16` (same catalog apart from pack_id/source fields).
- [ ] The human maintainer has run `rpggen analyze` on 3 real packs they own and recorded the results in `IMPLEMENTATION_NOTES.md` (this is input to the §51 coverage study).
