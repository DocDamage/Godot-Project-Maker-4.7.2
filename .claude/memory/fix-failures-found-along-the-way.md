---
name: fix-failures-found-along-the-way
description: "In the rpggen repo the user wants every test failure I come across fixed, not only reported, including ones that are not caused by the task at hand"
metadata:
  node_type: memory
  type: feedback
  originSessionId: fdcc3568-a4b5-4b72-8a96-0fbfb38fa1e9
  modified: 2026-10-11T21:54:48.878Z
---

On 2026-10-11, while I was finishing T16.13 in the rpggen repo (`F:\Godot Project Maker`), I reported that `tests/gui/test_options_m11.py::test_the_page_uses_two_columns_only_when_wide` failed when its file ran alone, showed it also failed without my changes, and moved on. The user (DocDamage) replied: "fix that failure and fix any failures you find along the way from now on."

**Why:** earlier the same day they had asked "can we fix those 9 machine-specific failures?" about failures I had been listing as a known baseline. They want a green suite, not a list of excuses for red tests.

**How to apply:** when a test fails during work in this repo, find the cause and fix it (the code, the test's own fragility, or the environment), even when the failure predates the task or only shows in some run orders. Say what the cause was. My reading: this does not cover weakening a test to make it pass (the build manual forbids that), and a fix that needs a change to the user's machine or accounts is still theirs to make, as with the git `safe.directory` setting (see [[local-test-environment-quirks]]).
