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

## 2026-11-04 — Candidato completo ancorado nos controles

Implementado `table_boundaries.py`: procura três controles verdes alinhados,
com dimensões semelhantes e espaços compatíveis, e acompanha a superfície azul
para cima. Margens são proporcionais à largura observada; não usa coordenadas
fixas da captura. Se não houver âncoras suficientes, não inventa uma mesa completa.
O tracker prioriza esses candidatos e mantém o detector experimental de feltro
quando não encontra controles. Ambos continuam sendo candidatos sem autorização
para OCR. Em cenas mistas, a prioridade dos candidatos ancorados pode omitir mesas
sem controles: cobertura multimesa completa permanece pendente.

A referência real antes reprovada passou no avaliador de cobertura (JSON atualizado).
Três testes novos passaram, incluindo quatro escalas (50%, 75%, 100%, 125%) com
translação, remoção dos controles e controles sem superfície azul. Sete testes
anteriores de observador também passaram. Essas variantes derivam da mesma captura,
não são validação independente de novos layouts. Não há reconhecimento semântico
de botões, validação de OCR, homologação Windows nem novo instalador nesta etapa.

## 2026-11-04 — Validação ampliada e cenas mistas

Corrigido retorno antecipado: encontrar controles em uma mesa não deve excluir
candidatos de feltro em outras regiões. Os dois métodos agora são combinados,
suprimindo candidatos com pelo menos 50% de sobreposição sobre a menor caixa.
Candidatos ancorados têm prioridade no limite de seis; isso não valida identidade
nem autoriza OCR.

Cinco testes de limites passaram: escalas/translação, ausência de âncoras,
controles sem mesa, composição com duas cópias de uma mesa real mais um candidato
sintético de feltro (exatamente três regiões), e limite de seis. A composição não
representa duas mesas reais independentes. Somados aos sete testes de observador,
seis de contrato Windows e quatro do avaliador, foram 22 testes aprovados nesta etapa.

`tools/check_capture_inventory.py` executou ambos os detectores nos 18 PNGs de
assets/aistudio. Resultado versionado em capture-inventory.json com hashes e caixas.
Somente dois PNGs geraram candidatos; grande parte dos outros PNGs mostra logs/UI.
Das quatro capturas visualmente identificadas como cenas com mesas, continuam sem
candidato image_2da5ef3e.png e _4CCF9DD1-A945-450A-9C7C-2334847FE3E4__02419b13.png.
A captura _72432B1C... gera apenas candidato de feltro, sem comprovação de cobertura.
A referência _21D744E1... continua passando no avaliador de cobertura anotada.
Não há taxa de acurácia calculada a partir deste inventário sem rótulos completos.

Pendências: detecção nas duas capturas sem candidato, mesas sem controles visíveis,
validação independente dos limites e recuperação de identidade. OCR continua
bloqueado. Nenhum instalador ou homologação Windows produzido nesta etapa.

## 2026-11-04 — Controles multicoloridos e máscara azul separada

Detectores ajustados para controles vermelhos/amarelos além dos verdes e uma
máscara azul separada (HSV H=105..130), pois a máscara ampla conectava a mesa ao
fundo ciano. Candidatos sobrepostos entre máscaras são suprimidos.
Inventário atualizado: quatro capturas com candidatos; os outros 14 PNGs continuam
sem candidatos. Isto não comprova acurácia geral ou recorte completo em todas elas.

Validação: sete testes de limites passaram e sete de observador passaram; referência
anotada original continua PASS. Dois novos ensaios de escala FALHARAM e permanecem
explicitamente registrados como expectedFailure: captura sem controles a 50% gera
zero candidatos; captura com controles multicoloridos a 75% perde parte do topo.
Os testes nas escalas nativas passaram, e multicolorido a 125% também passou.
Essas falhas conhecidas não são aprovação: próxima etapa deve resolvê-las sem
remover os testes. OCR continua bloqueado; não houve homologação Windows.
