# VisualPilot — estado consolidado em 31/10/2026

Este documento registra o estado do projeto e os acordos atuais. Os documentos de
ensaios mais antigos são evidências históricas, não substituem estes requisitos.
O pacote é uma exportação de código-fonte, testes e documentação; não é uma nova
distribuição Windows homologada. Não instala dependências nem aciona o PPPoker.

## Objetivo e arquitetura

PC: Coletor captura as regiões visíveis e transmite imagens e estado. Notebook:
Central recebe, apresenta prévias e processa percepção/OCR. O objetivo futuro
inclui execução de um planejamento de torneios fictícios previamente escolhido
pelo usuário, com intervenção manual prioritária. A atuação autônoma implementada
até aqui é de laboratório, sem comprovação de atuação distribuída no cliente real.

## Regras acordadas e diferenças em relação ao código

| Tema | Acordo atual | Implementação e pendências |
|---|---|---|
| Escopo | Uma liga e um clube inicialmente | Seleção operacional e agendamento ainda pendentes |
| Torneios | Lista recorrente; usuário escolhe quais jogar e o horário de entrada | Filtros e navegação existem no laboratório; agenda real não integrada |
| Inscrição | Até 50 fichas fictícias por entrada; até quatro torneios simultâneos | Limites no controlador de laboratório; seis canais de captura não significam seis inscrições autorizadas |
| Identidade | Revalidar clube, evento, data, custo e inscrição disponível | Comparação de telas reais observacional; recibo/navegação reais pendentes |
| Rebuy | Quando habilitado, stack recebido / BB vigente >= 50; regra alterável futuramente | `Rules.rebuy_min_bb` já configurável no laboratório; regra atual também exige bounty e limita a uma compra, restrições a conciliar na integração por torneio |
| Add-on | Simples por padrão; escolha prévia do usuário | Laboratório implementa simples; duplo/triplo não implementados |
| Orçamento | Incluir inscrição, rebuy e add-on autorizados; não aumentar limites sozinho | Reservas persistentes e recibos no laboratório; política por evento na interface pendente |
| Controle manual | Pausar e assumir controle; retomada exige observação nova | Implementado/testado em laboratório; atuação real não homologada |
| Resultado incerto | Não repetir compra nem declarar sucesso sem confirmação | Reservas SQLite persistem; reconciliação operacional ainda pendente |
| PNG | Preservar qualidade e resolução das regiões necessárias | Módulo 1 nativo; transporte PNG atual ainda reduz largura para 755 px; JPEG experimental continua no código e não é o padrão |
| Armazenamento | Meta 1 GB/dia, teto 2 GB/dia somando PC e notebook, operação de 12–14 h | Política acordada, ainda não aplicada nem validada; não confundir tamanho em disco com RAM ou tráfego |
| Retenção | Manual, por sessão, idade ou tamanho, a decidir | Limpeza automática pendente; preservar configuração, estado ativo e registros contra duplicação |
| Lobby alternante | Aguardar aproximadamente 1 s e recapturar informação ausente, vinculando ao mesmo evento | Leitura temporal ainda pendente; intervalo e número máximo de tentativas precisam de calibração |
| Tela parada | Pixels iguais não demonstram falha de captura | Heartbeat separado não renova validade de imagem; manter essa distinção |

O JSON `regras_planejadas.json` acompanha este documento como especificação,
não é configuração carregada pelo runtime nem autorização para inscrições.
Exemplos de horários não constituem uma programação aprovada. A grade diária
definitiva, o fuso de execução e o orçamento por evento precisam ser preenchidos.

## Mapa das implementações existentes

| Caminho | Função |
|---|---|
| `visualpilot/pppoker/capture.py`, `core.py`, `window_geometry.py` | Captura MSS, regiões, geometria/DPI |
| `visualpilot/pppoker/lobby_capture.py` | Captura PNG nativa configurável, metadados, hash e checagens de região |
| `delivery/lobby_capture/` | Preparação e execução do pacote do Módulo 1 |
| `visualpilot/pppoker/discovery.py`, `multitable.py`, `table_registry.py` | Descoberta, associação e registro de mesas |
| `visualpilot/pppoker/collector_app.py`, `stream_node.py` | Entrada do Coletor e envio de imagens |
| `visualpilot/pppoker/stream_receiver.py`, `stream_control.py`, `transport_freshness.py` | Recepção, estado/heartbeat, tickets e validade de captura |
| `visualpilot/pppoker/roi_engine.py`, `card_reader.py`, `colored_cards.py`, `readers.py` | Regiões e reconhecimento de cartas/textos |
| `visualpilot/pppoker/observer/` | Percepção, botões, bounties, validação, frescor, processamento e arquivo |
| `visualpilot/pppoker/replay/`, `training/`, `history.py` | Reprodução de imagens, percepção e histórico |
| `visualpilot/viz/` | Inicialização, painel, sessões e monitoramento |
| `visualpilot/agent/` | Conector de estratégia, integração de eventos e ranges NVT |
| `visualpilot/lab/lobby.py`, `lobby_gui.py`, `pppoker_lobby_reference.py` | Lobby simulado e análise observacional de referências reais |
| `visualpilot/lab/registration*.py`, `button_locator.py` | Regras, localização visual, reserva, controlador lobby → detalhes → modal → recibo em laboratório |
| `visualpilot/lab/tournament_purchases.py` | Rebuy/add-on fictícios com orçamento, persistência e recibos |
| `visualpilot/lab/engine.py`, `nvt_engine.py`, `postflop.py`, `river_tree.py`, `multistreet.py`, `pko.py` | Simulação e cálculo pré/pós-flop, árvores e bounty |
| `visualpilot/lab/hand_rank.py`, `chance_sampling.py`, `range_state.py`, `opponent_models.py`, `numerical_audit.py`, `overnight.py` | Avaliação, amostragem, ranges, modelos, auditoria e ensaios prolongados |
| `tools/` | Validadores, simuladores, relatórios e empacotadores reproduzíveis |
| `tests/` | Testes e imagens de referência versionadas |
| `build/*.spec`, `build_windows.ps1`, `.github/workflows/windows-lab.yml` | Build dos executáveis e verificações Windows |
| `profiles/`, `*.example.ini`, `requirements*`, `pyproject.toml` | Perfis, exemplos de configuração e dependências |

