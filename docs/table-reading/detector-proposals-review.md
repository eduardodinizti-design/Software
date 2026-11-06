# Proposal suppression correction — 2026-11-06

Root cause: enclosing-first deduplication allowed a contour touching the screenshot edges to suppress every overlapping interior candidate, even though that enclosing contour must subsequently be rejected as `PARTIAL`. In `_8C143...`, the HSV masks already generated the real table's `[703,54,686,1237]` box, but the earlier `[0,0,1436,1720]` proposal suppressed it.

Change: an edge-touching proposal no longer suppresses a fully interior proposal. Existing overlapping interior candidates retain their original suppression policy. All accepted tables still need existing structural evidence, layout geometry, visibility checks and optional blocker checks. Partial proposals remain visible diagnostically. No manual reference box enters runtime.

## Evidence

- 54 unmodified corpus PNGs: complete candidates **20 → 22**, no existing complete candidate removed or relocated.
- `_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png`: recovered `[703,54,686,1237]`, four corner scores `.7967/.8872/.887/.9825`.
- `_ABCB3886-A120-479F-9F0E-43096FB2D791__aaed78f0.png`: recovered `[611,104,686,1237]`. Visual review confirms the blue table, Hero 9d/2s and Fold/Call/Raise controls.
- Nine additional interior proposals remain `UNCERTAIN`; they were not promoted merely because the enclosing partial box stopped suppressing them.
- These are candidate counts, not a fully labelled precision/recall estimate. No claim of Windows/live or multi-table load validation.
- 12 detector tests pass: four new proposal tests and the eight preceding menu/corner tests. Negatives cover explicit blocker occlusion, a table cropped to touch frame edges, and synthetic blue nested rectangles without anchors.

```
VISUALPILOT_ASSETS=/workspace/software-current-audit/public/assets/aistudio /workspace/VisualPilot/.venv/bin/python -m unittest test_detector_proposals test_detector_batch test_corner_sampling -v
/workspace/VisualPilot/.venv/bin/python tools/compare_detector_proposals.py --before /tmp/detector-proposals-before.py --assets /workspace/software-current-audit/public/assets/aistudio --output docs/table-reading/detector-proposals-results.json
```

The comparison runner accepts the previous module snapshot via `--before`; the `/tmp` snapshot is session-local. Persisted per-source before/after results are in `detector-proposals-results.json`.

This closes the proposal failure recorded in `detector-batch-review.md`; that earlier report records the preceding stage rather than current status. Downstream board/hero correctness is validated separately, not implied by table detection.
