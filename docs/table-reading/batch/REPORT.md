# Consolidated laboratory batch — 2026-11-06

Passive colored-face reader; no PPPoker session required. This batch integrates corpus audit, detector correction, shared rank confirmation, board integrity, preselection semantics and a repeatable regression command.

| Evidence | Before | After |
|---|---:|---:|
| Board transformed cases: exact / incorrect / abstained | 18 / 3 / 2 | 18 / 0 / 5 |
| Hero original card occurrences | 34 correct, 0 wrong | 34 correct, 0 wrong |
| Hero including resizes: correct / incorrect / abstained | 101 / 0 / 1 | 99 / 0 / 3 |
| No-control corner probes accepted (24 transformations) | 15 | 21 |
| Complete proposals across 54 source PNGs | 19 | 20 |
| Parsed actions exposed in known preselection rows | 5 | 0 |

The three eliminated board errors now abstain, not magically become correct. The rank-A confirmation preserves glyph aspect ratio and rejects distorted false A votes. Its cost is two additional Hero abstentions at half resolution. A missing first board card can no longer turn the remaining river suffix into a claimed turn. A fully hidden trailing card still cannot be distinguished reliably from an earlier street in a single frame.

The menu detector isolates three bars from title-line contamination while preserving four-corner validation and thresholds. No previous accepted source proposal was lost. These counts do not establish general lobby-classification precision or recall.

A row containing F/C now marks all its parsed labels as preselection. Original labels/amounts remain inspectable, but action fields are cleared. This is not confirmation of the player's turn and does not enable clicks.

## Corpus and coverage

The audit counted 854 image paths, 302 distinct hashes and 552 duplicate copies. The 54 distinct aistudio screenshots were visually triaged; 24 show tables. Sixteen screenshots have linked labels; 38 lack linked labels. Thirty-nine distinct contents are explicitly synthetic. See ../BATCH_CORPUS.md and JSON for provenance.

A real colored 8h board previously missed by the detector-dependent search was found: 2s/8h/5h. It reads correctly in three resized manual crops. Its automatic full-frame proposal still fails; this is not an end-to-end success. The user's separate Hero 8h→3h incident remains unresolved without its original PNG. No real turn was located in the bounded 54-image search; existing turn tests use transformed river images.

All image accuracy counts use reused development material. Resizes are not independent hands. No new Windows capture latency or operational six-table capacity is claimed.

## Validation and reproduction

Run `python tools/run_lab_batch.py --assets public/assets/aistudio` from the repository root. The command runs contracts and eight replay jobs, records logs/JSON, caps laboratory Tesseract threads and exits nonzero on failed gates. Original Hero omissions and accepted wrong extended Hero/board reads fail validation. Degraded-image abstentions remain explicitly reported.

The integrated contract suite has 94 tests: 93 passed and one Windows-native test skipped on Linux. Complete replay outcomes are in regression/summary.json. CI also includes the new detector contracts; Windows CI uses a controlled Tk window, not PPPoker.

## Remaining work, grouped

1. One Windows observer session at intended working sizes: Hero, pre-flop, flop, turn, river; button labels and amounts; preselection, spectator/no-action states; move/minimize/restore. Save only divergent diagnostics, not continuous PNGs. See WINDOWS_ONCE.md.
2. Obtain an independent real turn and the original Hero 8h error if it recurs; keep their expected values separate from calibration.
3. Fix the merged/full-frame proposal on the newly found 8h source; improve degraded 4/7/A and small suit crops only against explicit regression evidence.
4. After single-table correctness, measure six-table load, memory/GDI stability and source identity through restarts. These remain unvalidated.

White-face cards and 16-table/multi-account expansion remain deferred. Current work does not require reopening PPPoker today.
