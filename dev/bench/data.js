window.BENCHMARK_DATA = {
  "lastUpdate": 1791507165067,
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
      }
    ]
  }
}