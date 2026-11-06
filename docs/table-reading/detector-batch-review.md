# Detector batch — 2026-11-06

## Change and causal evidence

Two labelled development crops contain a thin green window-title line at the top of the menu ROI. Normalizing the entire foreground mask combines that line with the hamburger menu and drops menu IoU to approximately 0.14. Extract one unambiguous group of three aligned horizontal bars before shape comparison. Width, spacing, alignment and density constraints apply; four corner anchors must still independently pass 0.65 in one measurement. No corner score cherry-picking or threshold reduction.

Synthetic mask tests cover title contamination, missing bar, occluding badge, ambiguous groups and misalignment. Existing missing-corner and uniform-blue negatives still pass.

## Batch evidence

Command:

```
VISUALPILOT_ASSETS=/workspace/software-current-audit/public/assets/aistudio /workspace/VisualPilot/.venv/bin/python -m unittest test_detector_batch test_corner_sampling -v
/workspace/VisualPilot/.venv/bin/python scripts/detector_batch.py --assets /workspace/software-current-audit/public/assets/aistudio --output docs/table-reading/detector-batch-results.json
```

- Eight tests pass.
- 8 real labelled table crops × 3 scales, with action controls artificially removed: accepted 15/24 → 21/24. These are **synthetic transformations**, not 24 independent real captures. No earlier pass lost.
- Three residual transformed failures belong to one crop whose menu is actually covered by an MTT badge; retaining rejection is correct.
- 54 unmodified real PNGs inspected by automatic detector: complete proposals 19 → 20. No previous complete proposal lost. This inventory is **not a precision/recall estimate**; all negative regions have not been independently annotated.
- Sole new full-frame acceptance: `_174B754B-2F65-41F4-8789-48F36C88B430__2ed2f963.png`, box `[699,52,699,1244]`. Visual review confirms a blue table with seats, four corner icons, no hero cards and no action controls. This demonstrates recovery without requiring a player's turn.
- All other raw proposals retain their classifications, including rejected regions. This does not prove lobby rejection for every lobby design.

## Remaining failure and limits

`_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png`: annotated manual box `[703,54,703,1237]` passes the four anchors (1.0, .9644, .9973, .9976), but automatic segmentation produces only `[0,0,1436,1720]`, rejected `PARTIAL/TOUCHES_FRAME_EDGE`. This is a proposal segmentation failure, not a card-reading failure. Manual extraction must not count as automatic success.

The specific recent spectator screenshots supplied only inline by the user are not available as original pixels here. No claim of repairing those exact captures, Windows/live capture validation, or six-table performance. No image saving introduced in the observer. No new captures requested.
