# Inventário consolidado do corpus local

Data: 2026-11-06. Índice reutilizável: `BATCH_CORPUS.json`. Nenhuma imagem privada foi copiada para este repositório; o índice referencia originais locais por caminho e SHA-256.

## Escopo e deduplicação

Varredura das árvores `/workspace/software-review` e `/workspace/software-current-audit`, excluindo `.git`, `node_modules`, `.venv` e `python_embedded`. Formatos PNG/JPG/JPEG; arquivos ZIP, vídeos e anexos remotos não foram extraídos nesta rodada.

| Medida | Quantidade |
|---|---:|
| Arquivos de imagem encontrados | 854 |
| Conteúdos únicos por SHA-256 | 302 |
| Cópias repetidas por SHA-256 | 552 |
| Capturas únicas em `public/assets/aistudio` | 54 |
| Dessas, com mesa visível na triagem manual | 24 |
| Capturas com rótulo vinculado por SHA ou nome | 16 |
| Capturas sem rótulo vinculado | 38 |
| Conteúdos em caminhos explicitamente sintéticos | 39 |
| Conteúdos com algum rótulo vinculado, todas categorias | 20 |

Os 54 screenshots incluem terminais, gerenciadores e telas de aplicação: não equivalem a 54 mãos. Os demais conteúdos incluem recortes derivados, templates e recursos de interface. `derived_or_unknown` é classificação conservadora; não são automaticamente exemplos reais independentes. Rótulos herdados não são resultados de reconhecimento.

O JSON inclui todos os caminhos de cada conteúdo, dimensões, classificações de procedência, referências e registros de rótulos, mais a lista dos 18 manifests/arquivos de rótulos encontrados. A vinculação automática procura `sha256`/`source_sha256` e `source`/`file`/`image` com `expected`/`label`/`cards`; schemas diferentes permanecem na lista de manifests, sem promessa de extração completa dos seus rótulos. Os totais de rotulagem significam vínculo encontrado por este procedimento, não cobertura exaustiva de todos os schemas.

## Achado: oito colorido real já disponível

Fonte: `/workspace/software-current-audit/public/assets/aistudio/_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png`.

- SHA-256: `2a4e7ea0153b94c241a76bd73f2f88b147504ca779cf0e99f48686b54a7d1d49`.
- Mesa manual `[703,54,703,1237]`; board global `[830,510,260,140]`, ambos `x,y,w,h`.
- Board **2s, 8h, 5h**, confirmado visualmente nesta revisão. Faces coloridas.
- Hero **7c, 6d** conforme rótulo histórico; não revalidado visualmente nesta rodada.
- Rótulos já registrados em `/workspace/software-review/docs/stabilization/parallel-real-labels.json`.
- Status histórico `MANUAL_COMPLETE`: detector anterior falhava nesta mesa. Portanto, limitar a busca às regiões aceitas pelo detector ocultava uma amostra útil.

Esse achado amplia cobertura real do board com 8h. Não reproduz o erro Hero 8h→3h relatado pelo usuário, cujo PNG original continua ausente. O replay do board é trabalho separado do inventário e deve ser conferido no relatório do executor.

## Busca independente do detector e lacuna de turn

Todas as 54 capturas únicas de aistudio foram triadas em folhas de contato, incluindo rejeitadas; boards candidatos foram vistos em resolução maior. Encontraram-se flops e rivers, mas **nenhum board real de quatro cartas foi identificado nesta triagem**. Isso não prova inexistência em vídeos, ZIPs ou anexos fora das duas árvores. Não converter river em turn removendo carta e contar como nova captura real.

Duas capturas de mesa apresentam faces brancas (`6988a9e2…`, `02419b13…`), fora do foco colorido atual. As demais capturas com mesa não devem ser descartadas só porque o detector não as aceita: há mesas ocluídas, escurecidas ou com slider aberto que servem como negativos e casos de rejeição.

## Conjuntos históricos e risco de contagem

- `docs/stabilization/frozen-validation-labels.json`: declara explicitamente que os exemplos já orientaram o desenvolvimento; **não são mais held-out**.
- `docs/stabilization/heldout-card-labels.json` e `parallel-real-labels.json`: rótulos de fontes reais; preservar a origem e distinguir mesas completas, ocluídas e recortes.
- `delivery/card_reader_fix/test_fixtures/manifest.json` e `segmented_manifest.json`: crops de rank/naipe derivados; não contar cada crop como nova mão independente.
- Diretórios `synthetic_deck`, manifests `synthetic-*` e variantes de tamanho: testes de contrato/robustez; não evidência de acurácia real.
- `repo_visualpilot/tests/fixtures/heldout_cards/labels.json`: conjunto separado, cuja procedência e tema precisam ser respeitados.

## Uso no lote

1. Reexecutar em lote fontes reais rotuladas, incluindo recortes manuais de mesas rejeitadas, e reportar detecção separadamente de leitura.
2. Usar 2s/8h/5h como regressão real adicional de board. Não substituir o caso Hero perdido.
3. Contar resultados por SHA de fonte e papel (Hero/board); variantes são robustez do mesmo exemplo.
4. Manter negativos sem mesa, lobby, tema branco e oclusão explícitos; não premiar ausência de leitura como acerto de carta.
5. Acumular para a próxima sessão real apenas as lacunas comprovadas: turn real colorido e ocorrências novas de erros, preservadas por salvamento diagnóstico explícito.
