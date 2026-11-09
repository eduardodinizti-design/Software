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

## O que FALTA (honesto) — próximos blocos da 3B

- **Medir o movimento REAL do Eduardo** num app de teste (alvos inofensivos, sem
  PPPoker) e ajustar `a,b` com `fit_fitts` → só então `calibrated=True` e é
  honesto falar em semelhança. Hoje é "movimento suave" com coeficientes default.
- **Validar o envio real** (SendInput movendo/clicando) contra o app de teste —
  latência, jitter, aceitação de eventos, correspondência coord enviada×observada.
- **Métricas de avaliação independentes** (duração×distância, curvatura, perfis
  de velocidade, estabilidade de chegada, erro final) sobre amostras gravadas.
- Só depois disso, e com turno/estado validados, cogitar apontar para uma ação
  real — o que é a fronteira da F4, com todas as travas (gate, revalidação,
  clique único) já no lugar.
```
