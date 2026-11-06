# Colored Hero batch — 2026-11-06

17 visually labeled table regions from the existing development corpus, 34 card occurrences at original resolution, plus 0.75 and 0.5 resizing: 102 occurrences total. These are reused development examples and transformations, not 102 independent hands or a holdout accuracy estimate. Dark/folded cards are included as appearance tests; recognizing their glyphs does not establish an active hand.

Run:

```sh
python tools/hero_batch.py --assets /path/to/aistudio --output hero-batch.json
```

The runner verifies source SHA256 and limits Tesseract OpenMP threads to one unless explicitly configured otherwise. Two concurrent workers are used. Timings are concurrent laboratory timings, not Windows capture latency.

| Scale | Before: correct / wrong / abstained | After: correct / wrong / abstained |
|---|---|---|
| Original | 34 / 0 / 0 | 34 / 0 / 0 |
| 0.75 | 33 / 0 / 1 | 33 / 0 / 1 |
| 0.5 | 34 / 0 / 0 | 32 / 0 / 2 |
| Total | 101 / 0 / 1 | 99 / 0 / 3 |

Comparable baseline is `hero-batch-controlled.json`; final is `hero-batch-after.json`. `hero-batch-before.json` preserves an initial oversubscribed run with many Tesseract timeouts. Its 88 abstentions are not a valid recognition baseline, and the thread setting must not be presented as a recognition algorithm improvement.

## Shared rank correction

Board replay exposed 4 and 7 read as A after resizing. All four OCR votes used the same horizontally widened glyph (12×8), so their agreement did not resolve the distortion. `read_segmented_rank` now requires an A to agree with two undistorted (8×8) OCR observations, extending the existing protection for 4. Disagreement or blanks cause abstention; there is no replacement guessed rank.

Eight mocked contract tests pass, including a distorted A rejected when original aspect reads 7, and a genuinely agreeing A accepted. Board replay confirms both wrong A readings now abstain. Across its 23 transformed cases, including the separate board-anchor repair, results changed from 18 exact / 3 wrong / 2 abstained to 18 exact / 0 wrong / 5 abstained. Five original boards retain 17/17 correct card occurrences. Details are recorded separately by the board batch.

The conservative guard loses two Ah readings at half scale (indices 2 and 12: original-aspect OCR returns blanks). Original resolution retains all 34 correct readings. The pre-existing Kc abstention at index 15, scale 0.75 (428×753 table), is a suit-shape abstention and remains unchanged. No suit threshold was relaxed.

## Evidence limits

No colored 8 occurs among these 17 Hero regions. The reported real Hero 8h→3h incident cannot be declared fixed from this batch. A separate colored board 8h source was discovered outside the automatically accepted table set and is covered by the board audit. Small-resolution variants are robustness probes, not a newly promised minimum supported size. Future independent screenshots and Windows replay are still needed.
