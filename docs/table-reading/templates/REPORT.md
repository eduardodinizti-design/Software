# OpenCV template fast paths — laboratory block

The existing OCR path remains available. The default reader now tries conservative real-ink templates first, then falls back to OCR without relaxing existing ambiguity rules. Both benchmark modes retain the previous exact per-frame OCR memo.

| Different table crops | Median OCR → templates (ms) | p95 OCR → templates (ms) | OCR calls per snapshot |
|---|---:|---:|---:|
| 1 | 1056.6 → 504.28 | 1073.14 → 508.84 | 10 → 4 |
| 3 | 3702.51 → 1625.41 | 4864.21 → 1691.36 | 35 → 14 |
| 6 | 7222.59 → 4264.48 | 7258.47 → 4398.38 | 69 → 39 |

All 36 benchmark calls (30 warm measurements plus six first calls) preserved semantic outputs and expected Hero/board labels. Six-table median improves about 41%; p95 remains approximately 4.40 seconds, so the 250 ms target is NOT met.

These are sequential Linux runs on synthetic tiled development crops, with one OpenCV thread and OMP_THREAD_LIMIT=1. Image loading is outside timing. Native capture is excluded. Five-sample p95 is exploratory; baseline-first order and shared-host load can bias timings. The one-table source differs from the previous block, so compare modes within this report, not absolute timings across reports.

## What is enabled

- Rank templates: 26 masks covering all 13 ranks as competitors, with matching aspect/topology, high IoU and a margin between ranks. A/4/3/8 always retain OCR. In the expanded 102-occurrence Hero replay, 17 occurrences skip OCR; six are from different screenshot sources than the templates. Full outputs remain 101 correct, zero accepted wrong and one abstention. Different-source samples are reused development data, not pristine holdout.
- Static button templates: F/C and Check only. Fold/Raise prototypes are competitors but not accepted shortcuts; they lack source-disjoint acceptance validation. Call/Bet and variable amounts remain OCR. Twelve real crops preserve semantics, with five shortcut hits on source-disjoint crops. No action is executed.
- Board ROI geometry: bounded cache of 128 immutable crop-local rectangles keyed by current dimensions/layout/region. No stale pixels, absolute positions or card state. Bounds exactly preserve the previous region. The arithmetic was already cheap; no speedup is attributed to this cache.

## Verification and remaining scope

The rank/button contracts cover missing atlas, ambiguous matches, partial text, added amounts, disabled mode and threshold conflicts. Full laboratory regression is in regression/summary.json. The Windows workflow uses a controlled Tk window; it does not validate PPPoker live performance.

Current limits remain blue layout, colored faces and at most six table proposals per source snapshot. The exact Hero 8h→3h incident, a real turn sample and native six-table endurance remain pending. More independent labeled glyph/button examples are needed before widening shortcut coverage. Fichas and potes are not implemented by this block.

Reproduce with `python tools/benchmark_templates.py --assets public/assets/aistudio --output benchmark.json`. `template_mode(False)` in Python restores the preserved OCR path for controlled comparisons. Previous `benchmark_reader.py` explicitly disables templates to preserve its historical OCR-memo comparison.

Detailed evidence: ../RANK_TEMPLATE_FASTPATH.md, ../BUTTON_TEMPLATE_FASTPATH.md, ../roi-geometry-review.md and benchmark.json.
