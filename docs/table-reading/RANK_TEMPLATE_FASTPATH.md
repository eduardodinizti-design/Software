# Conservative real-glyph rank shortcut

`rank_templates.py` compares segmented neutral glyphs with 26 small masks (two threshold variants for each of 13 ranks), extracted from real labeled colored development captures. Original proportions are preserved on a 48×64 canvas. No synthetic font or guessed label is used. The manifest stores source hash, crop coordinates, label basis and asset checksum. Total package size is small; only cropped glyphs are distributed, not full screenshots.

Acceptance requires both thresholds to select the same rank, IoU at least .92, a .12 margin over the best different rank, matching hole count, aspect ratio within 12%, and matching one/two-component topology. A, 4, 3 and 8 are competitors but never shortcut OCR because their known confusions warrant more independent coverage. Missing/corrupt/incomplete assets, ambiguity and blanks delegate to the existing OCR reader. `template_mode(False)` restores the previous path.

## Evidence

The 17-region Hero development batch has 34 original card occurrences plus two resized variants each, for 102 transformed occurrences. It is not 102 independent hands.

| Shortcut-only group | Correct accepted | Wrong accepted | OCR fallback |
|---|---:|---:|---:|
| Training-source occurrences | 11 | 0 | 31 |
| Source-disjoint occurrences | 6 | 0 | 54 |
| All | 17 | 0 | 85 |

Training-source self matches establish integration only and are not recognition validation. Source-disjoint means different screenshot hashes, not necessarily different hands or unrelated sessions. All sources are previously inspected development material; this is not a pristine holdout. The real colored board-eight screenshot supplies a competitor template and must no longer be counted as holdout.

Full Hero pipeline replay (`hero-batch-template-fastpath.json`) retains exactly the previous card outputs: **101 correct, zero wrong accepted, one suit abstention**, including **34/34 originals**. `rank-fastpath-acceptance.json` records every direct shortcut decision. The remaining 85 rank occurrences deliberately use OCR, so this change is a partial reduction of OCR work and not a claim of OCR elimination.

22 rank contract tests pass: 13 existing plus nine shortcut safety contracts. They test missing/corrupt atlas fallback, blank input, identical competing templates, disagreement between thresholds, component constraints, disabled mode and OCR bypass only on an accepted candidate. Unit template self-match checks are explicitly not included in the accuracy evidence.

Rebuild assets with `tools/build_rank_templates.py --assets /path/to/aistudio`; evaluate shortcut acceptance with `tools/evaluate_rank_fastpath.py --assets /path/to/aistudio --output report.json`. Full pipeline and board regressions are separate. Latency must be measured sequentially with comparable frames; these development replay timings are not a benchmark or Windows homologation.
