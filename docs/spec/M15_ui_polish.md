# M15 — Look, Feel and Ease of Use (release 1.3.0)

**Goal:** make the wizard look like a designed application and make every page quicker to use,
without taking away or moving a single function. The review of 2026-10-09 found that the wizard
runs on Qt's stock Fusion style with a 60-line stylesheet: buttons, inputs, tabs, scrollbars,
group boxes and cards all draw with Qt's defaults, there are no icons, the sidebar is a plain
list, and several pages are denser or emptier than they need to be. It also found one bug (raw
colour-escape codes in the Generate log), two things that waste time (a regeneration with
nothing changed takes as long as a full run; a failed run says "see the log" and shows nothing
of it) and one safety net that is missing (no visual regression test, so stylesheet work can
break a page silently).

Part A is the design system: tokens, a complete stylesheet, button kinds, icons, cards, the
stepper sidebar and page headers. Part B applies it page by page. Part C is the three
improvements beyond the look. Part D is the documentation, the screenshots and the gate.

This file follows the format of M01–M14. It was written against the branch `m14` (the 1.2.0
candidate) on 2026-10-09. **This milestone starts after `v1.2.0` is tagged** (T14.13) and ends
with `v1.3.0`.

## Ground rules for this milestone

* The M12 and M13 ground rules apply unchanged: core logic stays out of the GUI, pages only edit
  `WizardState`, every audit edit is undoable, and the post-release compatibility contract
  holds (`config_version` and `save_version` stay 1; nothing under `game/` is rewritten).
* **Nothing is removed and nothing moves out of reach.** Every control, menu entry, shortcut and
  dialog of 1.2.0 exists in 1.3.0 with the same object name (the GUI tests find widgets by
  object name) and the same shortcut. A card that moves a control to another place on the page
  says so in its spec; a card that puts a control behind a menu is a mistake, not a decision.
* **No new runtime dependency.** Icons are SVG files in the package, not an icon-font package;
  the stylesheet is rendered by rpggen's own code, not a theming library.
* **The tests that guard the GUI stay green at every card**, in both themes, at the minimum
  window (880 × 540) and the default (1100 × 720): `tests/gui/test_layout_fit.py` (nothing
  clipped or squeezed), `tests/gui/test_theme_a11y.py` (tooltips, names, tab order, mnemonic
  shortcuts, 3:1 status colours, status never colour-only, reduce motion, display scaling)
  and the page tests. A card that changes a selector or an object name updates the test that
  names it in the same commit.
* **Contrast.** Body text 4.5:1 against its surface, muted text 4.5:1, the six status colours
  3:1 against both base colours (the existing test), control borders and the focus ring 3:1.
  `docs/spec/M13_polish.md` T13.10 stays the reference for display scaling: icons are SVG,
  overlays stay one device pixel, nothing is a bitmap that blurs at 150 %.
* **Translation.** Every new user-visible string goes through `self.tr()` and
  `python tools/update_translations.py`; the French file gets the new strings marked
  unfinished (CONTRIBUTING says how).
* **Reduce motion** (`theme.reduce_motion()`) turns off every animation a card adds.
* **The screenshots** (`tools/make_doc_screenshots.py`) are regenerated at the end of each part,
  not at the end of the milestone, so the user guide never lags more than a part behind.
* **One pull request per card**, each with a before/after screenshot of every page it touches,
  in both themes, in its description.

## Order of work

| Step | Tasks | Why this order |
|------|-------|----------------|
| 1 | T15.16, T15.18 | Two small fixes with no dependency; they ship first and give the branch a green start |
| 2 | T15.01, T15.02, T15.03, T15.04, T15.05 | The design system; every later card builds on the tokens and the stylesheet |
| 3 | T15.06, T15.07, T15.08, T15.09 | The shell: page headers, the stepper, cards, motion and focus |
| 4 | T15.10 – T15.15, T15.17, T15.19 | The pages and dialogs, one card each; independent of one another |
| 5 | T15.20, T15.21, T15.22 | Beyond the look |
| 6 | T15.23, T15.24, T15.25 | Visual goldens, documentation, the gate, then tag `v1.3.0` |

Tasks inside a step are independent unless **Depends on** says otherwise.

## Index

Sizes are rough: **S** under a day, **M** 1–3 days, **L** 3–7 days.

| Card | Title | Size | Depends on | Status |
|------|-------|:----:|------------|--------|
| T15.01 | Design tokens and one stylesheet template | M | — | open |
| T15.02 | Every stock widget styled | L | T15.01 | open |
| T15.03 | Button kinds | S | T15.02 | open |
| T15.04 | An icon set | M | T15.01 | open |
| T15.05 | No inline styles | S | T15.01 | open |
| T15.06 | One page header everywhere | S | T15.02 | open |
| T15.07 | The stepper sidebar | M | T15.02, T15.04 | open |
| T15.08 | Cards | M | T15.02 | open |
| T15.09 | Focus ring and page motion | S | T15.02 | open |
| T15.10 | Welcome view | M | T15.06, T15.08 | open |
| T15.11 | Project page | M | T15.06, T15.08 | open |
| T15.12 | Audit page | L | T15.06, T15.04 | open |
| T15.13 | Mapping page | M | T15.06, T15.04 | open |
| T15.14 | Options page | M | T15.06, T15.08 | open |
| T15.15 | Generate page | S | T15.06, T15.07 | open |
| T15.16 | Generate log: no colour-escape codes | S | — | open |
| T15.17 | Results page | M | T15.06, T15.08, T15.21 | open |
| T15.18 | Window title with the project and the step | S | — | open |
| T15.19 | Dialogs | S | T15.02, T15.03 | open |
| T15.20 | Regeneration that skips what did not change | M | — | open |
| T15.21 | Failures that say what to do | M | — | open |
| T15.22 | Try the sample in two clicks | S | — | open |
| T15.23 | Visual regression goldens | M | T15.10 – T15.19 | open |
| T15.24 | Documentation, screenshots and changelog | S | Parts A–C | open |
| T15.25 | Gate (1.3.0) | S | T15.23, T15.24 | open |

---

# Part A — The design system

## T15.01 — Design tokens and one stylesheet template

**Depends on:** nothing
**Files:** `rpggen/gui/theme.py`, `rpggen/gui/style.qss.in` (new, replaces `style.qss` and
`style_light.qss`), `pyproject.toml` (package data), `packaging/rpggen.spec`,
`tests/gui/test_theme_a11y.py`

Two stylesheets with the same selectors and different colours are kept in step by a test. They
hold eleven rules. Every other colour, size and spacing in the wizard is either Qt's default or
a number typed into a widget's code.

