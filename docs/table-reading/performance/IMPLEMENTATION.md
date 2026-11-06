# Snapshot-scoped OCR optimization

The current reader uses OpenCV and Tesseract. This change removes redundant Tesseract subprocess calls for exactly identical prepared pixels with the same shape, dtype, OCR keyword arguments and executable path. It does not add YOLO, change recognition thresholds, infer labels from button colors or reuse results from previous screenshots.

`analyze_tables` opens a ContextVar-scoped memo and closes it in a finally block. Only uint8 arrays and string OCR outputs are retained; exceptions are not cached. The memo has a 256-entry / 16 MiB payload cap (Python metadata overhead is additional). Every snapshot starts empty. Contexts are isolated between ordinary threads; nested calls share the outer policy so the benchmark can disable reuse. Standalone readers outside a context retain their previous behavior.

Different preprocessing thresholds sometimes produce exactly the same mask. Rerunning the same deterministic OCR is redundant and does not constitute independent visual evidence. All existing disagreement/abstention rules remain unchanged. Hash similarity, approximate matching and persistent card memory are not used.

Each pipeline result exposes `ocr_work` requests/calls/hits/payload bytes. The observer's bounded 120-outcome diagnostics aggregate requests/calls/hits separately from millisecond timings. No image storage is introduced.

## Reproduction

```
python tools/benchmark_reader.py --assets public/assets/aistudio --output benchmark.json --samples 5
python tools/run_lab_batch.py --assets public/assets/aistudio
```

Run the benchmark alone to reduce CPU contention. It sets OMP_THREAD_LIMIT=1 and one OpenCV thread for BOTH modes; timings do not measure the impact of thread settings. Each sample has its own fresh memo. The first call is reported separately; it is not a truly cold OS/Tesseract startup. Baseline precedes optimized samples, so order/warmup effects remain possible. Five warm samples yield exploratory p95 estimates, not capacity certification.

Scenes are tiled real development crops. Identical repeats intentionally expose a favorable bound; use diverse-content results for planning. Pipeline timing includes detection and all enabled readers, but excludes Windows capture, live arrival rate and scheduling. Button outputs are checked for equivalence, not newly certified against independent ground truth. Hero/board expected labels are checked explicitly. The 250 ms p95 target must not be claimed unless actually achieved.
