# Protected-rank shortcut feasibility gate

Decision: **keep A, 4, 3 and 8 on OCR**. No runtime change or new template was made. The gate reused known labels only, with no search through the wider screenshot archive and no OCR or latency benchmark.

The evaluator temporarily removed only the protected-rank switch inside its own process. IoU, margin, aspect, topology and two-threshold agreement remained unchanged. It checked 102 Hero occurrences plus 60 board occurrences from six known board crops at three widths: 162 transformed occurrences, not 162 independent hands.

| Rank | Evaluation screenshot sources outside training | Positive occurrences | Correct proposed shortcuts | Wrong proposed accepts anywhere |
|---|---:|---:|---:|---:|
| A | 1 | 3 | 3 | 0 |
| 4 | 1 | 6 | 0 | 0 |
| 3 | 1 | 3 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 |

The three A observations are transformations of one Hero screenshot. They cannot establish broad safety. 4 and 3 gain no source-disjoint coverage with the existing strict criteria. The only known real colored board-eight source supplies competitor templates and is not independent evaluation. Thus this gate supports no new production shortcut and makes no speed-gain claim.

## Specific evidence needed before reopening

- **A:** additional independently captured genuine A hands, outside the atlas sources, at intended normal and reduced table sizes; retain the already known 4/7→A negative cases.
- **4:** genuine 4 crops from additional hands at the intended sizes, with an explicitly separated training/development split if new glyph variants are required. Existing six evaluation occurrences all fall back, so merely enabling the rank is ineffective.
- **3:** additional genuine 3 and 8 crops captured at the same intended sizes. The original reported Hero 8→3 PNG is absent; obtain a fresh instance if it recurs rather than marking it fixed.
- **8:** a newly captured colored 8 outside the one atlas source, together with confusable 3 negatives. Resizing the atlas screenshot does not supply this evidence.

These captures can be collected together in the next Windows validation session. No immediate real-table session is needed for this completed laboratory gate.

Reproduce: `tools/evaluate_protected_rank_gate.py --assets /path/to/aistudio --output report.json`. Detailed provenance, proposed candidates and fallback cases are in `protected-rank-feasibility.json`. The production rank switch is unchanged.
