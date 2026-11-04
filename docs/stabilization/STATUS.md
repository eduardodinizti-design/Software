# Observer stabilization — first implementation

Branch fix/observer-integration, based on d3c6e64. Work in progress, NOT a Windows release.

Changes: removed manufactured detections for missing NumPy/list inputs; HSV felt-candidate extraction replaces black-background projection; exact contour dimensions; conservative normalized-appearance association replaces left-to-right IDs; identical appearances are AMBIGUOUS; per-track integer geometry version. Observer runner now passes the actual Unity frame to the visual tracker and publishes candidate crops through telemetry, with desktop offsets.

All candidates remain unvalidated. Observer bypasses old full-surface single-table OCR and action logic. No production OCR accuracy or complete-table enclosure claim. This is a bounded diagnostic foundation, not finished tracking. Appearance changes may suspend identity; a visual table-ID reader and lifecycle policy remain necessary. Felt bounds may omit cards/buttons. Do not enable gameplay from these candidates.

Validation: Linux, real NumPy/OpenCV synthetic images. Original 12 tracker tests pass; 4 new regressions verify gray background, exact dimensions, identity swap, geometry increment, identical-appearance ambiguity, invalid inputs and out-of-bounds crops. Original OCR-routing test is only a local mock and not proof of real OCR integration.

Pending: capture bounds for this user's Unity surface; validated full-table detector with real images; windows process/API checks; moved/resized real screens; visibility; OCR version fencing; lifecycle recovery; packaged Windows validation. No installer rebuilt or approved.

## Second implementation: capture contract

- Removed process-query failures that fabricated pppoker.exe from a title.
- Removed title-based override of invalid process identity; native PPPoker/PPClient only. Emulator support needs explicit validated configuration, not generic python/electron/java allowlisting.
- Check Win32 client-area API return values; request thread Per-Monitor V2 before geometry lookup.
- Capture uses all_screens=True and validates exact returned dimensions, including negative desktop origins.
- Capture failure clears previews instead of feeding None into downstream readers.
- Runner rejects frame_valid_for_ocr=False and exposes query errors.

Three new Linux regression tests passed with mocked Win32/ImageGrab calls: access denied does not fabricate identity; (-1920,0,5760,2160) maps to correct bbox; wrong capture size is rejected. Four previous observer regressions passed again. This is contract validation, NOT Windows native validation. Full-surface occlusion and complete table-boundary calibration remain pending; no installer delivered.

## 2026-11-04 — Remoção do fallback global de identidade

A revisão encontrou um segundo fallback que, na ausência de candidatos autorizados,
voltava a enumerar todas as janelas e atribuía artificialmente `pppoker.exe` a elas.
Esse fallback foi removido. Ausência de processo autorizado retorna WINDOW_NOT_FOUND.
A lista de Z-order agora mantém janelas externas para detectar sobreposição, mas
somente processos autorizados participam da seleção do alvo. Janelas minimizadas
não contam como obstáculos.

Validação: 5 testes de contrato de captura passaram em Linux com APIs Windows
simuladas, incluindo rejeição de Chrome com título PPPoker e bloqueio por terminal
sobreposto. Isto não constitui homologação Windows. A oclusão ainda é calculada
sobre a superfície inteira; validação por mesa e enquadramento completo permanecem
pendentes. Nenhum instalador foi recompilado nesta etapa.
