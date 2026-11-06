# Detector computation reuse — 2026-11-06

Pure optimizations; proposal thresholds, geometry, ordering and rejection rules remain unchanged.

- Compute full-frame HSV once in `detect_table_crops`, passing that same current-frame array to `detect_control_anchored_tables` via private `_hsv`. Direct calls without `_hsv` retain their original behavior. This internal parameter assumes a valid conversion of the accompanying RGB image and is not an external input API.
- Reuse initial contour extraction when morphology did not change the mask; recompute after morphology when needed.
- Three-element medians in control combinations use the exact middle sorted value instead of constructing NumPy arrays twice per combination.
- Convert only the four sampled corner ROIs to HSV instead of the whole resized/native table. HSV conversion is pixel-local; RGB resize still occurs before sampling in canonical mode, preserving the original interpolation.

No frame, detection, template, geometry or score cache was added. Template files are still loaded each measurement, preserving missing/invalid template handling. Texture standard deviation remains unchanged because alternate prefix-sum arithmetic would introduce floating-point differences around acceptance thresholds.

## Validation

`tools/check_detector_optimization.py` loads an independent three-module baseline package and compares entire per-source outputs, including rejected proposals and corner diagnostics.

**54/54 original PNG outputs are exactly equal**, not just accepted-table totals. Evidence is persisted in `detector-optimization-parity.json`.

```
/workspace/VisualPilot/.venv/bin/python tools/check_detector_optimization.py --baseline /tmp/detector-perf-before --assets /workspace/software-current-audit/public/assets/aistudio --output docs/table-reading/detector-optimization-parity.json
VISUALPILOT_ASSETS=/workspace/software-current-audit/public/assets/aistudio /workspace/VisualPilot/.venv/bin/python -m unittest test_detector_proposals test_detector_batch test_corner_sampling test_table_reading -q
```

**25 tests passed** in 3.246s. This test-suite duration is not a performance benchmark. No detector speedup is claimed here; serialized stage timing is delegated to the integration run to avoid concurrent measurements. Baseline files in `/tmp/detector-perf-before` are session-local; the comparison tool accepts any equivalent supplied snapshot containing the three modules and anchor template directory.

## Follow-up isolated timing

After coordinating with the rank benchmark to avoid concurrent CPU work, `tools/benchmark_detector_paired.py` ran 10 warm alternating before/after pairs in one process, with OpenCV limited to one thread and no OCR. Baseline: `/tmp/visualpilot-baseline-56c7009`; scene: the same six diverse reused development crops tiled into one synthetic frame.

- Before median: **419.12 ms**.
- After median: **397.59 ms** (**21.52 ms / 5.14% lower**).
- After was faster in **10/10 pairs**; complete outputs matched exactly every run.
- Persisted samples: `detector-paired-timing.json`.

This supports retaining the limited optimization, but does **not** establish an integrated end-to-end speedup: the separate integrated alternating run measured detector medians approximately 448→450 ms and overall runtime regressed. Report those different scopes honestly. No live Windows or six-independent-table capacity conclusion follows from this synthetic detector-only benchmark.
