# Rank atlas expansion within the frozen source split

The atlas now includes 84 additional glyph masks extracted after resizing the existing seven Hero training screenshots to 0.5, 0.75 and 1.25 of their original table dimensions, then applying the same canonical crop and segmentation. These are transformations of real labeled pixels, not independent examples. No evaluation screenshot was added. The original board-eight competitor source remains unchanged.

The atlas contains 110 masks across 13 ranks. Acceptance thresholds are unchanged (IoU .92, different-rank margin .12, topology and aspect checks). A/4/3/8 still always use OCR. The comparison groups all template variants by rank, so duplicating a template does not create extra votes or defeat the margin.

`source_split.json` freezes the eight training screenshot hashes (seven Hero plus one board) and nine evaluation screenshot hashes. The latter contain ten Hero regions, because two regions share one source image. The rebuild script and unit tests reject training/evaluation overlap. This is source-disjoint development evaluation, not a pristine holdout or proof of independent hands.

| Shortcut-only group | Before: correct / wrong / fallback | After: correct / wrong / fallback |
|---|---|---|
| Training-source occurrences | 11 / 0 / 31 | 33 / 0 / 9 |
| Source-disjoint occurrences | 6 / 0 / 54 | 16 / 0 / 44 |
| All 102 occurrences | 17 / 0 / 85 | 49 / 0 / 53 |

Evidence: `rank-fastpath-acceptance.json` before; `rank-fastpath-expanded.json` after. Training matches are not counted as independent validation.

Full Hero replay preserves exactly all previous outputs: 101 correct, zero wrong accepted, one suit abstention; original size remains 34/34. The result is recorded in `hero-batch-expanded-atlas.json`. The remaining 53 rank occurrences retain OCR fallback. No latency claim is made from concurrent replay timings.

24 rank contract tests pass (13 existing, 11 template contracts), including frozen source split and duplicate-variant invariance of different-rank margin. Board regression is reported separately and must remain free of accepted errors before release.