**Spec**
* `theme.TOKENS` becomes the single table of design values, one dictionary per theme plus a
  shared one for sizes. The colours (starting values; the contrast tests decide the final ones):

  | Token | Dark | Light | Used for |
  |-------|------|-------|----------|
  | `bg` | `#1b1e24` | `#f5f6f8` | the window |
  | `base` | `#20232a` | `#ffffff` | inputs, lists, the audit grid (`theme.BACKGROUNDS` reads these) |
  | `surface` | `#262a32` | `#ffffff` | cards, group boxes, the detail panel |
  | `surface_hover` | `#2d323c` | `#f0f2f5` | a card or row under the pointer |
  | `border` | `#373d48` | `#d9dde3` | 1 px lines |
  | `border_strong` | `#4b5362` | `#b9c0ca` | input borders, dividers that must be seen |
  | `text` | `#e6e8ec` | `#1f2328` | body text |
  | `text_muted` | `#9aa3b2` | `#5f6672` | hints, captions, secondary rows |
  | `accent` | `#4f8ff7` | `#2f6fd6` | the one primary button, selection, links, the current step |
  | `accent_hover` | `#6aa2ff` | `#2a62bd` | |
  | `accent_pressed` | `#3b76d8` | `#24549f` | |
  | `on_accent` | `#ffffff` | `#ffffff` | text on the accent |
  | `focus` | `#8db8ff` | `#2f6fd6` | the keyboard focus ring |
  | `danger`, `warning`, `success` | the `state` label colours of today | | banners, badges, the problem label |

  The six **status colours** of the audit grid do not change and stay in
  `widgets/asset_grid.py` (`STATUS_COLORS`); the template reads them from there so the mirror
  comment and its test go away.
* The shared sizes: spacing `4, 8, 12, 16, 24, 32`; radii `control 6`, `card 10`, `chip 999`;
  the type scale `caption 12 px`, `body (the application font, unchanged)`, `section 15 px
  semibold`, `title 18 px semibold`, `display 22 px bold`; `control_height 30`; `icon 16`.
* `style.qss.in` is one file with `@name` placeholders (`@accent`, `@radius_card`,
  `@icons/check.svg`). `theme.stylesheet(name)` renders it: every placeholder is replaced from
  `TOKENS[name]` merged with the sizes, `@icons/` with the absolute path of the icon folder
  (T15.04), and a placeholder that is not a token raises `KeyError` at start-up, so a typo is
  found by the first test that applies a theme. `style.qss` and `style_light.qss` are deleted.
* `theme.palette(name)` reads the same tokens (window = `bg`, base = `base`, text, button =
  `surface`, mid = `border_strong`, highlight = `accent`, placeholder = `text_muted`, link =
  `accent`), so the palette and the stylesheet cannot disagree.
* `theme.token(name)` keeps its signature; the canvas tokens (`canvas_bg`, `grid_line`,
  `diff_changed`) join the table.
* A helper `theme.px(name) -> int` and `theme.color(name) -> QColor` for the few widgets that
  paint (the asset grid, the map preview, the stepper delegate), so no painter has a literal.

**Tests**
* The template renders for both themes with no placeholder left (`"@" not in rendered` outside
  `url()` paths); every token of the table is used at least once in the template or in Python
  (a token nobody reads is deleted).
* The rendered dark and light stylesheets have the same selectors in the same order (replaces
  the two-file test).
* `text` and `text_muted` have 4.5:1 against `bg`, `base` and `surface`; `border_strong` and
  `focus` have 3:1 against `bg` and `surface`; `on_accent` has 4.5:1 against `accent`; the six
  status colours keep 3:1 against both `base` values (the existing test, reading `BACKGROUNDS`
  from the tokens).
* `apply_theme("light")` still changes the palette and is remembered; the system theme still
  follows a faked scheme change.

**Done when**
* The wizard starts in both themes with the rendered stylesheet; nothing looks different yet
  (this card moves the colours, it does not change them beyond the table above).

## T15.02 — Every stock widget styled

**Depends on:** T15.01
**Files:** `rpggen/gui/style.qss.in`, `rpggen/gui/theme.py` (a `QProxyStyle`), `rpggen/gui/app.py`,
`rpggen/gui/icons/` (four indicator SVGs: `check`, `dot`, `chevron_down`, `chevron_right`),
`tests/gui/test_layout_fit.py`, `tests/gui/test_theme_a11y.py`

**Spec**
* Rules in the template for every widget the wizard uses, each with its normal, hover, pressed,
  checked, disabled and focused look drawn from the tokens:
  * `QPushButton`, `QToolButton`: height 30, radius 6, 1 px `border_strong`, `surface`
    background, `surface_hover` on hover, `accent` outline on keyboard focus; a menu button's
    arrow is `chevron_down.svg`.
  * `QLineEdit`, `QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QPlainTextEdit`, `QTextEdit`:
    `base` background, 1 px `border_strong`, radius 6, 6 px padding, `accent` border when
    focused, `text_muted` placeholder; the combo's popup is a `QListView` with `surface`
    background, 1 px border, 4 px rounded items and `accent` selection.
  * `QCheckBox::indicator`, `QRadioButton::indicator`: 18 px, drawn from the tokens with
    `check.svg` / `dot.svg` in `on_accent` on an `accent` fill when checked; the indicator of a
    partially checked box is a short bar.
  * `QTabWidget::pane`, `QTabBar::tab`: an underline tab bar (no boxes): the selected tab has a
    2 px `accent` underline and `text`, the others `text_muted`, 8 × 14 px padding; the pane has
    no frame; the corner widget keeps 8 px from the last tab (the clipped *Profile* button of
    today is fixed by T15.12, which moves it).
  * `QScrollBar`: 10 px, no arrows, a rounded `border_strong` handle that becomes `text_muted`
    on hover, a transparent trough.
  * `QProgressBar`: 8 px high, radius 4, `border` trough, `accent` chunk, text hidden (the
    pages say the number beside it).
  * `QGroupBox`: a card (`surface`, 1 px `border`, radius 10, 16 px padding) with its title as
    a section heading (15 px semibold) inside the top-left corner, not on the border.
  * `QMenuBar`, `QMenu`: `bg` / `surface`, 1 px border, radius 8, 6 × 12 px items, `accent`
    selection, a `border` separator; `QToolTip`: `surface`, 1 px border, radius 6, 6 × 8 px.
  * `QListView`, `QTreeView`, `QTableView`, `QHeaderView::section`: `base` background, no
    frame, 4 px rounded selection in `accent`, a `surface` header with a bottom border; the
    audit grid, the pack list and the phase list keep their delegates.
  * `QSplitter::handle`: 1 px `border`, 6 px wide hit area; `QSlider`: a 4 px groove, a 16 px
    round `accent` handle; `QStatusBar`, `QFrame[frameShape="4"]` (horizontal lines) → `border`.
* A `WizardStyle(QProxyStyle)` over Fusion draws the **focus ring** (2 px `focus`, radius 6,
  outside the control) only for keyboard focus (`Qt.FocusReason.TabFocusReason`,
  `BacktabFocusReason`, `ShortcutFocusReason`) and never for a mouse click, and draws the
  check-box and radio indicators when a platform ignores the stylesheet image (macOS).
* The application font is not changed; `app.create_app` sets `QApplication.setFont` only on
  Linux when the system font is missing (the screenshot tool's `ensure_real_font` already
  knows how).

**Tests**
* `test_layout_fit.py` passes unchanged: a 30 px control height and 14 px tab padding must not
  clip a button or a combo at 880 × 540 in either theme. A rule that fails it is changed, not
  the test.