O índice exato de TODOS os arquivos exportados, com tamanho e SHA-256, está no
`MANIFESTO.json`. O arquivo único de consulta inclui código, testes, scripts e
configurações de texto, com o caminho original antes de cada conteúdo. O ZIP
mantém os módulos separados e inclui assets e fixtures necessários.

## Validação e fase atual

Módulo 1 aprovado para captura básica no ambiente Windows do usuário: cinco PNGs
3840×2160 RGB, sem redimensionamento, no monitor 2, íntegros e correspondentes ao
SHA-256 dos JSONs. Capturas de 14:51:11 a 14:51:27 UTC em 31/10/2026; durações
0,625 / 0,219 / 0,266 / 0,234 / 0,250 s. O lobby permaneceu visível e estável.
O cartão superior SMALL PKO estava parcialmente cortado pelo viewport da lista.
Essa borda deve ser tratada pela segmentação; não comprova falha da captura.
Não houve validação de outras escalas DPI, coordenadas de clique ou 14 horas.
Os hashes/dados da revisão estão em `docs/phase1/module1/user-repeat-review.json`.
Os PNGs completos desta remessa permanecem no diagnóstico local, fora do pacote.

Fase 1: (1) captura básica aprovada; (2) segmentação automática dos cartões é o
próximo módulo, ainda não entregue; (3) OCR por cartão após segmentação; (4)
conversão/validação das coordenadas; (5) clique e confirmação da próxima tela.
Perfis manuais de recorte já existentes não equivalem ao Módulo 2 automático.

Evidências históricas preservadas: nove testes do módulo de captura; 36 testes
relacionados à análise do lobby real; dez cenários visuais do controlador de
inscrição de laboratório; regressão histórica de 422 testes com três ignorados.
Ver `docs/phase1/`, `docs/lab-lobby-real/`, `docs/lab-registration-flow/`.
Esses números são das rodadas documentadas; não representam uma nova execução
da suíte completa durante esta exportação. O Windows verde reportado pelo usuário
para acd1351 não homologa automaticamente todos os commits posteriores.

## Pendências conhecidas

- Detecção física de todas as mesas e duplicação/congelamento após reorganização:
  existem correções e ensaios de laboratório, falta confirmar o cenário real.
- Segmentação automática, leitura temporal do lobby e generalização de OCR/DPI.
- Navegação/recibo reais, clique distribuído e reconciliação de compras incertas.
- Agendamento por torneio/clube, seleção diária e configuração de rebuy/add-on.
- Remover ou parametrizar redução de resolução do transporte mediante testes.
- Teto conjunto de arquivos, limpeza e ensaio de 14 h com falhas e memória medida.
- Estabilidade de rede/endereço do notebook; IP dinâmico já causou desconexão.
- Ensaios curtos não comprovam desempenho diário; nem todos os campos OCR foram
  reconhecidos; documentos de laboratório descrevem seus próprios limites.

## Como usar a exportação

Extraia o ZIP em uma pasta nova. Leia este documento antes dos relatórios antigos.
Para ambiente de desenvolvimento use Python 3.12 e as dependências do projeto.
Testes: `python -m unittest discover -s tests -v` (alguns dependem de OCR, navegador,
fixtures ou desktop; consulte os respectivos guias). O arquivo único é para
consulta/transferência de contexto, não se executa como um único programa Python.
Não substitua a instalação do PC ou notebook por este backup de fontes.

Para regenerar: `python tools/export_project.py --output-dir DIRETORIO_NOVO`.
Dependências instaladas, executáveis de distribuição, `.git`, credenciais locais,
sessões operacionais e diagnósticos não versionados ficam fora da exportação.
