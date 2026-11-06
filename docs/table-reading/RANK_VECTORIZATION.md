# Exact rank-score vectorization

The 110 normalized atlas masks and their areas are now prepared once in `TemplateAtlas`. Each candidate mask computes all intersections in one NumPy batch. Union area uses the exact identity `template_area + candidate_area - intersection`. Selection still groups by rank, preserves first-template ties and stable rank ordering, and applies the same topology, aspect, IoU and margin checks.

No threshold, source split, template, accepted rank family or OCR fallback changed. A/4/3/8 remain OCR-only. Among the current 60 source-disjoint Hero occurrences, only three A observations (transformations of one screenshot) exist; there are no 4, 3 or 8 observations. This does not justify enabling those families. The historic missing Hero 8→3 failure remains unreproduced.

Validation:

- All 102 shortcut decisions and their reported scores match the preceding atlas-expansion report exactly (`rank-fastpath-vectorized.json` versus `rank-fastpath-expanded.json`). Counts stay 49 correct shortcuts, zero incorrect, 53 OCR fallbacks; source-disjoint shortcuts remain 16/60.
- 26 rank contract tests pass. New tests compare every rank score and geometry flag against the scalar reference for all 110 atlas masks, 32 deterministic random masks, and blank/full masks. Another test preserves the first-template geometry decision when pixel scores tie.
- Board guarded-case replay is recorded separately by `validate_guarded_ranks.py`.

This is computational refactoring with exact decision parity, not additional recognition coverage. Any latency improvement must be established by the coordinated sequential benchmark; replay time is not a Windows capture benchmark.

## Paired component measurement

A subsequent rank-only benchmark alternated baseline/current order for 20 paired repetitions over the same 102 prebuilt real crops in one process, with no OCR or other agent benchmark running. Both atlases were warmed before measurement. Results were exactly equal on every repetition.

| Implementation | Median per 102 crops | Median per crop |
|---|---:|---:|
| Scalar baseline commit 56c7009 | 205.47 ms | 2.014 ms |
| Vectorized | 115.75 ms | 1.135 ms |

The vectorized component was faster in 20/20 pairs; median paired difference was −88.97 ms per batch, approximately 44% for rank-template computation alone. Evidence and raw pairs: `rank-vectorization-paired-benchmark.json`; reproducer: `tools/benchmark_rank_vectorization.py`.

This supports retaining the local refactor, **not claiming improved integrated cycle latency**. Separate integrated six-table runs did not improve (reported 4044→4345 ms and paired isolated run 4367→4547 ms). OCR and the remainder of the pipeline dominate those workloads; these component measurements do not identify the cause of the integrated timing difference. No Windows performance guarantee follows.
