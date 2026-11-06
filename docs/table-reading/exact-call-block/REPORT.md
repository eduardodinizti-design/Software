# Exact Call template and bounded sample collection

The complete-label binary raster for `Call 1,0 BB` now bypasses OCR only on an exact match, including every digit and the BB suffix. Other amounts, resolutions and altered pixels retain OCR. Existing preselection behavior is preserved; no actions are executed.

## Laboratory evidence

- 165 contract tests: 164 passed, one native Windows test skipped on Linux.
- Button template replay and seven pipeline cases passed (see adjacent JSON reports).
- Eight real Call raster cases: three exact matches; different amounts and raster sizes rejected.
- 36 paired complete-button-row measurements across three screenshots: median approximately 400 ms before and 200 ms after; OCR calls fall from four to two. This measures button rows, not capture cycles or six-table throughput.
- Protected A/4/3/8 families remain on OCR: independent evidence is insufficient. The original missing 8h misread image remains unresolved.

## Bounded samples

`python coletar_amostras.py --hwnd HWND_ATUAL` captures one snapshot and saves native Hero, board and button regions only, under logs/leitura. Replace HWND_ATUAL with the current numeric window handle. Offline image plus metadata input is also supported.

Samples remain UNLABELED and are never automatically imported for training. Each bundle is limited to 2 MiB and shares the existing 100 MiB diagnostic quota. One laboratory table produced 234,761 bytes including JSON; size varies with content. Normal observation still does not save images.

Native PPPoker performance and multi-table behavior still require a later Windows session. CI results are published separately by the Windows workflow.
