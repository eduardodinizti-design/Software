# Protocolo da Suprema — DESCOBERTO AO VIVO (recon 20/11/2026, read-only)

## Motor e transporte
- **Cocos Creator + V8** (JavaScript): `v8.dll`/`v8_libplatform.dll`/`v8_libbase.dll` carregados.
- O path de **injeção JS por RVA** (`se::ScriptEngine::evalString` @ RVA 0x2a85e do agente) está
  **STALE nesta build**: o eval "retorna 1 (sucesso)" mas NÃO executa de verdade (silêncio total
  em OutputDebugString, `cocos2d::log` @0x72987d9a e `LuaLog` @0x729c86ff). NÃO confiar no path JS.
- **ROTA ROBUSTA (escolhida): ler a rede.** O jogo fala com o servidor por **WebSocket sobre TLS**
  (`websockets.dll` + `libssl-1_1.dll`/`libcrypto`). Hookando **`SSL_read`/`SSL_write`** (em
  libssl-1_1.dll — `SSL_read`@0x722615a5, `SSL_write`@0x7226143d nesta sessão; resolver por NOME)
  pega-se o tráfego **JÁ DESCRIPTOGRAFADO**. É a "verdade" (análogo ao protobuf do PPPoker).

## Formato do frame
- WebSocket binário: header `82 7e <len16 BE> ...` depois sub-protocolo estilo **Pomelo/Pinus**
  (`04 00 <len16> 06 05` + rota `"onMsg"`) e então o **corpo JSON em TEXTO PURO**.
- Mensagens grandes (ex.: `moveturn` 4096+ bytes) **fragmentam** em vários `SSL_read` → o parser
  precisa **reassemblar o frame WS** (pelo length do header) antes de dar JSON.parse.

## Mensagens (event types) — `{"route":"onMsg","event":"<X>","data":{...}}`
- **`gameinfo`** → `data.game_info`: `dealer_seat`, `shared_cards:[ints]` (BOARD), `pot`, `state`,
  `game_counter`. Street pela QTD de shared_cards (0=pré,3=flop,4=turn,5=river) — mais robusto que `state`.
- **`moveturn`** → `data.game_seat`: mapa `uid -> {seat, uid, coins, cards, role, chips, chips_round,
  sitout, winnings, ...}`. É o estado dos ASSENTOS.
  - **HERÓI** = o assento cujo `cards` traz CÓDIGOS REAIS (ex.: `[40,23]`); oponentes = `null` ou `[0,0]`.
  - **stack** ≈ `coins` (33900/65251/288895...); **aposta na rua** ≈ `chips` (500=blind, 3500=raise).
    ⚠️ CONFIRMAR coins-vs-chips-vs-chips_round com captura de 1 rua limpa (hipótese atual: stack=coins, bet=chips).
- **`prompt`** → `data.gamer_prompt`: `{fold,check,call,raise,all_in,ready,bet}`. TODOS `null` quando
  NÃO é a vez do herói; quando ATIVO, viram objetos com valores (min/max/amount) = ações legais +
  sizes. (Não peguei um prompt ATIVO ainda — pegar na próxima, é o que guia a EXECUÇÃO/Fase 2.)
- Ruído p/ decisão: `matchesStatusPushNotify`, `apiClub...jackpot`, `countdown` (só {seat,sec} do timer).

## Codificação de carta — RESOLVIDA (recon 2)
- **`carta = rank*4 + suit`**, rank 2..14 (2..9,T,J,Q,K,A), suit 0..3 → faixa 8..59. Decode:
  `rank = code//4`, `suit = code%4` (bijeção; rótulo exato do naipe ♦♣♥♠ é indiferente p/ o cérebro,
  igual ao insight do ppp_cards — o que importa é naipes IGUAIS=flush, preservado por `%4`).
  Amostras: hero `[44,28]`=J?7?, `[40,23]`=T?5?; board `[36,59,39,56]`=9,A,9,A.
- `[0,0]`/`null` = carta oculta (oponente/face-down). HERÓI = assento com códigos reais.

## STACK vs BET — RESOLVIDO (recon 2)
- **`coins` = STACK (fichas ATRÁS)**, **`chips` = apostado na mão/rua**. CONFIRMADO: no all-in do hero,
  `coins`→0 e `chips`→32400 (stack inteiro). Logo **stack_bb = coins / bb**.

