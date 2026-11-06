# Second consolidated laboratory block — 2026-11-06

## Changes and evidence

- Fixed enclosing-contour suppression: a rejected frame-edge contour no longer hides an interior table proposal. Structural checks, four-corner thresholds and blocker rejection remain required. Across the same 54 source PNGs, complete proposals increased from 20 to 22; no previous complete proposal disappeared or moved. Nine additional interior proposals remain uncertain.
- The previously missed colored board **2s/8h/5h** now passes the full detection-to-reading pipeline from the original image, without a manually supplied crop. The second recovered source reads Hero **9d/2s** correctly.
- Added a smaller, undistorted Ace retry only when both original-aspect confirmations are blank. All four new observations across both masks and OCR modes must agree. Hero development replay improves from 99/102 to 101/102 correct, with one abstention and zero wrong accepted cards. Original-size results remain 34/34.
- The 23-case transformed-board regression remains 18 exact, zero wrong accepted and five abstentions; the observed false 4/7→A readings remain blocked.
- Seven integrated pipeline scenarios now pass (previously six): original sources, artificial absent-Hero, empty and partial boards, recovery and black frame. Derived scenarios are not new real hands or Windows tests.
- Snapshot metadata now names the passive reading scope and lists enabled Hero/button/board readers instead of claiming Hero-only scope.

## Validation and CI repair

The previous Windows workflow failed three storage tests because their output directories made the shared quota scan the entire runner temporary directory. The tests now create isolated diagnostics/leitura children under their own temporary roots, matching the production directory structure. Storage limits were not increased or disabled. The previous native controlled-window capture test itself passed.

The integrated Linux contract run has 103 tests: 102 passed and the native Windows test skipped. Nine real-OCR replay jobs are recorded in regression/summary.json. Run them with:

```
python tools/run_lab_batch.py --assets public/assets/aistudio
```

The Windows workflow includes the new detector tests. Its native test uses our controlled Tk window, not PPPoker; consult the workflow result for the published commit.

## Limits and next real session

These are reused development sources and synthetic transformations, not independent production accuracy estimates. No live capture speedup, six-table load or automatic account tracking is claimed. The remaining Kc reduced-suit abstention is retained. The user's exact Hero 8h→3h remains unresolved without its original source; successful board8h reading does not resolve it. A real turn sample is still missing.

The next grouped session remains the existing [Windows checklist](../batch/WINDOWS_ONCE.md): normal working sizes; Hero and flop/turn/river; action labels and preselection; spectator/no-action; move/minimize/restore. Save only discrepancies. Six-table load/GDI endurance follows single-table validation. No continuous image storage was added.
