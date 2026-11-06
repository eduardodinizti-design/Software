# Smaller undistorted Ace confirmation

The preceding Ace guard deliberately converted false 4→A and 7→A results into abstentions. It also abstained on two real Hero Aces resized to half width. Investigation found that their neutral glyph produced blank Tesseract output at 8×8 expansion but A at 2×2, 3×3, 4×4, 6×6 and 10×10, with both segmentation thresholds and both OCR modes. This is sensitivity to rendered glyph size, not missing rank strokes.

The change keeps the original guard. Only when BOTH original-aspect observations are blank, and the initial four distorted observations were all A, it retries at undistorted 4×4. Both threshold masks and both OCR modes must return A: four unanimous observations. A conflicting rank, one blank mixed with a rank, any blank in the retry, or an OCR failure abstains. No majority vote or suit inference was added.

Hero replay, same 17 reused colored regions and three scales:

| Run | Correct | Wrong accepted | Abstained |
|---|---:|---:|---:|
| Guard baseline (`hero-batch-after.json`) | 99 | 0 | 3 |
| Smaller retry (`hero-batch-small-aspect.json`) | 101 | 0 | 1 |

Original size remains 34/34. The two recovered observations are Ah at indices 2 and 12, half scale. Kc at index 15, scale .75 remains a suit abstention. No suit thresholds were relaxed. These are development transformations, not independent hands or deployment accuracy.

13 mocked contract tests verify unanimity, blank/conflict rejection, no retry after partial original-aspect confirmation, and exception behavior. Board replay must also retain rejection of the reduced 4/7 false-A cases; see the paired board report.

Board regression confirmed in `board-batch-next-rank.json`: 23 transformed cases remain 18 exact, zero wrong accepted, five abstentions. Both reduced false-A cases remain rejected. Thus the two recovered Hero Aces do not reopen the observed board errors.