* A new test renders a `QCheckBox`, a `QComboBox` and a `QPushButton` offscreen in both themes
  and checks that the pixel in the middle of the checked indicator is the accent and that the
  button's border differs from its background (the stylesheet really applies).
* The focus ring is drawn after `Tab` and not after a click (grab the widget, compare the
  border pixels).
* `test_theme_a11y.py`: every rule's `color` against its `background` meets the ratios of the
  ground rules (a small parser over the rendered stylesheet; it covers the pairs it finds and
  skips rules without both).

**Done when**
* Every page looks consistent in both themes with no stock Fusion control left (walk the pages
  and the dialogs: Storage, Conflicts, Variant, Regeneration preview, Grid editor, Animations,
  Object cutter, Asset picker, Profile, Learned rules, About, Crash).

## T15.03 — Button kinds

**Depends on:** T15.02
**Files:** `rpggen/gui/style.qss.in`, `rpggen/gui/widgets/buttons.py` (new),
`rpggen/gui/wizard.py`, `rpggen/gui/pages/*.py`, `rpggen/gui/dialogs/*.py`

Today every button looks the same, so the eye has nothing to find: *Next* and *Browse…* carry
the same weight.

**Spec**
* A dynamic property `kind` on `QPushButton` and `QToolButton` with four values:
  * `primary`: `accent` fill, `on_accent` text, semibold. **One per view**: the wizard's Next /
    Generate / Show results, *Open in Godot* on Results, *Confirm* in the audit's detail panel,
    the accepting button of a dialog.
  * `secondary` (the default): as T15.02 draws it.
  * `quiet`: no border and no fill until hover (Quit, *Remove from the list*, *Show in folder*,
    the per-row buttons of the Mapping page, the audit's *Shortcuts*).
  * `danger`: `danger` border and text, `danger` fill with white text on hover (the Storage
    dialog's *Clear* of *your data*; nothing else is destructive, so nothing else gets it).
* `buttons.set_kind(button, kind)` sets the property and repolishes (a property set after the
  widget is shown needs `unpolish`/`polish` to take effect; the helper does it so no page
  forgets).
* The wizard's bottom bar: *Quit* `quiet` at the left, *Back* `secondary`, *Next* `primary`,
  both 96 px wide at least so the bar does not move as the label changes between *Next*,
  *Generate* and *Show results*. The Generate page's *Cancel* takes the Next button's place in
  the bar while a run is on (the page hides Quit already); it is `secondary`.
* The accessible description of a `primary` button says "main action", so a screen reader
  tells the user which one it is.

**Tests**
* Every page and the welcome view have exactly one visible `primary` button at a time
  (`test_theme_a11y.py`); the wizard's Next is it on pages 1–5, Show results on 6, Open in
  Godot on 7 after a success and none after a failure.
* The bottom bar's buttons keep their object names and mnemonic shortcuts (`Alt+N`, `Alt+B`).

**Done when**
* On every page the primary action is the first thing the eye finds.

## T15.04 — An icon set

**Depends on:** T15.01
**Files:** `rpggen/gui/icons/*.svg` (new, about 36 files), `rpggen/gui/icons.py` (new),
`THIRD_PARTY_NOTICES.md`, `pyproject.toml`, `packaging/rpggen.spec`, `tests/gui/test_icons.py` (new)

The wizard has no icons. A sidebar step, a Browse button, a status and a Play button all read
as words only.

**Spec**
* The icons are **Lucide** (ISC licence; recorded in `THIRD_PARTY_NOTICES.md` with the licence
  text), copied as plain SVG with `stroke="currentColor"`, 24 px viewBox. The set: `folder`,
  `folder-open`, `file-archive`, `plus`, `x`, `trash`, `check`, `check-circle`, `alert-triangle`,
  `x-circle`, `info`, `circle`, `circle-dot`, `search`, `filter`, `layout-grid`, `list`,
  `play`, `pause`, `square`, `eye`, `external-link`, `download`, `refresh-cw`, `settings`,
  `sliders`, `chevron-down`, `chevron-right`, `chevron-left`, `undo`, `redo`, `map`, `image`,
  `music`, `volume-2`, `box`, `gamepad-2`, `user`, `users`, `swords`, `book-open`, `help-circle`,
  `copy`. A card that needs another one adds it to the folder and to this list.
* `icons.icon(name, color: str | None = None, size: int = 16) -> QIcon`: renders the SVG with
  `currentColor` replaced by `color` (default `text`), at `size` × the screen's device pixel
  ratio, cached per `(name, color, theme, ratio)`; a second pixmap in `text_muted` is the
  icon's disabled mode. `theme.signals.changed` clears the cache, and every widget that holds
  an icon re-asks for it (a `ThemedIcon` helper that connects for a button or an action, so no
  page writes that code).
* `icons.pixmap(name, color, size)` for labels and delegates.
* Where icons go in this milestone: the stepper (T15.07), the page headers' help link
  (T15.06), the Project page's Add Zip / Add Folder / Remove / Browse buttons, the audit's
  filter row and Confirm / Exclude / Edit grid / Animations / Cut objects buttons, the Mapping
  rows' Choose / Clear / Show in audit buttons, the Generate phase list, the Results actions
  (Open in Godot, Play, Open starter map, Open failed folder, View logs, Export bundle), the
  welcome cards, the Godot status row, the menu actions that have an obvious one (New, Open,
  Undo, Redo, Review mode, User guide). Text stays beside every icon except on the per-row
  buttons of the Mapping page and the filter row of the audit, where the tooltip carries it.
* Icons never carry meaning alone: a state icon always sits next to its word or has it as the
  accessible name (the existing "not colour-only" rule, extended to "not icon-only").

**Tests**
* Every file in the folder is well-formed SVG with `currentColor` and no fixed colour; every
  name the code asks for exists (a scan of `icons.icon("` and `icons.pixmap("` calls).
* An icon at ratio 2 has twice the device pixels; after a theme change the cached pixmap for
  the old theme is gone.
* The frozen build (`tools/package.py --smoke`) finds the icon folder.

**Done when**
* The icons are in place in the spots above and nothing says less than before.

## T15.05 — No inline styles

**Depends on:** T15.01
**Files:** `rpggen/gui/pages/archetype_page.py`, `rpggen/gui/pages/results_page.py`,
`rpggen/gui/pages/welcome_page.py`, `rpggen/gui/widgets/asset_detail.py`,
`rpggen/gui/widgets/collapsible.py`, `rpggen/gui/widgets/map_preview.py`,
`rpggen/gui/widgets/options_summary.py`, `rpggen/gui/style.qss.in`, `tests/gui/test_theme_a11y.py`

Ten widgets set their own colours or fonts with `setStyleSheet`, which is why the archetype
cards, the summary chips and the welcome title do not follow the theme.

**Spec**
* Each inline style becomes a rule in the template keyed by object name or property:
  `QLabel#welcomeTitle` (display size), `QLabel[role="title"]`, `QLabel[role="section"]`,
  `QLabel[role="caption"]` (the type scale, used by T15.06 onwards), `QToolButton[card="true"]`
  and `:checked` (the archetype cards, T15.08 refines them), `QLabel#check_*` → one property
  `accentGlyph="true"`, `QLabel[stat="true"]` (the Results counts), `QPushButton[kind="primary"]`
  (T15.03 replaces the Open in Godot style), `QToolButton#collapsibleHeader`,
  `QLabel[chip="true"]`.
* Two inline styles carry **data** colours and may stay, read from a table instead of a literal:
  the status badge of the detail panel (from `STATUS_COLORS`) and the legend dots of the map
  preview (from `map_preview.MARKER_COLORS`). They are the only two.
* `tests/gui/test_theme_a11y.py` gets `test_no_inline_styles`: a scan of `rpggen/gui` for
  `setStyleSheet(` finds only `theme.py` and the two allowed call sites.

**Done when**
* The scan passes and the light theme shows no dark-theme leftover (the archetype card borders
  and the chips were the visible ones).

## T15.06 — One page header everywhere

**Depends on:** T15.02
**Files:** `rpggen/gui/widgets/page_header.py` (new), `rpggen/gui/pages/base.py`, every page,
`rpggen/gui/wizard.py`, `tests/gui/test_shell.py`

The Project page has no title, the Archetype page starts with a question, the Audit page with a
progress bar and the Options page with a preset combo; the margins differ from page to page.

**Spec**
* `PageHeader(title, purpose)`: the title at `title` size, the one-line purpose in `text_muted`
  under it, and at the right a `quiet` help button with the `help-circle` icon that opens the
  user guide at the page's `help_anchor` (what `F1` does). Between them a slot
  (`header.add_widget`) for a page's own controls: the audit's review-progress line and
  *Review mode* button, the Mapping page's *Undo*, the Options page's preset bar and *Reset to
  defaults*, the Generate page's elapsed time.
* `WizardPage` gains `purpose = ""` and builds the header itself in `__init__` from `title` and
  `purpose`; pages that already have a `title` get a purpose:

  | Page | Title | Purpose |
  |------|-------|---------|
  | Project | Project | Your asset packs, where the project goes, and which Godot builds it. |
  | Archetype | Kind of game | Choose how the game plays. You can make the other kinds later. |
  | Audit | Audit | Check what rpggen found in your packs. Confirm what is right, fix what is not. |
  | Mapping | Mapping | Which asset plays each part in the starter map and the systems. |
  | Options | Options | What the project includes. Presets fill the page in one click. |
  | Generate | Generate | rpggen builds, checks and plays the project before it hands it over. |
  | Results | Results | What was made, what to look at, and what to do next. |
* Every page's layout: margins 24 px left and right, 20 px top, 16 px bottom, 12 px between
  the header and the body (`theme.px("space_24")` and so on; no literal).
* The problem label of the window (the red line above the buttons) becomes a banner (T15.08's
  `Banner`, `danger` kind) with the `x-circle` icon.

**Tests**
* Every page has a `PageHeader` whose title equals the sidebar name and whose help button opens
  the guide at `help_anchor` (`test_help_anchors.py` extends to the button).
* `test_layout_fit.py` still passes with the header at 880 px.

**Done when**
* The seven pages open with the same header in the same place.

## T15.07 — The stepper sidebar

**Depends on:** T15.02, T15.04
**Files:** `rpggen/gui/widgets/stepper.py` (new: a `QStyledItemDelegate`), `rpggen/gui/wizard.py`,
`rpggen/gui/style.qss.in`, `tests/gui/test_shell.py`, `tests/gui/test_theme_a11y.py`

**Spec**
* The sidebar stays a `QListWidget` (the tests and the keyboard handling work on it) and gets
  a `StepDelegate` that paints each row as a step: a 24 px circle at the left joined to the
  next by a 2 px vertical line, the step's name and its count beside it.
  * Not visited: an outlined circle (`border_strong`) with the number; `text_muted` name.
  * Current: an `accent`-filled circle with the number in `on_accent`, `text` name in
    semibold, a 3 px `accent` bar at the row's left edge (not a full-row fill).
  * Done (`ok`): a `success`-filled circle with the `check` icon; the line down to the next
    step is `success` too.
  * Attention: a `warning` circle with the `alert-triangle` icon and the count after the name
    (`Audit · 12`); error: a `danger` circle with `x-circle`.
  * Disabled rows (not reachable yet) are `text_muted` at 60 %.
* Narrow mode (below 1000 px): the circles and the line only, 52 px wide as today; the names
  and counts stay in the tooltips and the accessible names (unchanged).
* The row's accessible name keeps the "Step 3, Audit, needs attention (12)" form; the glyphs
  (`✓ ⚠ ✖`) stay in `STATUS_GLYPHS` for the narrow-mode text and the screen reader, so the
  status is never icon-only.
* The hover look: `surface_hover` on the row; the pointer cursor on an enabled row.
* The welcome view hides the sidebar as before; the first wizard page shows it.

**Tests**
* `test_shell.py` still reads status from `sidebar.item(i)`; the delegate's `paint` is
  exercised by grabbing the sidebar in both themes at both widths and checking the circle's
  centre pixel for the current and for a done step.
* `test_theme_a11y.py`: the accessible names are unchanged.

**Done when**
* The sidebar reads as progress at a glance, wide or narrow.

## T15.08 — Cards

**Depends on:** T15.02
**Files:** `rpggen/gui/widgets/card.py` (new), `rpggen/gui/pages/welcome_page.py`,
`rpggen/gui/pages/archetype_page.py`, `rpggen/gui/widgets/pack_list.py`,
`rpggen/gui/widgets/options_summary.py`, `rpggen/gui/style.qss.in`

**Spec**
* `Card(QFrame)`: `surface`, 1 px `border`, radius 10, 16 px padding; property
  `interactive="true"` adds `surface_hover` and a `border_strong` border on hover and the
  pointer cursor. `Banner(Card)`: a one-line card with an icon and a `kind` (`info`, `warning`,
  `danger`, `success`) that colours its left 3 px edge and icon; the text wraps.
* `CardButton(QPushButton)` with `kind="card"`: a whole card that is a button, for the welcome
  view's three choices: an icon at the top left (`play`, `folder-open`, `refresh-cw`), the
  title at `section` size, the description in `text_muted`, and 2 px `accent` border when it
  has keyboard focus. The sample card's split arrow (today a narrow strip that reads as a
  scrollbar) becomes a `quiet` button *Choose a sample ▾* under the description that opens the
  same menu; a click on the card itself is the top-down village, as before.
* The archetype cards: 1 px `border`, radius 10, `surface`; checked: 2 px `accent` border and
  a `check-circle` icon in `accent` at the top right (the `✔` label of today, now an icon with
  the same object name and accessible text).
* The pack cards (`PackCardDelegate`) and the project cards (`ProjectCard`): the same radius,
  border and hover; the pack card's format and licence badges use the chip rule.
* The options summary, the audit detail panel and each feature group of the Options page are
  `Card`s (T15.12, T15.14 place them).

**Tests**
* The welcome cards are reachable with Tab, activate with Enter and Space, and keep their
  object names and signals (`test_menus_welcome.py`).
* The archetype cards still show the check when chosen (`test_theme_a11y.py`).

**Done when**
* Every card-shaped thing in the wizard is one of these three classes.

## T15.09 — Focus ring and page motion

**Depends on:** T15.02
**Files:** `rpggen/gui/wizard.py`, `rpggen/gui/theme.py`, `tests/gui/test_shell.py`

**Spec**
* A page change cross-fades the stacked widget over 120 ms (`QGraphicsOpacityEffect` on the
  incoming page, `QPropertyAnimation`); with `theme.reduce_motion()` the change is immediate.
  The welcome view's change to the wizard does the same.
* A `Banner` that appears (the problem label, a Results banner) slides nothing: it appears.
  Motion is only on page changes.
* The focus ring of T15.02 is the only focus indication; the stylesheet's `:focus` rules are
  removed so a mouse click shows no ring.

**Tests**
* With reduce motion on, `show_page` changes the stack index synchronously; with it off, the
  index changes at once and the opacity reaches 1 within 200 ms (`qtbot.waitUntil`).

**Done when**
* Page changes feel settled and nothing flashes.

---

# Part B — The pages

## T15.10 — Welcome view

**Depends on:** T15.06, T15.08
**Files:** `rpggen/gui/pages/welcome_page.py`, `tests/gui/test_menus_welcome.py`

Without recent projects, 70 % of the window is empty and the Godot line sits alone at the
bottom in green.

**Spec**
* Layout: the title and subtitle; the three `CardButton`s in a row (equal width, 160 px high);
  then **either** the recent projects (the cards of T13.08, in a grid of two columns at 1100 px
  and one below 900 px, under a `section` heading *Recent projects* with *Locate…* and
  *Remove* as `quiet` buttons at its right) **or**, when there are none, a *How it works*
  strip: three `Card`s side by side, each an icon, a number and one line (*1 Add a pack you
  own*, *2 Check what rpggen found*, *3 Generate and open in Godot*), with the user-guide link
  under them.
* The Godot status becomes a `Banner` above the bottom margin: `success` with the `check-circle`
  icon and the version and path while Godot is found; `warning` with *No Godot 4.7.2 found* and
  the two actions at its right, *Download Godot 4.7.2* (`primary`, the only primary on the
  view when it shows) and *Choose…* (`secondary`, opens the Project page's Browse). While it
  looks, `info` with *Looking for Godot…*. The object names (`welcomeGodotStatus`,
  `welcomeDownloadGodot`) stay.
* The window's title is *rpggen* on the welcome view (T15.18).

**Tests**
* With no recent projects the strip shows and the list is hidden; with one, the reverse.
* The banner's kind follows the Godot check (found, missing, looking).

**Done when**
* A first start fills the window and says what to do.

## T15.11 — Project page

**Depends on:** T15.06, T15.08
**Files:** `rpggen/gui/widgets/project_form.py`, `rpggen/gui/widgets/pack_list.py`,
`rpggen/gui/pages/project_page.py`, `tests/gui/test_project_page.py`

The drop zone takes most of the page while the three required fields sit under it; *Try with
sample pack* floats alone at the bottom.

**Spec**
* The body is two `Card`s. The first, *Asset packs*: the pack list, which when empty is a 96 px
  drop zone with the `file-archive` icon, *Drop folders or archives here* and, on the same
  line, the two `secondary` buttons *Add Zip/7z…* and *Add Folder…* (now with icons) and the
  `quiet` link *or try the sample pack* (the `sample_button`, same object name and signal);
  with packs in it, a list of pack cards that grows to 3 cards and then scrolls, with the
  buttons and *Remove* in a row under it. The dashed border stays while a drag is over the
  list.
* The second card, *Project*: the form with a fixed 140 px label column: *Output folder*
  (with Browse…), *Godot executable* (the combo, Browse…, and the version as a chip beside the
  label: `4.7.2.stable` in `success`, or the reason in `danger`), *Project name*. The hints
  under the fields become placeholder text (*Where the Godot project will be created*, *1 to
  64 characters*) and the red error lines stay under the field as today.
* `Next` is enabled and disabled as before (`validate` unchanged); `reveal_missing` marks the
  fields as before.

**Tests**
* `test_project_page.py`: the empty drop zone shows the sample link; adding a pack hides it;
  the tab order runs list → Add Zip → Add Folder → sample → Output → Browse → Godot → Browse →
  Name (`test_theme_a11y.py` names the order).

**Done when**
* The page fits at 880 × 540 with no scrolling until the third pack.

## T15.12 — Audit page

**Depends on:** T15.06, T15.04
**Files:** `rpggen/gui/pages/audit_page.py`, `rpggen/gui/widgets/asset_detail.py`,
`rpggen/gui/widgets/asset_grid.py`, `rpggen/gui/widgets/bulk_panel.py`,
`tests/gui/test_audit_cards.py`, `tests/gui/test_audit_edits.py`, `tests/gui/test_layout_fit.py`

The filter bar is three rows tall, the *Profile* button is clipped by the tab strip at 1100 px,
and the detail panel is a wall of fields.

**Spec**
* The header's slot holds the review line (*27 of 27 reviewed · 0 need attention*), its
  progress bar (200 px) and the *Review mode* button.
* **One filter row** above the grid, in a `FlowLayout` so it wraps at 880 px and is one line
  at 1100: the status chips (`Needs attention 0`, `Auto-detected 0`, `Confirmed 27`,
  `Unused 0`, `All 27`, each with its status dot), then the role combo, the pack combo, the
  search field with the `search` icon inside it, the *Group by folder* toggle as an icon
  button (`layout-grid` / `list`) with its text in the tooltip, and the *Profile* menu button
  (`settings` icon + *Profile*) at the row's right end. `Shortcuts` moves to the footer (next
  point). The tab strip (Assets, Rules, Terrain, Packs, Changes) loses its corner widget and
  can no longer clip.
* **A footer** under the grid: the queue line (*Nothing needs attention · 13 of 27 shown*) at
  the left, the key line (`C Confirm · X Exclude · 1–9 Role · N Next`) at the right in
  `caption`, and *Shortcuts* as a `quiet` button after it.
* **The detail panel** is a `Card` with four sections, each a `section` label and 8 px
  between rows: *Picture* (the preview; *Show in folder* as a `quiet` icon button on the
  path line), *What it is* (Pack, Usage, Role and the *Why* line in `caption`), *How it is
  used* (Confidence with its badge, Collision, Tileset, Tags) and *Actions*: *Confirm*
  (`primary`, `check`), *Exclude* (`secondary`, `x`) on the first line, *Edit grid…*,
  *Animations…*, *Cut objects…* (`secondary`, icons) on the second, in a `FlowLayout`.
  The audio section (waveform, loop points) and the animation transport sit in *Picture*.
* The bulk panel keeps its controls and becomes a `Banner`-shaped bar (`info`) that says
  *12 selected* with its combos and *Apply*.
* The grid: cells get a 6 px radius and a `surface` background; the status strip stays, the
  corner glyph stays (not colour-only); the folder headers of *Group by folder* use the
  `section` label and `quiet` buttons.

**Tests**
* `test_audit_cards.py` and `test_audit_edits.py` find every control by its object name as
  before; `test_layout_fit.py` at 880 × 540 shows the filter row wrapped to two lines and
  nothing clipped; the *Profile* button is fully inside the page at both sizes (a new assert).

**Done when**
* The page at 1100 px shows the filter row on one line, the full *Profile* button, and a
  detail panel with visible sections.

## T15.13 — Mapping page

**Depends on:** T15.06, T15.04
**Files:** `rpggen/gui/pages/mapping_page.py`, `rpggen/gui/widgets/sound_section.py`,
`tests/gui/test_mapping_page.py`

Each role row is 85 px tall and says *✔ assigned* nine times; the Choose and Clear buttons are
the same weight as everything else.

**Spec**
* The summary (*2 of 2 required roles assigned, 7 of 7 optional*) moves to the header's slot
  with *Undo* (`quiet`, `undo` icon) beside it.
* The sections *World*, *Characters*, *Items and UI*, *Sound* are `Card`s with the `section`
  heading; the rows inside are 48 px: the thumbnail (32 px, `base` background, radius 4), the
  role name in `text` with `*` for a required one and its hint (*Used for the starter map*) in
  `caption` under it, a 10 px status dot plus the word (`assigned`, `placeholder`, `missing`)
  in `caption` (the word stays: not colour-only), the candidate combo (stretch), and three
  icon buttons at the right: *Choose…* (`folder-open`), *Clear* (`x`, disabled when the choice
  is the automatic one), *Show in audit* (`eye`). The three are `quiet` and have their text as
  tooltip and accessible name; object names stay.
* A row whose role is missing has a `warning` left edge and a *Use a placeholder* `quiet`
  button in place of the combo's hint (what the placeholder checkbox does today, same state).
* The sound section's *Edit…* and *Add slot…* become `secondary` buttons with icons in the
  card's heading row.

**Tests**
* `test_mapping_page.py`: the row widgets keep `choose_button`, `clear_button`, `audit_button`
  and the combo; a required role without an asset shows the placeholder button; nine rows and
  the sound card fit at 1100 × 720 with at most one scroll step.

**Done when**
* At 1100 × 720 the World and Characters sections are both visible without scrolling.

## T15.14 — Options page

**Depends on:** T15.06, T15.08
**Files:** `rpggen/gui/pages/options_page.py`, `rpggen/gui/widgets/options_sections.py`,
`rpggen/gui/widgets/options_summary.py`, `tests/gui/test_options_page.py`

**Spec**
* The header's slot holds the preset bar (*Preset* combo, *Save as preset…*, *Manage…*) and
  *Reset to defaults* (`quiet`, `refresh-cw`), which leaves the feature group it floats in.
* The summary card stays at the top of the body (a `Card`).
* The feature groups (*World*, *Game systems*, *Content*, *Editor and debug*) become `Card`s in
  a **two-column grid** (`FlowLayout` of cards 440 px wide at least; one column below 920 px
  of page width). Each option keeps its checkbox, its name and its description under it in
  `caption`; an option that needs another one keeps its greyed state and its *needs …* line.
* *Starter map* / *Starter world* / *Imported maps*, *Screen*, *Layers*, *Version control*,
  *Export targets* are the same group boxes, now cards, full width, in the order of today.
* *Advanced* is a `Card` whose heading row is the collapsible header with the `chevron-right`
  / `chevron-down` icon.

**Tests**
* `test_options_page.py` finds every option by object name; the dependency greying still
  works; at 880 px the grid is one column and `test_layout_fit.py` passes.

**Done when**
* The page at 1100 × 720 shows the summary and the first two feature cards side by side.

## T15.15 — Generate page

**Depends on:** T15.06, T15.07
**Files:** `rpggen/gui/pages/generate_page.py`, `rpggen/gui/widgets/stepper.py`,
`tests/gui/test_generate_page.py`

**Spec**
* The header's slot shows the elapsed time and the estimate (*0:42 · about 40 s left*) in
  `caption`.
* The status line (*Building the game…* / *Generation failed.*) at `section` size, the step
  line under it in `text_muted`, then the progress bar with the percentage at its right in
  `caption` (the bar's own text is hidden by T15.02).
* The phase list uses the `StepDelegate` of T15.07 in its vertical form: a circle per phase
  (outlined → spinning `accent` ring for the running one → `success` check → `danger` cross
  → `text_muted` dash with *skipped* for a check that did not run), the phase name, and the
  duration at the right. The spinning ring is a 12-frame rotation; with reduce motion it is a
  still `accent` ring.
* *Show details* becomes a `quiet` toggle with the chevron icon; the log is a `Card` with the
  `LogView` inside and the *older lines* note in its footer. A failure still opens the log.
* *Cancel* sits in the window's button bar where Next is (T15.03); the page's own Cancel
  button keeps its object name and is the one the bar shows.

**Tests**
* `test_generate_page.py`: the phase rows show the right state for `on_phase`, `on_skip`, a
  failure and a cancel; the estimate line appears on the second run.

**Done when**
* A run reads as a checklist completing.

## T15.16 — Generate log: no colour-escape codes

**Depends on:** nothing
**Files:** `rpggen/core/godot.py`, `rpggen/core/godot_log.py`, `rpggen/gui/widgets/log_view.py`,
`docs/godot_api_verified.md`, `tests/unit/test_godot.py`, `tests/gui/test_generate_page.py`

The log on the Generate page shows Godot's output with its colour codes as text (`[90m[1m…`),
on screen and in `godot_<phase>.log`.

**Spec**
* `run_godot` sets `NO_COLOR=1` in the child's environment (Godot 4 honours it; verify and
  record the version in `docs/godot_api_verified.md` as the project rule asks).
* Whatever Godot still prints, `godot.py` strips ANSI escape sequences
  (`\x1b\[[0-9;?]*[ -/]*[@-~]`) from every line before `on_line`, before the log file and
  before the captured output, so the three agree and a parser never sees one. The strip is
  the guarantee; `NO_COLOR` only saves the work.
* `LogView.append_line` strips too (a belt for lines from other sources: git, 7-Zip).

**Tests**
* A fake Godot that prints a coloured line: the callback, the log file and `GodotRun.stdout`
  hold the plain text; the environment the fake received has `NO_COLOR=1`.
* `LogView` shows a plain line for a coloured one.

**Done when**
* The doc screenshot of the Generate page shows plain text.

## T15.17 — Results page

**Depends on:** T15.06, T15.08, T15.21
**Files:** `rpggen/gui/pages/results_page.py`, `tests/gui/test_generate_results.py`,
`tests/gui/test_results_m11.py`

After a failure the page is a near-empty list with *Fix: See the godot_import log* as text and
the three useful buttons at the bottom.

**Spec**
* **Success.** A `success` `Banner` (*Your project is ready*, the run id in `caption` at its
  right). Under it a hero row: the starter-map picture in a `Card` (left, 3/5) and at the right
  *Open in Godot* (`primary`, full width, 40 px), *Play* and *Open starter map* (`secondary`,
  icons) in a row, and the *What next* text. Then the counts as **stat tiles**: a row of small
  `Card`s each with the number at `title` size and its caption (`tilesets`, `animations`,
  `maps`, `warnings` …; the `count_*` object names stay). Then the grouped warnings list and
  the notes, as today.
* **Failure.** A `danger` `Banner` (*Generation failed. Nothing was delivered.* with the phase
  in its second line) and, right under it, the action row *Open failed folder*, *View logs*,
  *Export diagnostic bundle* (`secondary`, icons; same object names). Then the issue list in a
  `Card`, each row an icon, the code, the message, the fix line, and the one-click fix buttons
  of T15.21 (*Open the import log*, *Show this asset in the audit* …) **in the row**, not in a
  box under the list. Under the list a *Last lines of the log* `Card` with the `LogView`
  showing the last 30 lines of the failed phase's log (T15.21 says which file), with *Show
  more* opening the whole file.
* **Cancelled.** An `info` banner and the *Generate again* button, as today.
* The `fix_box`, `fix_label`, `group_detail` and `show_assets_button` keep their names; the
  group detail (*Show these assets*) becomes the row's expander.

**Tests**
* The success state shows one `primary`; the failure state none; the failure state shows the
  log tail of the right file and the fix buttons of the issue's code.

**Done when**
* After a failure the first screen says what failed, shows the log lines that say why, and
  offers the fix.

## T15.18 — Window title with the project and the step

**Depends on:** nothing
**Files:** `rpggen/gui/wizard.py`, `tests/gui/test_shell.py`

**Spec**
* The title is `<project name> · <n>. <page> — rpggen` on a wizard page (the project name
  from the state, or the output folder's name, or nothing before the first dot while both are
  empty), and `rpggen` on the welcome view. `_update_title` already exists; it gains the
  name and the step.
* While a run is on, the title starts with the percentage (`36 % · My game · 6. Generate —
  rpggen`), so a minimised window still says how far it is (the taskbar progress of
  `taskbar.py` stays).

**Tests**
* The title on each page, with and without a name, and during a run.

**Done when**
* Alt-Tab and the taskbar name the project and the step.

## T15.19 — Dialogs

**Depends on:** T15.02, T15.03
**Files:** `rpggen/gui/dialogs/*.py`, `rpggen/gui/widgets/grid_editor.py`,
`rpggen/gui/widgets/object_cutter.py`, `rpggen/gui/app.py` (the crash dialog)

**Spec**
* Every dialog's button box: the accepting button `primary`, the others `secondary`, at the
  bottom right, 16 px margins; a dialog that has a destructive button (Storage: *Clear* of
  *your data*) marks it `danger`.
* The conflict resolver: the three panes get a header row each (*Last generated*, *Yours*,
  *New*) with a chip for the line count that differs, a 300 px minimum per pane so the dialog
  opens at 1000 px wide at least, and the file list at the left as a `Card`.
* The regeneration preview: the tree's top-level rows get the state icons (`refresh-cw` for
  updates, `alert-triangle` for conflicts, `trash` for removals) and the backup line becomes
  an `info` banner.
