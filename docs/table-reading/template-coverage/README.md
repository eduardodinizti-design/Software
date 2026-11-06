# Template coverage expansion

This block expands the existing OpenCV path, not the product scope. Colored cards, blue layout, passive reading and six proposals per source remain the target. OCR fallback is preserved; no gameplay actions or continuous image storage are added.

## Rank coverage

The rank atlas adds real-pixel scale variants from the same training screenshots. Its frozen source split excludes the nine evaluation screenshot hashes from construction. Thresholds remain IoU .92 and different-rank margin .12 with aspect/topology checks. Multiple variants of the same rank are grouped; they do not count as competing independent votes. A/4/3/8 retain OCR.

Shortcut coverage rises from 17 to 49 of 102 transformed Hero occurrences. On sources excluded from template construction, shortcuts rise from 6 to 16 of 60 occurrences, with no wrong accepted rank. Full Hero results remain 101 correct and one abstention, including 34/34 originals. These are reused development images, not a pristine holdout. See ../RANK_TEMPLATE_EXPANSION.md.

## Benchmark interpretation

The before implementation is the exact table_reading tree from commit 04719c19f6b33de2daa4df3c41af211728402677, verified against Git blob hashes before benchmarking. Both versions run with templates and snapshot-scoped OCR memo enabled. The benchmark uses the same synthetic tiled development crops, one OpenCV/OpenMP thread, five warm calls plus first call for each of one/three/six crops. Source loading is outside timing. No native capture is included.

Before is run before after, so order and shared-host load can bias timings. Five-sample p95 is exploratory. Comparison must preserve semantic outputs and expected Hero/board cards; construction-source matches are not independent recognition evidence.

Use the current benchmark runner with VISUALPILOT_READER_ROOT pointing to a checkout of the selected version (the baseline script predates --modes). Reproduce either implementation with `python tools/benchmark_templates.py --assets public/assets/aistudio --output benchmark.json --modes templates`. The new --modes option only selects the benchmark comparison, not production behavior.

## Incremental performance

| Different table crops | Median before → after (ms) | p95 before → after (ms) | OCR calls |
|---|---:|---:|---:|
| 1 | 528.17 → 517.72 | 586.56 → 520.75 | 4 → 4 |
| 3 | 1607.77 → 1648.51 | 1649.03 → 1724.51 | 14 → 14 |
| 6 | 4418.27 → 4029.29 | 4427.9 → 4059.22 | 39 → 35 |

All 36 calls preserved expected cards, and semantic references matched between implementations. The incremental speed gain is modest in these original-size scenes; expanded rank coverage primarily also benefits resized appearances. Do not equate shortcut coverage growth with an equal latency improvement. The 250 ms target remains unmet.

Fold and Raise are now enabled after separate-source validation using larger real exemplars without lowering thresholds. Six button masks span four construction sources; 16 replay crops preserve semantics, with ten source-disjoint shortcuts. Call amounts and Bet retain OCR. A real Bet example is labeled for future work but is not an enabled template. See ../BUTTON_TEMPLATE_FASTPATH.md.

The three-crop case was approximately 2.5% slower, with unchanged OCR calls. This small-sample run cannot separate larger-atlas overhead from shared-host/order variation. There is no claim of uniform acceleration.
