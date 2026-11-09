# Fase 3B — Controlador de cursor (núcleo), sem apontar ao PPPoker

Primeiro bloco da Fase 3B, implementando a spec `ORIENTAÇÃO PARA MOVIMENTO
NATURAL D.txt` com a separação que ela exige: **gerador de trajetória puro ×
adaptador Windows × coordenador de intenção/revalidação**. Tudo testável no lab;
nada é apontado ao PPPoker nesta fase.

> **Aviso da spec:** sem dados de referência do usuário, o resultado é
> "movimento suave", **não** "humano". Uma trajetória natural não prova
> indetectabilidade. Este bloco **não** autoriza execução.

## Módulos

- **`cursor_trajectory.py`** (puro, sem Windows/clique):
  - Mínimo jerk `s(u)=10u³−15u⁴+6u⁵` (começa/termina parado); posição =
    início + s(u)·(destino−início).
  - Duração por Fitts `T=a+b·log2(1+D/W)` — **nunca** duração universal. `a,b`
    são DEFAULTS marcados `calibrated=False` (a spec proíbe apresentar
    coeficiente inventado como medido); `calibrate(a,b)` fixa os medidos.
  - Relógio injetável; progresso pelo tempo REALMENTE decorrido. Desktop virtual
    com coords negativas. Ponto-alvo = centro da região interna segura (sem
    tremor/overshoot por padrão).

- **`cursor_input_win.py`** (adaptador Windows, win32 lazy, backend injetável):
  - `SendInput` (API documentada; §7 propõe migrar do SetCursorPos+mouse_event).
  - Move absoluto normalizado ao **desktop virtual** (0..65535, VIRTUALDESK),
    tratando origem/múltiplos monitores/coords negativas.
  - **Clique ÚNICO** com soltura GARANTIDA (try/finally); tempo de pressionamento
    documentado, validável no teste (não escolhido para "invisibilidade").
  - Relata quantos eventos o sistema aceitou — aceitação de entrada ≠ execução
    da ação pela aplicação.

- **`cursor_controller.py`** (coordenador, máquina de estados §8):
  `AWAITING_INTENT → VALIDATING → MOVING → REVALIDATING → CLICKING → VERIFYING →
  DONE | CANCELLED | UNKNOWN_RESULT`. Garantias:
  - **Gate** no `BotControl` (F2): sem RUNNING, nada é enviado.
  - **Revalidação NA CHEGADA** antes do mouse-down (recaptura/confere janela/
    geometria/alvo/estado/prazo) — corrige o anti-padrão "validar → mover demorado
    → clicar sem revalidar" do executor manual. Alvo movido/invalidado → sem clique.
  - **Cancelável** no movimento (intervenção do usuário, foco, alvo, prazo) sem
    disputar o mouse (não puxa o cursor de volta).
  - **Clique único / anti-duplo**: uma intenção gera no máx. um clique; `id`
    consumido não reexecuta.
  - **Exclusão mútua**: um lock de processo serializa o cursor compartilhado; a
    fila não guarda intenção vencida (revalida o prazo após o lock).
  - **Desconhecido ≠ sucesso**: sem verificação do efeito → UNKNOWN_RESULT, sem
    repetir o clique.

- **`cursor_calibration.py`**: `MovementRecorder` (telemetria limitada, sem
  imagens) + `fit_fitts` (ajusta a,b por mínimos quadrados; devolve n e R²;
  `measured=False` com razão quando faltam amostras ou não há variância —
  nunca inventa coeficiente).

## Testes (`test_cursor.py`, 28)

Trajetória (endpoints/velocidade nula nas pontas/monotonia/Fitts/amostragem),
adaptador (normalização ao desktop virtual, clique down→up, **soltura garantida
mesmo em erro**), coordenador (happy path = 1 clique; não-armado; vencida;
cancelamento por intervenção; **revalidação na chegada falha → sem clique**;
alvo movido; sem verificador → desconhecido; anti-duplo; exclusão mútua ocupada),
calibração (recupera a,b; poucas amostras/variância nula não viram medido).

