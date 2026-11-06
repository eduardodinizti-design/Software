# Offline reader performance

All 60 calls (50 warm measurements and 10 first calls) preserved complete semantic outputs and matched expected Hero/community cards. Every call discarded its own OCR memo; no cache survived between frames. Actions remained disabled.

| Scenario | Median baseline → memo (ms) | p95 baseline → memo (ms) | OCR calls baseline → memo |
|---|---:|---:|---:|
| repeated_1 | 2945.2 → 2538.2 | 3001.7 → 2567.6 | 30 → 24 |
| repeated_3 | 8800.3 → 2600.1 | 9785.7 → 2784.7 | 90 → 24 |
| repeated_6 | 17670.8 → 2926.8 | 17772.6 → 3004.8 | 180 → 24 |
| diverse_3 | 5223.5 → 3497.8 | 5241.2 → 3533.3 | 53 → 35 |
| diverse_6 | 11337.5 → 7129.5 | 11445.0 → 7706.5 | 112 → 69 |

The diverse six-crop case is the more relevant laboratory observation. Identical repeated tiles deliberately favor cache hits and do not demonstrate live six-table capacity. Diverse crops are also synthetic tilings of reused development sources. Scenarios contain different numbers of visible community cards and buttons, so absolute timings are not an isolated scaling comparison.

## Method and limits

- Full pipeline: detector, OCR setup, Hero, button and community-card readers. No Windows capture or desktop interaction.
- Five warm samples per mode/scenario. First call is recorded separately per scenario/mode in this process, not an OS-cold start.
- Baseline always precedes memo; order and warmup may bias timing comparisons.
- Five-sample p95 is exploratory and near the maximum, not stable production tail latency.
- OpenCV and Tesseract/OpenMP use one thread. No other planned OCR workloads ran concurrently.
- JSON records every sample, stage median/p95, source hashes, complete semantic references and OCR requests/calls/hits/bytes.

## Environment

- python: 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]
- platform: Linux-6.18.57-x86_64-with-glibc2.41
- opencv: 4.11.0
- opencv_threads: 1
- OMP_THREAD_LIMIT: 1
- cpu_model: INTEL(R) XEON(R) PLATINUM 8573C
- tesseract_version: 5.5.0

## Reproduce

```sh
python tools/benchmark_reader.py --assets "$VISUALPILOT_ASSETS" --output docs/table-reading/performance/benchmark.json --samples 5
```

Source decoding and tiling happen outside timed calls. Each call runs the real detector and readers; no OCR or detector result is mocked. Nonzero exit signals label or semantic mismatch.

## Decision

The 250 ms p95 end-to-end target is **not met**, even before Windows capture. Six diverse crops still require 7706.5 ms exploratory p95. The optimized median stage times are approximately: detection 413 ms, OCR setup 31 ms, Hero reading 4888 ms, button reading 1163 ms and board reading 571 ms. Stage medians do not necessarily sum to the total median.

Prioritize reducing rank/button OCR subprocess dependence next. Compare a template-based fast path or persistent OCR backend against the preserved fallback and existing negative cases before considering a trained detector/classifier replacement. YOLO alone localizes objects; card rank/suit and variable action amounts still need explicit recognition and validation. Detection's own 413 ms also exceeds the whole-system target in this synthetic scene, so OCR optimization alone cannot establish the target.

Exact snapshot memoization is retained because outputs match and work decreases. No capture identity checks, recognition thresholds or frame freshness rules were relaxed. Cache payload is bounded and discarded after each snapshot; the observer reports requests/calls/hits without storing images.

Integrated laboratory regression: 121 contracts, 120 passed and one native-Windows test skipped, plus nine replay jobs. Windows CI for the published commit must be checked separately; it uses a controlled Tk capture window, not PPPoker.
