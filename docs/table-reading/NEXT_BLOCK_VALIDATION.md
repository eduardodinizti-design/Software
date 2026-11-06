# Independent pipeline validation

Seven calls through `analyze_tables(..., read_community=True)` with the real detector, hero reader and board reader. No detector mocks, proposed boxes or cropped input in the current implementation run. Two reused development images; not seven independent hands or Windows capture tests. Metadata is explicitly synthetic.

Before comparison uses the detector source saved at `/tmp/detector-proposals-before.py`, loaded in memory under its package to preserve relative imports. Both comparisons use the current rank reader. Detector hashes are recorded in the JSON reports, so this comparison isolates the detector correction, not the rank correction.

| Case | Previous detector | Current detector |
|---|---|---|
| Full source 8C143…, board 2s/8h/5h | FAIL: no accepted board | PASS |
| Existing Jc/5d/3c full source | PASS | PASS |
| Same source with hero face area erased | PASS: board retained, target hero absent | PASS |
| Same source with board erased | PASS: no accepted board | PASS |
| Same source with middle board card erased | PASS: no accepted board | PASS |
| Original source restored after negatives | PASS | PASS |
| Black frame | PASS: no accepted board | PASS |

Total: **6/7 before, 7/7 after**. All observations keep actions disabled.

The automatically detected 8C143 crop is `[703,54,686,1237]`; its board is correctly read as `2s/8h/5h`, despite differing from the previous manually supplied width 703. This closes the detector-to-board integration gap for that development example.

The spectator, empty, partial and black cases are deliberately transformed images, not claims of real spectator-session validation. The spectator source contains another table: the absent-hero check applies to the table with the expected board, so valid cards on the other table are not mislabeled as a failure.

The new rank-A confirmation retry was independently replayed against the earlier 23 board transformations: **18 exact, zero accepted wrong, five abstentions**, unchanged. The two degraded rank cases still abstain safely.

```sh
python tools/validate_next_block.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/next-block-after.json
python tools/board_batch_evaluation.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/board-batch-next-rank.json
```

The integrated runner sets `OMP_THREAD_LIMIT=1` unless explicitly configured, records source hashes, and exits nonzero on an expectation failure. JSON artifacts contain the full pipeline outputs; no image files are written.

Additional standalone full-pipeline validation: `_ABCB3886-A120-479F-9F0E-43096FB2D791__aaed78f0.png` automatically yields `[611,104,686,1237]`, Hero **9d/2s**, and no accepted board. No crop annotation was supplied. Evidence: `next-block-second-source.json`. This is an eighth pipeline call on a third development source, separate from the seven-case before/after table above.
