window.BENCHMARK_DATA = {
  "lastUpdate": 1791499100971,
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
      }
    ]
  }
}