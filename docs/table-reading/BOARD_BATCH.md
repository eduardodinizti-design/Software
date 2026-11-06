# Board laboratory batch

Six reused, manually labeled development images of the colored-face blue layout. These are not independent holdout data, Windows capture tests, or evidence for other layouts.

## Results

The same 23 transformed cases from five images were run before and after the changes. Twenty cases are complete boards at widths 575/702/835 or brightness 70%; three replace a river card with felt.

| Outcome | Before | After |
|---|---:|---:|
| Exact accepted board | 18 | 18 |
| Incorrect accepted board | 3 | 0 |
| Abstention | 2 | 5 |

Fixed a structural error: hiding the first river card left four contiguous cards which were wrongly accepted as TURN. The calibrated layout starts its first community card around 20% of table width. A row starting beyond 25% is now rejected with `BOARD_PARTIAL_OR_OBSTRUCTED` and `FIRST_CARD_ANCHOR_MISSING`. This deliberately assumes this layout. A fully hidden trailing card cannot reliably be distinguished from a genuine earlier street using this single frame alone.

Two rank errors were caught in the batch: 4h became Ah at width 575; 7d became Ad at width 702. The shared segmented-rank change now requires the original-aspect OCR confirmation for A, as already required for 4. Both become abstentions rather than accepted wrong cards. Exact recognition of these two degraded crops remains open.

The five original crops still match all 17 community-card occurrences. A sixth manually cropped source (`_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png`) gives 2s/8h/5h correctly at widths 575/703/835: three transformed cases of one hand, not three new hands. Its table detector was bypassed explicitly.

Fifteen board unit tests pass, including missing-first-one/two-card rejection before OCR. No saved images or click actions added.

## Reproduction

Set `VISUALPILOT_ASSETS` to the local source-image directory. These scripts set `OMP_THREAD_LIMIT=1` by default: parallel Tesseract runs without the cap produced timeouts on this host. Reported per-case times are concurrent laboratory measurements, not Windows latency claims.

```sh
python -m unittest test_community_cards -q
python tools/board_batch_evaluation.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/board-batch-after.json
python tools/board_batch_eight.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/board-batch-eight.json
OMP_THREAD_LIMIT=1 python tools/evaluate_colored_boards.py --assets "$VISUALPILOT_ASSETS"
```

`board-batch-before.json` preserves the pre-fix results. `board-batch-after.json` contains the structural fix plus shared rank-A confirmation. Scripts return nonzero on incorrect accepted boards (batch) or a mismatched additional eight-board case.
