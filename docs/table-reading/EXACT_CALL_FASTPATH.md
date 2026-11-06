# Exact Call 1.0 BB shortcut

A complete **Call 1,0 BB** ink raster can now bypass OCR only when every binary ink pixel and its shape equal the validated exemplar. No resize, digit inference, tolerant matching, prefix extraction or amount rounding occurs at matching time. The existing preprocessing enlarges native pixels by exactly 3 using nearest-neighbor: the validated native 24×123 ink becomes 72×369. Whole-label matching preserves both value and BB unit.

The single training source is `_4528A8B5…85ee615d.png`. `_58CB106F…581ae999.png` and `_76D7A22C…78803c80.png` supply source-disjoint checks with identical raster ink. They are three screenshots of the same label, not evidence for arbitrary digits or amounts.

Other Call1.0 raster sizes, Call1.6, Call2.0 and Call13.5 all reject this shortcut and keep OCR. Approximate amount matching remains disabled: the previous gate showed Call1.0/1.6 whole-label IoU 0.9394, an insufficient separation margin.

## Correctness

- Eight real Call raster checks passed: three exact positives and five fallback cases, including 1.6/2.0/13.5 and a smaller 1.0 raster.
- Twenty-four relevant unit tests passed. Tests cover a changed pixel, rescaling, appended ink, absent/corrupt assets, injected OCR bypass and mixed preselection rows.
- Thirty-six complete button-row calls preserve semantic outputs (three sources × six calls per mode). The five warm samples plus first call are recorded separately.
- F/C remains preselection for the whole row. The recognized amount stays `1.0`, unit `BB`, while `action` remains null and `label_action` remains CALL. No click permission is enabled.
- Evidence is `EXACT_WHOLE_LABEL_RASTER`; no `ocr_readings` are fabricated.

## Paired laboratory measurements

Only this exact shortcut was disabled in the baseline. Existing static-label templates and per-call OCR memo remained enabled in both modes. Order alternated by repetition; OpenCV and OpenMP were limited to one thread. No other planned OCR workload ran concurrently.

| Source | Median baseline → exact (ms) | p95 baseline → exact (ms) | OCR calls |
|---|---:|---:|---:|
| Training 4528 | 399.3 → 201.4 | 408.6 → 204.4 | 4 → 2 |
| Disjoint 58CB | 396.9 → 193.7 | 402.1 → 210.1 | 4 → 2 |
| Disjoint 76D7 | 402.5 → 196.5 | 424.5 → 199.7 | 4 → 2 |

These are five-sample whole-button-row timings, excluding capture, detector, Hero and board. The p95 is exploratory, near the largest sample. This is not a live Windows latency or broader amount-recognition claim.

## Artifacts

- `table_reading/button_template_assets/Call_1_0_BB_exact.png`
- `table_reading/button_template_assets/exact_call_provenance.json`: source/asset hashes, native and enlarged shapes, training/evaluation split.
- `tools/build_exact_call_template.py`: reconstructs and verifies the exact asset.
- `tools/validate_exact_call.py` and `exact-call-validation.json`: all raster checks, full outputs, sample timings and OCR counts.
- `test_exact_call_template.py`: targeted contracts.

A missing asset, altered SHA-256 or unexpected shape disables only the exact shortcut and leaves the original OCR path available.
