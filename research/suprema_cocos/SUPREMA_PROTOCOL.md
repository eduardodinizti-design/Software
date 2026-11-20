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

## Codificação de carta (a confirmar offline com +amostras)
- Inteiros fora de 0-51 (vi 59) → NÃO é 0-51. Padrão provável **`rank*4 + suit`** (rank 2-14, suit 0-3 →
  faixa 8..59). Ex. board visto `[36,59,39,56]`, hero `[40,23]`. Decodificar e cross-checar o naipe
  (qual índice é ♦♣♥♠) com o feltro numa captura com showdown.
- `[0,0]` = carta oculta (oponente/face-down).

## Blinds
- `sb`/`bb` NÃO apareceram nos frames de jogo — provavelmente numa mensagem de **room/config/enter**.
  Capturar o `enterRoom`/config, OU derivar da MENOR aposta de blind (`chips` do SB).

## PRÓXIMO (offline): construir o parser real
`suprema_net.py` (novo): hook SSL_read → reassembla frames WS → JSON.parse → alimenta `SupremaTable`
(suprema_state.py já existe e vira table_state). O contrato de eventos do `inject_emit.js` muda de
"hooks JS" para "parse do JSON de rede". Capturas desta sessão: `suprema_capture_full.log`,
`../../../scratchpad/diag5_out.log`.
