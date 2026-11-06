# Bounded parallel board reading

Community-card recognition now runs at most two card readers concurrently. Inputs, preprocessing, thresholds, returned ordering, duplicate checks and Hero exclusions are unchanged. Both workers finish before the next snapshot. The snapshot-local OCR cache uses a lock for accounting/insertion; subprocess work runs outside the lock. No cross-frame results are retained. Injected test readers remain sequential.

Validation: 57 focused tests passed. The paired pipeline benchmark used two reused real source screenshots, three samples per source in each process, four processes in serial/parallel/parallel/serial order: 24 total calls. All full semantic signatures matched within each source. Recognition accuracy beyond these development examples is not established.

For the source with board, serial median was 2815 ms and parallel 2716 ms (about 3.5%). The source without board showed 449 vs 471 ms; the parallel board path is not entered there and these results demonstrate timing variability. An isolated board measurement on a third reused source had serial 1023/1039 ms and parallel 851/714 ms, identical full output (about 24% lower median). Two measurements per mode are exploratory, not a stable tail-latency estimate. Native capture and Windows performance are excluded.

No changes to storage policy, table detector or acceptance thresholds. Use VISUALPILOT_PARALLEL_BOARD=0 for a controlled sequential comparison. Per-card concurrency can change OCR cache hit counts; memory limits remain enforced under concurrent insertions. All timing data are in adjacent JSON files. Run tools/benchmark_parallel_board.py for the paired pipeline measurement.
