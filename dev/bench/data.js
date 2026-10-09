window.BENCHMARK_DATA = {
  "lastUpdate": 1791587017147,
  "repoUrl": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2",
  "entries": {
    "rpggen performance": [
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "dead707d5cbec932b8d2660a08d78ec5de86e0c1",
          "message": "CI: a perf branch step that keeps the checkout; room for a slow cancel run\n\n- The gh-pages step makes its empty commit with git mktree/commit-tree and\n  pushes it, without switching branches (\"git checkout -\" had no previous\n  branch to go back to; the branch now exists).\n- test_cancel_during_analysis... waits up to 60 s for the whole run on a\n  busy runner (the Windows job ran 4x slower than locally); the check that\n  matters, the stop within 2 s of the cancel, is unchanged.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T18:31:29-04:00",
          "tree_id": "2af3a63737d1f93e588ef48030ef9d4a923965af",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/dead707d5cbec932b8d2660a08d78ec5de86e0c1"
        },
        "date": 1791499097784,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 17.39,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 2.18,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 106.52,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 104.35,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 14.94,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 15.4,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 8.2,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 9.32,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "8d7967af077742857fd23fcae76ba3a1343157fd",
          "message": "T12.56: languages: in-game picker and wizard translations\n\nGame:\n- Settings > Language lists System and the locales of generated/i18n\n  (RpgStrings.locales()); RpgSettings.language is saved in settings.cfg and\n  applied with TranslationServer.set_locale. The settings menu redoes the\n  texts it sets in code when the language changes; the title and battle\n  hints follow NOTIFICATION_TRANSLATION_CHANGED. Missing keys stay English.\n- The settings scene gets a Language row (ui_recipes RECIPE_VERSION 10); the\n  generated README explains adding a column to game/i18n/strings.tsv.\n\nWizard:\n- rpggen/gui/translations.py installs a QTranslator (and Qt's qtbase one)\n  for the saved language or the system's UI language, before any widget is\n  made; View > Language saves the choice for the next start.\n- tools/update_translations.py: extract (pyside6-lupdate) and release\n  (pyside6-lrelease). Packaging builds and bundles the .qm files; they are\n  not committed.\n- French pilot: step names, navigation, menus and the welcome view (83 of\n  578 texts); CONTRIBUTING documents the process. Error messages stay\n  English.\n- Page names are marked with QT_TRANSLATE_NOOP so lupdate finds them; the\n  GUI test session pins English.\n\nAlso fixes a typed-array assignment in the T12.55 GDScript test.\n\nPython suite 1372 passed; GDScript tests 459 passed; basic16 generation and\nsmoke pass with Godot 4.7.2.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T20:32:36-04:00",
          "tree_id": "722a85679aab182ea681e338f48e9a5f683e207f",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/8d7967af077742857fd23fcae76ba3a1343157fd"
        },
        "date": 1791506803106,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 12.96,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 1.26,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 96.05,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 84.68,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 13.75,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 9,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 4.69,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 4.37,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "a0539eaece7c8a86710cdfd6fbead342911f8d39",
          "message": "GDScript tests: a script error fails its test; fix the tests that hid one\n\n- run_tests.gd installs a Logger: a SCRIPT ERROR logged while a test runs\n  fails that test (it used to abort the function and count as passed). A\n  test that awaits is waited for (20 s), and deferred calls it queued run\n  before it is judged. A \"godot:\" summary of the errors Godot logged is\n  printed on every run; rpggen.dev godot-test shows it.\n- Tests fixed so they run to the end with their checks: the lock, party and\n  quest tests load the English strings their notes format; t.near takes a\n  message; the party battle helper uses a typed enemy list; the inventory\n  test builds the real menu scene; tests that call _ready by hand no longer\n  ready a node twice; the interaction-prompt test types its event list.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T20:47:52-04:00",
          "tree_id": "e3d9e8f7e94759801d24a6ce4ab7bef355ca959d",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/a0539eaece7c8a86710cdfd6fbead342911f8d39"
        },
        "date": 1791507162706,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 9.86,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 0.64,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 72.97,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 57.72,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 9.15,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 7.31,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 2.51,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 2.2,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "84f239bc9ec9280dea96101829954dea82fe41cc",
          "message": "Fix the batch's integration failures\n\n- The dialogue data scripts are @tool: the dialogue dock read placeholder\n  instances and crashed the editor of any project with dialogue; the dock\n  frees its scratch state.\n- RpgStrings.format: toasts fall back to English when untranslated.\n- Minimap: hidden between scenes (a script error during map changes); the\n  recipe hashes maps without Godot's per-save ids (deterministic builds,\n  no-op regenerations); the key is the project path, so the runtime holds\n  no res://game/ path.\n- The example custom recipe gets a fixed .uid, and custom-recipe build\n  steps continue the standard count.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T23:02:12-04:00",
          "tree_id": "e20d434401ae2c176681beb6a20e7b34843e8401",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/84f239bc9ec9280dea96101829954dea82fe41cc"
        },
        "date": 1791515325207,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 10.94,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 1.25,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 107.14,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 77.93,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 8.85,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 7.54,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 4.73,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 4.44,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "99c486afc063630d997854b0e9a03f8e2fff4623",
          "message": "Docs: what is done and what is left for 1.0\n\n- docs/status.md: every milestone's status, M12 card by card, and what\n  is left before v1.0.0 (by what a program and only a person can do),\n  with the known limits of 1.0; linked from the README and START_HERE.\n- M12 index gets a Status column; 00_START_HERE lists M11 and M12.\n- User guide: version control and pack art, skipped checks,\n  --tile-size, the conflicts command, a map of the game features.\n- Generated README: equipment and shops, quests, light, the dialogue\n  tab, the party; the archetype part is numbered after the sections it\n  follows; the Assets dock is no longer \"a later update\".\n- Runtime README: equipment, shops, quests, gates, light, minimap.\n- Root CHANGELOG: everything M12 added.\n- coverage.md: a form feed had eaten part of a Windows path.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T23:16:05-04:00",
          "tree_id": "0ac33385996aea9159dab4bed11b86dac4cb974d",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/99c486afc063630d997854b0e9a03f8e2fff4623"
        },
        "date": 1791516189663,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 9.08,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 1.27,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 107.47,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 94.44,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 11.34,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 9.07,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 4.9,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 4.49,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "9726d0ed771caf6d9dfff5d78f230c4836c52b67",
          "message": "Plan M13: twenty improvements and the Metroidvania archetype before 1.0\n\nAdds docs/spec/M13_polish_and_metroidvania.md with 31 task cards: ten wizard\nUX cards, seven feature improvements, three feature additions, nine cards for\na side-view Metroidvania archetype, the documentation card and the M13 gate.\nT12.66 (the 1.0 gate) now depends on T13.31. The start page, status page and\nCONTRIBUTING reference the new milestone; each known 1.0 limit names the\nM13 card that removes it.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T23:34:19-04:00",
          "tree_id": "6478683aa00bf369f7af160db2de0541691945a9",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/9726d0ed771caf6d9dfff5d78f230c4836c52b67"
        },
        "date": 1791517193222,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 8.79,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 0.79,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 106.12,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 80.09,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 9.98,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 10.59,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 3.59,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 3.34,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "399f9f4b3121b942c0f0609d5001b727faafc139",
          "message": "Plan: 1.0 ships from M12; M13 (1.1.0) polish and M14 (1.2.0) Metroidvania\n\nSplits the M13 plan in two and moves both after the 1.0 tag, under a\npost-release compatibility contract (no prompt on regeneration, optional\nsave keys, path shims for moved runtime scripts). M13 keeps the twenty\nimprovements plus a shared lock-and-key planner; the connected-maps world\nplan is stored in the project and reused on regeneration, VAL-027/028 are\nwarnings, audio decoding goes through soundfile, taskbar progress is\noptional. M14 holds the Metroidvania: side-view TileSet layers only for\nthat archetype, side-view NPCs, objects and a single camera, a stored room\nplan, a second side-view CC0 sample pack, binding rows, a perf ceiling and\nCI split per archetype. T12.66 no longer depends on M13.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T23:50:44-04:00",
          "tree_id": "9c8ed798b13c02047ed159df0ecc6038ae20e551",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/399f9f4b3121b942c0f0609d5001b727faafc139"
        },
        "date": 1791518190513,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 10.27,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 1.27,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 99.88,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 92.56,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 10.4,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 8.65,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 4.91,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 4.52,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "558df8ac88b218e22c8a2425155e57d6f19afee8",
          "message": "Plan T13.24: world repair, generated maps mend their doors and reachability\n\nAdds a card to M13: a map graph shared by the validator and the repair\ntool, three additive repairs (retarget a dangling door, create a missing\nspawn and return door, join an unreachable map to its nearest neighbour),\nrun by itself after a build on maps whose stored hash is unchanged, with a\nbackup that Restore previous undoes, offered as a one-click fix for edited\nmaps and as an undoable Fix in the dock. M14 reuses it for room exits.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>",
          "timestamp": "2026-10-08T23:55:08-04:00",
          "tree_id": "5a84c0f18e1b5010aeed04cf1bb4c756006d1474",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/558df8ac88b218e22c8a2425155e57d6f19afee8"
        },
        "date": 1791518529062,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 11.07,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 1.28,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 103.45,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 89.85,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 22.07,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 13.32,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 5.7,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 5.11,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "initial upload",
            "username": "DocDamage"
          },
          "distinct": true,
          "id": "446b9f6c4420c26499b6211e915f41e8f6aef32e",
          "message": "Smoke: sequence_plays puts its test trigger where nothing else is\n\nOn a planned map the start is below the first house's door; the trigger\nlanded on the door and the generation failed its smoke test.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-09T02:00:35-04:00",
          "tree_id": "05a0bd142f508e8d9491d03b088882c8abe1d8f5",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/446b9f6c4420c26499b6211e915f41e8f6aef32e"
        },
        "date": 1791526354489,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 7.84,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 0.63,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 96.82,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 67.29,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 8.42,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 7.71,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 3.55,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 2.53,
            "unit": "s"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "email": "dsferraro@gmail.com",
            "name": "DocDamage",
            "username": "DocDamage"
          },
          "committer": {
            "email": "dsferraro@gmail.com",
            "name": "DocDamage",
            "username": "DocDamage"
          },
          "distinct": false,
          "id": "433c96e2406b708dce2412f9c5ce1ab0afd62039",
          "message": "Merge main into m14\n\nmain's two commits (the screenshot test's four pictures, the smoke step's free\nspot) were already on m14 in a later form; only the note about the smoke fix is new.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
          "timestamp": "2026-10-09T18:39:26-04:00",
          "tree_id": "0eda9a6cedd9db5e4c3acd7124c640ee53211921",
          "url": "https://github.com/DocDamage/Godot-Project-Maker-4.7.2/commit/433c96e2406b708dce2412f9c5ce1ab0afd62039"
        },
        "date": 1791587014576,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "analysis of 1000 images, cold",
            "value": 6.97,
            "unit": "s"
          },
          {
            "name": "analysis of 1000 images, warm",
            "value": 0.6,
            "unit": "s"
          },
          {
            "name": "full generation of 1000 images",
            "value": 69.6,
            "unit": "s"
          },
          {
            "name": "regeneration of 1000 images, nothing changed",
            "value": 58.89,
            "unit": "s"
          },
          {
            "name": "cold analysis, serial",
            "value": 7.19,
            "unit": "s"
          },
          {
            "name": "cold analysis, parallel",
            "value": 5.8,
            "unit": "s"
          },
          {
            "name": "image analysis, serial",
            "value": 2.75,
            "unit": "s"
          },
          {
            "name": "image analysis, parallel",
            "value": 2.53,
            "unit": "s"
          },
          {
            "name": "metroidvania from the side-view sample",
            "value": 32.06,
            "unit": "s"
          }
        ]
      }
    ]
  }
}