## PROMPT ATIVO (a vez do herói) — CAPTURADO (recon 2) — guia a EXECUÇÃO (Fase 2)
- `event:"prompt"` → `data.gamer_prompt`: cada ação é **`true`** (disponível), **`null`** (não) ou
  **string de range** p/ raise. Ex. real:
  `{"fold":true,"check":true,"call":null,"raise":"range,4000,27900,2X,4000,3X,8000,4X,12000","all_in":true,"bet":null}`
- **raise string** = `"range,<min>,<max>,<label>,<valor>,..."` → min=4000, max=27900, presets 2X=4000,
  3X=8000, 4X=12000. (`call` traz o valor a pagar quando disponível.) É o que o executor usa p/ dar o size.

## Blinds
- No frame de room/status vem `"blinds":10` (rótulo do nível; stakeRangeID=99) + `"ante":0`. O BB EFETIVO
  em fichas sai do `raise` unit (1X≈2000 no exemplo) OU dos posts de blind (`chips` do SB/BB). Derivar bb
  dos posts é o mais robusto (não confiar no rótulo `blinds`).

## PRÓXIMO (offline): construir o parser real
`suprema_net.py` (novo): hook SSL_read → reassembla frames WS → JSON.parse → alimenta `SupremaTable`
(suprema_state.py já existe e vira table_state). O contrato de eventos do `inject_emit.js` muda de
"hooks JS" para "parse do JSON de rede". Capturas desta sessão: `suprema_capture_full.log`,
`../../../scratchpad/diag5_out.log`.

## DECODIFICAÇÃO COMPLETA DO FLUXO DA MÃO (recon 21/11/2026, SSL_read ao vivo)
Eventos REAIS do ciclo da mão (o `is_game_event` antigo não incluía gamestart/gameover — corrigido):
- **`gamestart`** = INÍCIO (vem em vários frames): `game_info{dealer_seat, game_counter(=ID da mão),
  state, pot}` + `room_status.seats:[uid por índice de assento]` (None=vazio) + `game_seat{uid->
  {seat, coins(=STACK), chips(=apostado na mão), chips_round(=apostado na rua), cards, role, sitout}}`.
  - **ANTE**: no 1º frame todos com `chips=1500 round=1500` (ante=1500/jogador; pot=1500×N).
  - **BLINDS por `role`**: `role=82`=SB, `role=93`=BB; valor = `chips - ante`. Ex.: SB 6000, BB 12000.
  - **INVARIANTE-CHAVE**: `coins + chips` por assento = **stack inicial da mão** (constante até o
    gameover somar ganhos). Logo `start_stack = coins+chips` no 1º avistamento.
- **`moveturn`** / **`gameinfo`** = updates de estado. Ação do assento = **Δ(chips)** entre snapshots
  (incremento). Rua = qtd de `shared_cards` no `gameinfo` (0=pré,3=flop,4=turn,5=river). `state` 1/2=pré.
- **`gameover`** = FIM/SHOWDOWN: `game_result{allpots:[...], cards:[[board]], seats{uid->{seat, coins
  (=stack final, inclui ganho), chips(=total investido), cards(=reveladas)}}, patterns, lightcards}`.
  Ganhador = assento com `coins` final > (stack antes do showdown). ⚠️ As `cards` do gameover usam
  codificação DIFERENTE (valores >59, ex. 77) — NÃO é rank*4+suit; p/ o board usar `gameinfo.shared_cards`
  (confiável) e p/ cartas do herói o `game_seat` do fluxo. Reveladas de vilão: decodificação a resolver.
- **`KOdata`** = bounty PKO: `{loser{uid,displayID}, winners{uid,displayID,bounty,bountyTmp}}`.
- Ruído: `countdown, clientPing, matchesStatusPushNotify, apiClub.*, sendEmoji, updateOutsCards`.

### Contrato p/ o HandAccumulator (códigos ppp_actions): 1=fold,2=check,3=call,4=agressão(bet/raise/
### all-in por contexto),8=SB,9=BB,10=ante. `on_action(seat, code, chips=INCREMENTO)`. start_stack via
### set_seat; mark_hero(hero_seat); board no on_round_start(stage,board=...); winner no on_winner.
### Fixtures capturados: scratchpad/suprema_all_events.jsonl (2 mãos completas gamestart→gameover).
### PRÓXIMO: suprema_hand_builder.py (buffer por mão; constrói no gameover; conserva dinheiro) -> .txt.
