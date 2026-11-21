# Captura de mão do X-Poker (Cocos2d-x / GLFW) — plano

Engine (memória [[nvt-salas-engines]]): **X-Poker = Cocos2d-x / GLFW, janela externa**.
Processo: `X-Poker.exe` (ou `XPoker.exe`/`X_Poker.exe`). O NvtTracker JÁ é homologado em
X-Poker (VPIP/PFR/3Bet do 3253170), e o parser já aceita o token de sala — então o
DOWNLOAD/stats/HUD já servem. Falta a CAPTURA própria (hoje vinha do conversor externo/H2N).

## Estado
- Downstream agnóstico de sala: PRONTO (`emit_hand`/`HandAccumulator` com `room='Xpoker'`).
- Recon: `recon_xpoker.js` + `recon_xpoker.py` (READ-ONLY): identificam a engine (Cocos/Lua/JS)
  e listam os exports reveladores (ScriptEngine/eval/execute/jsb/lua/log).

## Sessão ao vivo (com X-Poker aberto numa mesa)
1. `python -I recon_xpoker.py` → ver PISTAS DE ENGINE e os exports.
2. Decidir o caminho:
   - **JS/jsb (como a Suprema):** achar `ScriptEngine::evalString`/`executeString` (export ou
     RVA por assinatura) e REUSAR o padrão da Suprema (agente evalString + inject_recon/emit).
     Boa chance de o mesmo `suprema_capture_agent.js` servir trocando EXE/RVAs.
   - **Lua:** hookar o dispatch nativo das mensagens (ou `lua_*` do handler) e ler os campos.
   - Sem export óbvio: assinatura/RVA como foi feito na Suprema (RE do binário).
3. Achar o fluxo da mão (deal/ação/board/winner) e emitir EVENTOS NORMALIZADOS (mesmo
   contrato do PPPoker/Suprema) → `HandAccumulator(room='Xpoker')` → `.txt` → NvtTracker.

## Notas
- GLFW indica janela/He render próprios; a lógica de jogo ainda é Cocos (JS ou Lua).
- Confirmar encoding de cartas e enum de ações (traduzir p/ o enum de `ppp_actions`).
