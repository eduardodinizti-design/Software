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

## 2026-11-04 — Sobreposição por região no observador

O guardião informa todas as janelas superiores sobrepostas, inclusive obstáculos
pequenos e janelas topmost acima do cliente em primeiro plano. O observador pode
capturar essa superfície, mascara as áreas externas antes da detecção e bloqueia
prévias de candidatos que intersectam ou encostam nos obstáculos. Outras regiões
continuam sendo analisadas. O caminho live continua bloqueando superfície ocluída.

Os candidatos expõem visibility e complete_table_validated=false. A segmentação
por feltro ainda não comprova que cartas e botões estejam no recorte; OCR permanece
bloqueado. Mesas completamente encobertas podem desaparecer da lista de candidatos;
esta etapa não implementa recuperação de identidade após oclusão. Máscara pode
fragmentar candidatos; a margem de contato rejeita bordas diretamente adjacentes,
sem prometer classificação perfeita de todos os fragmentos.

Validação: 13 testes de laboratório passaram (7 de observador, 6 de contrato de
captura/seleção), incluindo origem negativa, isolamento entre regiões, recorte de
obstáculos nos limites, imutabilidade do frame original e bloqueio live. APIs Windows
simuladas; sem homologação nativa ou novo instalador.

## 2026-11-04 — Ensaio de recorte com captura real existente

Foi inspecionada a captura `_21D744E1-8BE6-4C79-82AF-5582DD6A9547__6988a9e2.png`
(2072×1278), que contém uma mesa PPPoker visível à esquerda, outros clientes e um
terminal sobreposto. O detector atual retorna zero candidatos nessa captura.
Não está aprovado para encaminhar mesas completas ao OCR.

`tools/check_real_table_crops.py` reproduz essa falha e retorna código 1.
Referências manuais, exclusivas desse fixture, medem cobertura da mesa, cartas,
stacks e controles inferiores. Exige cobertura de 98% de cada região e ocupação
de 90% do retângulo candidato pela referência, impedindo aprovação do desktop
inteiro. Essas referências não são coordenadas operacionais do bot.

Comando: `python tools/check_real_table_crops.py --output docs/stabilization/real-crop-report.json`
Resultado atual: FAIL: complete table not detected. Evidência JSON versionada.
Quatro testes do avaliador passaram (referência completa, feltro incompleto,
desktop inteiro e ausência de detecção). Esses testes validam o avaliador,
não o detector. Próximo trabalho: substituir a segmentação somente por cor por
localização dos limites completos, usando esta captura como regressão e outras
escalas/temas como validação. OCR continua bloqueado, sem novo instalador.
