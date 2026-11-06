# Independent guarded-rank regression

The vectorized glyph scorer preserves **all 23 board results exactly**, including candidate rectangles, rank/suit evidence, scores, accepted cards and rejection statuses. A separate positive eight-board replay matches `2s/8h/5h` at widths 575, 703 and 835.

Overall: **26 transformed calls, 21 exact boards, zero accepted wrong boards, five abstentions**. These are transformations of six reused real source images, not 26 independent hands.

The two earlier false-acceptance cases remain rejected:

- River resized to width 575: the four-of-hearts glyph previously misread as Ah is still an abstention (`2:width-575`). Its source is excluded from the glyph atlas.
- Flop resized to width 702: the seven-of-diamonds glyph previously misread as Ad is still an abstention (`4:width-702`). Its source is excluded from the glyph atlas.

Three additional abstentions are deliberate card-occlusion transformations. The positive eight source contributed to the glyph atlas and **is not source-disjoint evidence**; this check only establishes stability. The protected set remains **A, 4, 3, 8**, all routed to OCR. No protected rank was newly enabled.

`tools/validate_guarded_ranks.py` verifies input hashes, records the reference-report hash and atlas source split, and fails on any accepted wrong board, exact-result divergence, positive-eight regression or changed protected-rank set. It compares against `board-expanded-atlas-regression.json`; current output is `guarded-ranks-validation.json`.

```sh
OMP_THREAD_LIMIT=1 python tools/validate_guarded_ranks.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/guarded-ranks-validation.json
```

The detector is bypassed with documented table crops. Parallel OCR execution is used only for regression throughput; no latency or Windows-capture claim is made.
