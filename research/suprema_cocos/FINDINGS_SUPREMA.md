# Achados — captura de mão da SUPREMA (Cocos Creator + V8), fase paralela ao PPPoker

Objetivo: capturar TODAS as mãos da Suprema no formato texto Hand2Note (room
`SupremaPoker`) e alimentar o NvtTracker — o mesmo destino do PPPoker. Diferença: a
Suprema é **Cocos Creator com lógica em JavaScript (V8)**, então hookamos no PRÓPRIO JS
do jogo (muito mais fácil que offsets IL2CPP).

## O que JÁ está pronto (20/11)
- **Injeção verificada por RE** (reusada do organizador NVT-Mesas, `agents/suprema_agent.js`):
  rodar JS arbitrário no V8 do jogo pelo caminho `se::ScriptEngine::getInstance()`
  [RVA 0x2ac54] + `evalString(this, code, -1, NULL, NULL)` [RVA 0x2a85e, thiscall], na
  **main thread** (fila no hook de `?drawScene@Director@cocos2d@@QAEXXZ`). Processo = `SupremaPoker.exe`,
  módulo `libcocos2d.dll`. Confirmado que o namespace **`spp.*`** existe (ex.: `spp.enableResizeHorizontally`).
- **Downstream agnóstico de sala:** `hand_history_emit.emit_hand` e `HandAccumulator` agora
  aceitam `room` → a MESMA pipeline (acumulador→emit→`hand_text_sink`→watcher NvtTracker)
  serve a Suprema. Provado: mão com `room='SupremaPoker'` passa no parser ESTRITO do NvtTracker (saldo 0).
- **Ponte de saída:** `suprema_capture_agent.js` hooka o log nativo (OutputDebugStringA/W) e
  encaminha ao Python só as linhas marcadas `[[NVT]]` que o JS injetado emite (via `send()`).
- **Recon:** `inject_recon.js` instala `globalThis.__nvt` (dump/shape/findHandlers/hookfn/hookWS)
  e faz o recon inicial. Runner `recon_suprema.py` (anexa, injeta, imprime [evt], aceita
  comandos `__nvt.*` do teclado p/ iterar ao vivo).

## O QUE FALTA (só com a Suprema ABERTA — recon ao vivo)
Mesma lógica do PPPoker, porém em JS:
1. Rodar `python -I recon_suprema.py`, entrar numa MESA e jogar 1 mão até o showdown.
2. Ver em `[evt]`: `hello` (quais globals existem), `shape spp`, `findHandlers spp`, tráfego `ws`.
3. Achar o DISPATCH de mensagens do servidor (candidatos: um método em `spp` que casa
   `on*/recv/dispatch/handle/message/notify`, ou o `onmessage` do WebSocket). Hookar com
   `__nvt.hookfn('<path>','<metodo>')` e observar os `call` numa mão real.
4. Mapear as mensagens do FLUXO DA MÃO (análogo aos `*BRC`/`*RSP` do PPPoker):
   - início da mão / deal (botão, blinds, assentos→conta, stacks)
   - cartas do herói
   - cada AÇÃO (assento, tipo fold/check/call/bet/raise/all-in, valor)
   - board por rua (flop/turn/river)
   - showdown (cartas reveladas) e ganhador/pote
5. Se `console.log` NÃO cair em OutputDebugString neste build, usar `agent.logExports()` p/
   achar o canal de log do libcocos2d e `agent.hookLogAt(addr)`.

## Plano de implementação depois do recon
- Escrever `inject_emit.js`: hooka as mensagens decodificadas e emite EVENTOS NORMALIZADOS
  (o MESMO contrato do PPPoker, p/ reusar o acumulador):
  `{t:'round_start', stage, cur_blind, board, hero_cards, button_seat, hand_id, datetime}`,
  `{t:'hand_card', cards}`, `{t:'action', seat, atype, chips, hand_chips}`, `{t:'ante', ...}`,
  `{t:'winner', collected, total_pot}`.  (atype segue o enum de `ppp_actions`; se a Suprema
  usar outro, traduzir no JS p/ esse enum.)
- `capturar_maos_suprema.py` (já esqueleto): anexa, injeta `inject_emit.js`, roteia os
  eventos p/ `HandAccumulator(room='SupremaPoker', ...)` → `.txt` → NvtTracker.
- Validar round-trip com `hand_history`/`nlhe_text` (fixtures), como no PPPoker.

## Notas / riscos
- Multi-mesa: a Suprema abre 1 processo por janela (`allow_multiple`) — provável 1 V8 por
  processo, então o discriminador de mesa é o PID (mais simples que o PPPoker single-process).
  Confirmar ao vivo.
- Atachar o Frida já instrumenta o processo (parte "invasiva"); tudo READ-ONLY (observa, não
  joga). Ver [[nvt-hotkeys-politica]]. O conversor externo que o usuário usava faz equivalente.
- Encoding de cartas e enum de ações da Suprema podem diferir do PPPoker — mapear no recon.
