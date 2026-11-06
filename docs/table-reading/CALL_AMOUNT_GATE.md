# Call amount feasibility gate

The existing sixteen-crop report contains eight Call labels: 1.0 BB in four sources, 1.6 BB in two, 2.0 BB in one and 13.5 BB in one. This inventory reuses saved observations and real pixels; it makes no additional OCR calls.

**Do not use approximate whole-label matching for amounts.** Call 1.0 and Call 1.6 reach IoU 0.9394 in the current normalized-mask comparison. Their margin is only 0.0606, below the existing 0.12 guard. Lowering that guard would favor confusing amounts.

A narrower option is feasible: the complete native binary ink of **Call 1.0 BB**, shape 24×123, is identical in `_4528A8B5…`, `_58CB106F…` and `_76D7A22C…`. One may serve as a fixed exemplar and two as source-disjoint checks. An exact equality shortcut must use the entire native mask, with no resizing, tolerated pixel errors or substring matching. All other values and raster sizes must fall back to OCR. This finding is not authorization to generalize digits.

## Missing evidence for broader coverage

- 1.6 BB: two real sources exist, but raster heights 24 and 23 differ; neither currently has an exact source-disjoint partner.
- 2.0 BB and 13.5 BB: only one source each in this report. Additional independently captured matching examples are needed.
- Digit characters **4, 7, 8 and 9** are absent from these eight amount labels. Multi-digit and different decimal-precision amounts remain unvalidated.
- No bare Call label or alternative unit/currency is established by this set.

`call-amount-feasibility.json` records source names, native mask hashes/shapes and the pairwise matrix. `tools/evaluate_call_amount_gate.py` checks source SHA-256 values before extraction. OCR observations are not an exhaustive independently labeled amount dataset. No runtime was changed by the gate.

The narrow exact-raster option was subsequently implemented and validated; see `EXACT_CALL_FASTPATH.md`. Approximate amount matching remains rejected.
