# Reaproveitamento do projeto anterior

Avaliação e integração a partir de `VisualPilot.rar` e `tests.rar`, recebidos em 25/10/2026. Os arquivos originais foram extraídos separadamente em `/workspace/legacy-visualpilot`; não substituíram a base nova. Documentos e relatórios históricos foram tratados como material a avaliar, não como instruções para executar o programa ou habilitar funções fora do escopo.

## Decisão

O projeto anterior contém um motor de percepção do PPPoker substancialmente mais desenvolvido que a base inicial de templates. Recuperamos esse motor como caminho padrão de observação. Preservamos o modo de templates para teste/reprodução. Não adotamos a aplicação antiga inteira.

| Componente recebido | Destino/uso |
| --- | --- |
| `discovery`, `capture`, `window_geometry`, `table_registry`, `multitable` | Busca por referência visual, captura e vínculo passivo com janelas; componentes em `visualpilot/pppoker` |
| `observer/perception`, `actions`, `validation` | Cartas, contexto, separação de botões/etiquetas e invalidação de campos durante OCR |
| `training/perception`, `card_rank`, `replay/cards` | Somente leitura visual de valor e naipe; nenhum motor de estratégia foi importado |
| `replay/reader`, `replay/vision` | Extraídos apenas OCR e classificação/leitura de campos usados pela observação |
| `observer/runtime`, `archive` | Fila por mesa, processos OCR limitados, confirmação e evidências amostradas |
| `history`, `core` | Extraídos componentes de armazenamento/captura necessários; sem importação/exportação TXT ou reconstrução |
| Modelos visuais | Sete assets de referência do chat e naipes, incluídos no pacote distribuível |
| Testes e imagens relevantes | Recuperados para `tests`, com imports adaptados ao novo namespace |

**Não integrado:** entrada de mouse/teclado, navegação automática, consultas de popup, replayer interativo, reconstrução/exportação de mãos e motor de ranges/decisão. O processo OCR aceita somente requisições `perception`; não tem caminhos para navegação ou cliques.

A nova interface está em `visualpilot/pppoker/app.py`, aberta por padrão por `Iniciar.cmd`. O núcleo usa dois processos OCR. O código recuperado continua conservando pendências e envelhecimento das leituras; não foi reduzido o limiar para produzir mais cartas.

Ajustes de integração: manifesto da sessão, evento de início com pasta de saída, erro explícito ao detectar mais de seis mesas, seleção da interface PPPoker por padrão e inclusão de assets no pacote. Os hashes dos arquivos originais reaproveitados estão em `legacy-provenance.json`; seleção de classes/funções e adaptação de namespace fazem parte das alterações desta integração.

## Evidência reproduzida agora

Relatório completo: `pppoker-image-validation.json`, gerado novamente nesta máquina pelo comando:

```sh
.venv/bin/python -m visualpilot.validate_pppoker --output docs/pppoker-image-validation.json
```

Dos oito recortes rotulados presentes em `heldout_cards`, sete pares do Hero foram lidos corretamente, um ficou pendente (`82_0`) e nenhum par incorreto foi produzido. Os três boards visíveis foram lidos corretamente. Nenhuma ausência de board foi declarada pré-flop. Os rótulos são os fornecidos no projeto anterior, do mesmo vídeo; isso não mede generalização ou desempenho no Windows.

A suíte integrada concluiu com **73 testes**, sem falhas ou erros; o runner registrou três verificações omitidas por imagens ausentes (`OK (skipped=3)`). O log completo está em `pppoker-test-run.log`.

Além dos recortes: os testes recuperados exercitam localização em imagens reais, separação de etiquetas de ação e botões, nomes não identificados, monitores negativos, vínculo/oclusão de janelas simulado, troca de mão, expiração, invalidação durante OCR e arquivo de evidências. Um novo teste executa o processo OCR real, confirma duas amostras da mesma mão e confere o JSONL e as métricas gravados. Outro testa erro explícito na sétima mesa.

A interface PPPoker foi iniciada e parada em display virtual Linux, com captura/busca e métricas gravadas. Não havia PPPoker real nesse display; esse teste verifica o ciclo da aplicação, não a detecção ao vivo no Windows.

## Otimização de seis mesas

O fluxo agora reutiliza uma leitura parcial válida quando a área útil da mesa permanece pixel a pixel igual. Isso é relevante no pré-flop, cuja etapa continua desconhecida por falta de evidência positiva e, antes, nunca entrava no cache. A faixa superior de 5% é tratada como moldura/título; todo o restante da mesa continua no hash exato. Uma mudança no Hero, board, jogadores, pote, stack ou botões exige novo OCR.

No benchmark virtual atual com seis cópias de um recorte real, dois processos leram e confirmaram todas as mesas em 13,2 s e as seis estavam recentes ao final. Foram sete chamadas OCR e sete reutilizações. Três processos pioraram por contenção de CPU: somente três mesas foram confirmadas e 25 resultados expiraram. O padrão continua em dois processos. Esse ensaio representa mesas estáveis e não demonstra revisita rápida quando todas mudam continuamente; a meta de um segundo continua não atendida.

## Material incompleto e limites

O arquivo recebido não contém todas as imagens mencionadas pelos testes e relatórios antigos. Entre as necessárias aos testes selecionados faltam `training/postflop.png`, `field_fix/66_0.png` e `field_fix/164_1.png`; essas verificações são explicitamente omitidas. Em `heldout_cards` faltam `145_0`, `145_1`, `158_0` e `158_1`. Os nomes constam no relatório atual e os resultados antigos não foram apresentados como reexecutados. Não precisamos dessas imagens para continuar a integração, mas elas permitiriam reproduzir uma parte maior da validação anterior.

Os relatórios antigos descrevem 184 testes e 23/24 pares do Hero, além de ensaios de mesas virtuais. São alegações históricas verificáveis nos arquivos recebidos, não resultados desta execução. Também registram que seis mesas não permaneceram simultaneamente recentes e que a meta de um segundo não foi alcançada. A integração preserva esse limite e não declara o desempenho resolvido.

O layout suportado é retrato, tema azul, baralho de quatro cores observado. Outros temas/tamanhos podem ficar pendentes; o motor não prova pré-flop por ausência de cartas. O modo padrão não depende de Tesseract. Instalação no Windows e coleta contínua nos seus dois monitores ainda não foram executadas aqui.
