# Plano — Percepção da mesa (ler o contexto certo pro cérebro decidir)

> Objetivo: o advisor hoje é bom de poker, mas recebe um **retrato errado da mesa**.
> Isto gera os erros grotescos ao vivo (CALL de T2o, open de J8o/Q9o, limp não visto).
> A EXECUÇÃO (clicar fold/call/check/raise/all-in) já está pronta e testada. O
> gargalo é a PERCEPÇÃO. Este plano ataca em camadas, na ORDEM DE DEPENDÊNCIA.

## Princípio de teste (parar de drillar ao vivo)
Spots ao vivo são fugazes e caros de reproduzir. Em vez disso:
1. **Coletar um conjunto de spots rotulados** (capturas com a verdade anotada à mão:
   cartas, posições, apostas por assento, quem abriu/limpou, spot correto).
   Já temos sementes: `bets_diag`, `limp_spot`, `valida_bets` (no scratchpad; mover
   pra `tests/fixtures/table_context/`).
2. **Corrigir e validar OFFLINE** contra esse conjunto (regressão), não ao vivo.
3. Só então **1 passada de confirmação ao vivo**.

## Camadas (ordem de dependência)

### ✅ Camada 1 — VALOR das apostas (FEITA, 12/11)
`table_state.read_bets`: região do valor corrigida (borda direita do chip, altura
±0.02h, upscale 4x + OTSU). Lê 0,5/0,9/1,0/4,0 → 4/4; ao vivo 0,8 e 1,0 limpos.

### ✅ Camada 2 — POSIÇÕES (FEITA, 12/11)
RAIZ: não era a lógica de posição nem a detecção do botão (ambas certas) — era a
**OCUPAÇÃO**: `read_occupancy` não via o `top_center` (o box do nameplate ali mistura
nameplate+chip de aposta+feltro → blue~0.51 borderline → marcava VAZIO → `derive_positions`
deslocava TODAS as posições, SB caía no assento errado). FIX: fallback pelo **AVATAR**
(foto clara → blue<0.5; assento vazio/'Empty' → blue ~0.72–0.99) — conservador, sem FP.
Validado na fixture `limp_spot`: SB volta a ser top_center; 8 ocupados; 19 testes OK.
Falta: validar em mais fixtures (Empty-button, assentos ocluídos) e calibrar anchors se
preciso. Detalhe abaixo mantido como histórico.

### 🔑 Camada 2 (histórico do diagnóstico) — POSIÇÕES
**Problema (visto ao vivo):** o SB real (jvlioAL, topo) ficou **sem posição (None)** e
o rótulo "SB" foi pra outro assento ('right_up'). Botão (D) no periih.
**Onde:** `table_reading/dealer_button.py` (`find_dealer_seat`, `derive_positions`,
`_CORE`) + `seat_layout.CLOCKWISE`.
**Hipóteses a investigar:** (a) `find_dealer_seat` detecta o badge "D" no assento
errado; (b) `occupied_seats` entra incompleto (assento do apostador não marcado
ocupado → sem posição); (c) a ordem `CLOCKWISE` vs. a ordem real da mesa não casa
em mesas 6/7-handed. **Validar:** derive_positions(dealer, ocupados) → conferir
SB/BB/BTN contra a verdade em N spots rotulados. **Sem isto, `count_limpers`
(que exclui SB/BB pela posição) e a classificação de spot NUNCA ficam certas.**

### ✅ Camada 3 — ATRIBUIÇÃO aposta→assento (FEITA, 12/11)
FIX em `read_bets` (3 partes): (1) **rejeita chip sobre o AVATAR** de assento ocupado
(timer/roupa/logo vermelhos das fotos viravam 'chip'); (2) atribui **só a assentos
OCUPADOS** (Camada 2); (3) **UMA aposta por assento** (mantém o chip mais perto do
jogador → chip central/morto perde p/ o verdadeiro, mata o phantom). Validado: `limp_spot`
→ [SB 0.5, BB 1.0] (phantom 1.3 sumiu); end-to-end spot=open_raise, J3o LJ → fold. 19 testes OK.
FALTA: validar num spot com LIMP REAL de vilão (confirmar limpers>0) e por fixtures variados.

### Camada 3 (histórico) — ATRIBUIÇÃO aposta→assento
**Problema:** o chip de aposta fica ENTRE o assento e o pote (puxado pro centro), e o
"assento mais próximo" erra — duas apostas colapsaram em 'top_center'.
**Onde:** `read_bets` (heurística `min(SEAT_ANCHORS, key=dist)`).
**Fix proposto:** atribuir pelo VETOR assento→centro (o chip fica na reta entre o
nameplate do assento e o pote), não pela distância crua; 1 aposta por assento (a mais
próxima da reta). Validar contra os spots rotulados.

### Camada 4 — CLASSIFICAÇÃO do spot (first_in / vs_open / vs_limp / iso)
Depende de 1+2+3 corretos. Com apostas+posições certas: `count_limpers` conta limp
(~1bb de não-blind), `opener_raise_bb` acha o open (>1.5bb). Hoje cai em `open_raise`
quase sempre porque não enxerga limp/opener. **Validar:** o spot inferido == spot real
nos rotulados (incl. casos de limp e de open).

### Camada 5 — RANGES 6-max vs 9-max
**Problema:** caveat `TABLE_NHANDED_USING_9MAX_REF` — usa referência 9-max numa mesa
6/7-handed, desalinhando mapeamento de posição→range. **Onde:** `preflop_advisor` +
pack de ranges. **Decisão de produto:** ter ranges por tamanho de mesa, OU um
mapeamento posicional honesto 9max→6max, OU assumir e marcar (como hoje). A definir.

## Ordem recomendada
1. **Camada 2 (posições)** — keystone, destrava count_limpers e spot.
2. **Camada 3 (atribuição)** — junto, pra o par assento+valor ficar certo.
3. **Camada 4 (spot)** — cai de bônus quando 2+3 ok; validar limp/open.
4. **Camada 5 (6max/9max)** — decisão de ranges.
5. Só então **re-armar o operador** (a execução já está pronta).

## Antes de re-armar
NÃO re-armar auto-jogando até Camadas 2–4 validadas em fixtures. A execução é seca;
o olho precisa estar confiável — senão volta o T2o-call.

## Pronto e testado nesta sessão (não armar ainda)
- Raise com preset (lock_hand) + all-in pela barra (slider drag) — 17 testes.
- Leitura do valor das apostas (Camada 1) — 13+19 testes.
- Velocidade 3× (fast-path), faixa de status (`--overlay`), auto-arm (`--auto-arm`).
- Nada commitado ainda (aguardando autorização do Eduardo).
