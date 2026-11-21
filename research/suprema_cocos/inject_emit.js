/* inject_emit.js — JS do jogo (V8 Suprema) que HOOKA o fluxo da mão e emite EVENTOS
   NORMALIZADOS (mesmo contrato do PPPoker) p/ o HandAccumulator montar o .txt.

   ESTADO: TEMPLATE. Até os hooks reais serem plugados (depois do recon_suprema.py), este
   arquivo é NO-OP seguro — define helpers e não observa nada. Ver FINDINGS_SUPREMA.md.

   Contrato de evento (emitir com __nvt.emit, que o agente encaminha como {nvt:{...}}):
     {t:'seat',   seat, player, stack}                 // mapa assento->conta+stack (EnterRoom)
     {t:'ante',   seat, amount}
     {t:'round_start', stage(1..4), cur_blind, board:[...], hero_cards:[...], button_seat, hand_id, datetime}
     {t:'hand_card', seat, cards:[...]}                 // cartas do herói
     {t:'action', seat, atype, chips, hand_chips, all_in}   // atype = enum ppp_actions (1fold 2check 3call 7bet/raise 8sb 9bb 10ante)
     {t:'winner', collected:[[seat,amount],...], total_pot}
     {t:'hand_over'}
   Cartas: usar o MESMO encoding do decoder (ppp_cards: naipe*256+rank) OU já mandar string
   'As','Kd' (o acumulador aceita lista de strings). Decidir no recon conforme o dado da Suprema.
*/
(function () {
  var G = (typeof globalThis !== 'undefined') ? globalThis : this;
  if (!G.__nvt) { try { console.log('[[NVT]]{"emit_setup":"__nvt ausente; rode inject_recon.js antes"}'); } catch (e) {} return; }
  var E = G.__nvt;
  function emit(ev) { E.emit(ev); }

  // ---- helpers de tradução (preencher conforme o schema real da Suprema) ----
  // Ex. (quando souber o dispatch): ao receber a mensagem de ação do servidor, chamar:
  //   emit({t:'action', seat: msg.seatId, atype: mapAction(msg.type), chips: msg.amount, all_in: !!msg.allin});
  // function mapAction(supremaType){ /* traduz o enum da Suprema -> enum ppp_actions */ return supremaType; }

  // ---- PONTO DE PLUGAGEM (preencher após o recon) ----
  // Descomente/ajuste quando o dispatch da mão for identificado. Exemplos de padrão:
  //
  //  (A) via método de dispatch do spp:
  //    E.hookfn('spp', '<metodoDispatch>', 'spp.dispatch');   // só p/ observar
  //    // depois, envolver "de verdade" traduzindo cada mensagem p/ emit({t:...})
  //
  //  (B) via WebSocket/handler específico — parse do payload -> emit(...)
  //
  // Enquanto nada acima estiver ativo, este arquivo NÃO emite eventos (no-op seguro).

  try { console.log('[[NVT]]{"emit_setup":"inject_emit.js carregado (template no-op); plugue os hooks pos-recon"}'); } catch (e) {}
})();