* The variant dialog, the grid editor, the object cutter, the asset picker, the profile
  dialogs, the learned rules dialog, the storage dialog, About and the crash dialog: the
  stylesheet does most of it; each is opened once in both themes and anything that still
  looks stock is fixed here.
* The About dialog shows the icon of the application (`tools/make_icon.py`'s SVG) at 48 px.

**Tests**
* Each dialog opens in both themes (`qtbot`) with exactly one `primary` button.

**Done when**
* No dialog looks like a different program from the wizard.

---

# Part C — Beyond the look

## T15.20 — Regeneration that skips what did not change

**Depends on:** nothing
**Files:** `rpggen/core/orchestrator.py`, `rpggen/core/ledger.py`, `rpggen/core/promote.py`,
`rpggen/core/report.py`, `rpggen/cli.py`, `rpggen/gui/dialogs/options_dialogs.py` (the
regeneration preview), `docs/spec/03_ERROR_CODES.md` (one note code), `docs/regeneration.md`,
`tests/integration/test_regeneration.py`, `tests/perf/test_perf.py`

`perf.json`: a full generation of the 1,000-image pack takes 58 s; a regeneration of it with
nothing changed takes 59 s. The ledger already knows nothing changed (`unchanged` in
`orchestrator.py`), but it is only used to decide whether to rewrite the report.

**Spec**
* Before the `import` phase, a regeneration computes whether the run is **a repeat**: the
  packs' stamps, the config, the audit, the mapping, the options, `RECIPE_VERSION`, the runtime
  version and the Godot version are what the ledger recorded, and the project's generated
  files are what the ledger says (hashes). A repeat **skips** `import`, `build`, `validate`,
  `smoke` and `export` and goes to `promote` (which has nothing to write) and `report`; each
  skipped phase is reported with the new note code `REGEN-010` (*nothing changed since the last
  run; this check was not repeated*) through `on_skip`, so the Generate page shows the dash and
  the word, and the report's *Checks* section says so.
* A repeat is **not** a repeat when: the user edited a generated file (a conflict would be
  found), the last run failed or was cancelled, a `--full` flag (CLI) or *Run every check
  again* checkbox (the regeneration preview, off by default; remembered per project in the
  ledger) is set, or the ledger is missing or older than 1.3.0.
* `rpggen-cli generate … --json` reports the skipped phases in `skipped` with the code, as
  the schema already allows.
* The dry run says *A regeneration would skip the checks: nothing changed.*

**Tests**
* Integration: generate, regenerate unchanged → `skipped` holds the five phases with
  `REGEN-010`, the project is byte-identical; change one option → nothing is skipped; edit a
  generated file → nothing is skipped and the conflict is found; `--full` → nothing is
  skipped.
* Perf: `regeneration of 1000 images, nothing changed` asserts under 10 s (a new ceiling
  `REGENERATE_UNCHANGED_S`), and a new row `regeneration of 1000 images, full` keeps the old
  ceiling.

**Done when**
* The perf row shows the repeat under 10 s and `docs/regeneration.md` explains the rule and
  the checkbox.

## T15.21 — Failures that say what to do

**Depends on:** nothing
**Files:** `rpggen/core/godot_log.py`, `rpggen/core/orchestrator.py`, `rpggen/gui/fixes.py`,
`rpggen/gui/pages/results_page.py`, `rpggen/gui/window_menus.py`, `docs/errors.md`,
`tests/unit/test_godot_log.py`, `tests/gui/test_generate_results.py`

**Spec**
* `godot_log.first_error(text) -> GodotError | None`: the first `ERROR:` / `SCRIPT ERROR:` /
  `Parser Error` line of a Godot log with its message and, when the line names one, the
  `res://` path and line number. The orchestrator attaches it to the issue of the failed
  phase (`BUILD-001`, `BUILD-002`, `VAL-0xx`, `SMOKE-0xx`) as `detail["cause"]`,
  `detail["log"]` (the log file's name) and `detail["file"]`.
* The Results page shows the cause under the issue's message (*Godot said: Parse error at
  line 12 of res://generated/objects/house.tscn*), and the log tail card (T15.17) reads
  `detail["log"]`.
* New fixes in `fixes.py`: `open_log` (*Open the log*, for every issue with `detail["log"]`,
  opens the file in the system viewer through the existing *View logs* path),
  `show_asset` (*Show this asset in the audit*, when `detail["file"]` maps to a catalog asset
  through the ledger's asset-to-file table) and `open_failed_folder`. The registry keys stay
  codes; a second table keys on the detail present, so a fix never depends on a code that
  does not carry the detail.
* `docs/errors.md` gets the cause line in the entries of the codes above.

**Tests**
* `first_error` over the three kinds of Godot error lines and a log without one; the fix
  buttons appear for an issue with `detail["log"]` and not without; `show_asset` lands on the
  asset.

**Done when**
* The failed-run screenshot of the user guide shows a cause and a button.

## T15.22 — Try the sample in two clicks

**Depends on:** nothing
**Files:** `rpggen/gui/wizard.py`, `rpggen/gui/pages/welcome_page.py`,
`rpggen/gui/pages/generate_page.py`, `docs/user_guide.md`, `tests/gui/test_sample_pack.py`,
`tests/gui/test_wizard_flow.py`

*Try the sample* walks to the Options page and stops; a first user has to find Generate.

**Spec**
* The welcome card's click walks through to the **Generate** page (every page in between is
  entered and left as with Next, so the Options page writes its defaults) and starts the run.
  The Generate page shows an `info` banner for a sample run: *Using the default options. Back
  changes them; nothing was written yet* — with Back enabled until the run starts writing
  (`promote`), as the cancel rule already allows.
* The Project page's *Try with sample pack* (the in-wizard button) keeps walking to the
  Options page as today: a user who is already in the wizard is choosing a pack, not asking
  for a result.
* The user guide's *First run* becomes: press *Try the sample*, wait, press *Open in Godot*.

**Tests**
* `test_sample_pack.py`: from the welcome view the sample lands on the Generate page with the
  banner and the run started (the fake Godot of the tests); from the Project page it lands on
  Options as before.

**Done when**
* A first start to a playable project is two clicks and a wait.

---

# Part D — Verification, documentation and the gate

## T15.23 — Visual regression goldens

**Depends on:** T15.10 – T15.19
**Files:** `tests/gui/goldens/*.png` (new), `tests/gui/test_visual_goldens.py` (new),
`rpggen/dev.py` (`update-ui-goldens`), `tools/make_doc_screenshots.py`, `.github/workflows/ci.yml`

Every page is already rendered by the screenshot tool; nothing compares the result with what it
was.

**Spec**
* `make_doc_screenshots.render` gains `size=` and `font=` parameters; the goldens are rendered
  at 1100 × 720 and 880 × 540, both themes, with the bundled test font that
  `dev.ensure_real_font` installs, on the welcome view and the seven pages (the Generate and
  Results pages from the recorded fake run the GUI tests already use, no Godot).
* `test_visual_goldens.py` (marked `slow`) renders the same and compares each with its golden:
  the mean absolute difference over the image is under 1.5 % and no 32 × 32 block differs by
  more than 20 %; a failure writes the rendered image and a diff image beside the golden under
  `tests/gui/goldens/_failed/` and names the page, theme and size.
* `python -m rpggen.dev update-ui-goldens` rewrites them; a pull request that changes a
  golden carries the before/after in its description (the ground rule).
* CI runs the test on the Windows leg (the fonts the goldens were made with) and on Ubuntu
  with the same bundled font; a platform where the font cannot be installed skips with a
  reason.

**Tests**
* The test itself; a unit test over the comparison with a shifted image and a recoloured one.

**Done when**
* A stylesheet change that moves a button fails CI with a picture.

## T15.24 — Documentation, screenshots and changelog

**Depends on:** Parts A–C
**Files:** `docs/user_guide.md`, `docs/images/*.png`, `README.md`, `CHANGELOG.md`,
`docs/status.md`, `docs/spec/00_START_HERE.md`, `THIRD_PARTY_NOTICES.md`, `CONTRIBUTING.md`
(the design tokens and the icon rules for contributors)

**Spec**
* Every screenshot regenerated; the guide's text follows the moved controls (the audit's
  *Profile* button, the Mapping page's icon buttons, the Options page's *Reset to defaults*,
  the Results page's log tail, the two-click first run).
* `CONTRIBUTING.md` gets a *Look and feel* section: where the tokens are, how to add an icon,
  the one-primary rule, the no-inline-style rule, the golden workflow.
* `CHANGELOG.md` 1.3.0: the user-facing summary of this milestone; the runtime changelog is
  unchanged (nothing in the generated game changes).

**Done when**
* The guide's pictures match the program and the README's first picture is the new audit page.

## T15.25 — Gate (1.3.0)

**Depends on:** T15.23, T15.24

* CI green on Windows and Ubuntu, both PySide6 legs, including the visual goldens, perf (with
  the new regeneration ceiling) and the frozen smoke test on three systems (the icons and the
  template are in the bundle).
* The upgrade test of M13 repeated with the 1.3 build over a 1.0, 1.1 and 1.2 project: no
  prompt, nothing under `game/` changes, and a repeat regeneration skips its checks.
* Manual rows: both themes at 100 %, 150 % and 200 % scaling on every page and dialog; a
  300-asset audit with the one-row filter bar; the wizard with a screen reader (NVDA on
  Windows) through the seven pages; keyboard only from the welcome view to Results; reduce
  motion on and off; the French wizard (the longer strings must fit the new rows and the
  stepper).
* Then tag `v1.3.0`.

---

## Appendix — The review of 2026-10-09, item by item

| Finding | Card |
|---------|------|
| Stock Fusion look, a 60-line stylesheet, two files to keep in step | T15.01, T15.02 |
| Every button carries the same weight; Quit beside Back and Next | T15.03 |
| No icons anywhere | T15.04 |
| Ten inline styles that do not follow the theme | T15.05 |
| Pages start differently (no title, a question, a progress bar) | T15.06 |
| The sidebar is a plain list; narrow mode shows numbers only | T15.07 |
| Welcome and archetype cards look like group boxes; the sample card's split arrow reads as a scrollbar | T15.08 |
| No focus ring of its own; page changes snap | T15.09 |
| Welcome view mostly empty on a first run; the Godot line alone at the bottom | T15.10 |
| Project page: the drop zone dwarfs the form; the sample button floats | T15.11 |
| Audit: a three-row filter bar; *Profile* clipped at 1100 px; a dense detail panel | T15.12 |
| Mapping: 85 px rows, *assigned* repeated, same-weight buttons | T15.13 |
| Options: a long single column; *Reset to defaults* inside a group | T15.14 |
| Generate: a plain phase list, a 36 % bar, the log without a frame | T15.15 |
| Raw colour-escape codes in the Generate log | T15.16 |
| Results after a failure: an empty list and *see the log* as text | T15.17, T15.21 |
| The window title only ever says *rpggen* | T15.18 |
| The dialogs look like another program | T15.19 |
| A regeneration with nothing changed takes as long as a full run | T15.20 |
| *Try the sample* stops one page short | T15.22 |
| Nothing catches a stylesheet change that breaks a page | T15.23 |
