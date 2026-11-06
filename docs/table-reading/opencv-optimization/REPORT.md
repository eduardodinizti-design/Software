# OpenCV computation experiment

Candidate changes: share current-frame HSV/contours, use exact three-element medians, and batch rank-template intersections. No thresholds, labels, accepted families or cross-frame cache were changed. Baseline: verified table_reading tree from 56c7009f73686ccc25f272bfdcc29b25a7bbee89.

## End-to-end results

| Diverse tiled crops | Sequential median before → candidate (ms) |
|---|---:|
| 1 | 501.28 → 516.66 |
| 3 | 1609.07 → 1982.01 |
| 6 | 4044.47 → 4345.17 |

A follow-up alternated isolated before/after processes without concurrent OCR. Six-table median was 4366.54 → 4546.87 ms; exploratory p95 was 4729.25 → 4969.88 ms. Therefore no end-to-end acceleration was demonstrated. Variability affects unchanged OCR stages too. Five warm samples per mode cannot establish production tail latency or attribute the entire difference causally.

All paired semantic outputs and expected cards matched. These are reused development sources tiled into synthetic scenes, not live independent tables. Native Windows capture is excluded. Both versions used OMP_THREAD_LIMIT=1 and one OpenCV thread.

## Correctness evidence

- Entire detector output unchanged on 54/54 original PNGs, including rejected regions and scores.
- Rank decisions and scores unchanged on 102 transformed occurrences: 49 shortcuts, 0 wrong, 53 OCR fallbacks.
- Independent board replay: 23/23 previous outputs exactly preserved plus 3 positive-eight cases; total 21 correct, 0 wrong, 5 abstained. Known 4/7→A mistakes remain rejected.
- A/4/3/8 stay on OCR: available source-disjoint Hero material is insufficient to authorize a wider shortcut. The missing exact Hero 8h→3h case remains unresolved.

Separate component-only timing is required to decide whether the computation changes are worth retaining; it must not be described as an end-to-end speedup. See the final decision below.

## Final decision

Retain the limited computation changes for demonstrated local benefits, without claiming end-to-end acceleration. A separate same-process benchmark alternated the scalar/vectorized rank implementations over the same 102 crops for 20 pairs, without OCR: median 205.47 → 115.75 ms per batch (about 44% lower), all 20 pairs faster and exact outputs. Per crop this is about 2.014 → 1.135 ms, not a complete card-reading time.

A serialized detector-only benchmark alternated ten pairs on the same six-crop synthetic scene, one OpenCV thread, no OCR: median 419.12 → 397.59 ms (about 5% lower), all ten pairs faster and exact full proposals. These experiments ran separately to avoid planned concurrent load. See ../rank-vectorization-paired-benchmark.json and ../detector-paired-timing.json.

The local savings are small relative to several seconds of OCR work, explaining why overall acceleration is not established. Native capture is excluded from every latency figure here. The 250 ms target remains unmet; widening protected-rank shortcuts still requires additional independent real examples. No new reading capability, gameplay action or cross-frame cache is introduced.

Integrated correctness regression is recorded in regression/summary.json. Windows CI uses a controlled Tk capture window rather than live PPPoker.