## Validado no Windows (read-only, sem mover/clicar)

O backend ctypes real constrói e lê `virtual_bounds` (ex.: -1920,0,4480,1440) e
`cursor_pos`, com normalização 0..65535. **Nenhum movimento ou clique enviado.**

## Como rodar

```bash
python -m unittest test_cursor
```

## Bloco 2 (09/11): medição, envio real e avaliação

- **`cursor_eval.py`** (puro): `movement_metrics` (duração, distância reta,
  comprimento/curvatura do caminho, velocidade de pico, tempo-ao-pico, overshoot,
  erro final, reversões/correções), `summarize_trials` (agrega + nota de que é
  descritivo, NÃO prova de origem humana), `make_trials` (alvos variados,
  determinístico por seed).
- **`cursor_sendcheck.py`**: valida o ENVIO real — move para coords conhecidas
  via SendInput, mede coord enviada×observada e RESTAURA a origem (sem clicar).
- **`cursor_test_app.py`** (Tk, alvos inofensivos, NUNCA PPPoker):
  - `--measure`: você move o mouse até cada alvo e clica; grava telemetria,
    ajusta Fitts (`fit_fitts`) e salva `logs/cursor/measure-*.json`.
  - `--auto` (experimental): o controlador move+clica via SendInput; mede
    enviado×observado e se o clique surtiu efeito; `logs/cursor/auto-*.json`.
    ESC aborta.

### Envio real VALIDADO no Windows (move, sem clique)

`cursor_sendcheck.py` no setup do Eduardo (desktop virtual -1920,0,4480,1440):
alvos atingidos com **erro ~1,3 px** (arredondamento da normalização 0..65535),
todos os eventos aceitos, cursor restaurado. A correspondência coord
enviada×observada está dentro de 1–2 px — adequada para clicar no centro seguro
de um botão de dezenas de px.

### Como medir seu movimento (calibração)

```bash
python cursor_test_app.py --measure --trials 15
# mova o mouse até cada quadrado e clique; ao fim salva logs/cursor/measure-*.json
```
O relatório traz as amostras, o ajuste de Fitts (a, b, n, R²) e o resumo de
métricas. Com ele, `TrajectoryGenerator.calibrate(a, b)` passa a `calibrated=True`.

### Clique real VALIDADO no Windows (`--auto`, app inofensivo)

`logs/cursor/auto-*.json`: o controlador moveu via SendInput, revalidou na chegada
e clicou em **6/6** botões → `state=DONE`, `confirmed=True` (o comando do botão
disparou). A intenção VENCIDA (demo) → `CANCELLED/INTENT_EXPIRED`, **sem clique**.
Fecha a validação de ponta a ponta: move + clique único + confirmação + recusa de
intenção vencida, tudo real. Correções do caminho: o `cancel_check` passou a
comparar o cursor com o ÚLTIMO ponto comandado (não o próximo — evita falso
cancelamento num passo rápido); o app fecha pela MAIN thread (Tk não é thread-safe).

## Status da 3B e o que fica

- **Núcleo + envio + clique: COMPLETOS e validados ao vivo.** Trajetória suave,
  SendInput (move ~1,3px; clique 6/6), revalidação na chegada, clique único,
  cancelamento (intervenção/vencida), exclusão mútua, gate — tudo provado.
- **Calibração de Fitts: inconclusiva** (1ª medição deu R²=0,03, b<0 — não
  usável). Mantido o `calibrated=False` ("movimento suave"), que é o honesto.
  Uma calibração real exigiria protocolo mais limpo + mais trials; é polimento
  OPCIONAL, não bloqueia.
- **Decisão do produto:** a via sustentável é a ASSISTIDA (a máquina decide, o
  usuário clica — zero input injetado). Entrada injetada carrega a flag
  `LLMHF_INJECTED` do Windows e é detectável por anti-bot independentemente do
  realismo da trajetória; NÃO se persegue evasão de detecção. O controlador fica
  como automação honesta, com todas as travas, para uso supervisionado.
