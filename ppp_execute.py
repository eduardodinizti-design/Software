"""CLICKER do agente PPPoker: traduz o PLANO (ação de botão) em CLIQUE FÍSICO no botão certo da
mesa. REUSA as peças validadas do operar_mesa — read_action_buttons (acha o botão na tela),
never_fold_free (nunca folda com check), rect_frame_to_screen (frame->tela), cursor físico
(adapter move_to/click_once). Single-click (FOLD/CHECK/CALL) é feito aqui; RAISE/BET (sizing
multi-etapa) delega ao executor existente (on_sizing) — nunca vira clique único errado.

Camadas:
  - PURA/testável: resolve_click(recommended, button_row) -> o que clicar (single/multistep/none).
  - VIVA (tudo injetável p/ teste): make_execute(...) compõe grab_frame -> read_buttons ->
    resolve_click -> cursor físico. DRY continua sendo decidido no agente (só chama execute se ARMADO).

LEI: clique SEMPRE cursor FÍSICO (SendInput), NUNCA background/injeção [[nvt-regra-cursor-fisico-visivel]].
Esta fase entrega o single-click testado offline; o grab_frame real + o executor de sizing são
plugados ao ARMAR (por ordem do Eduardo).
"""
from __future__ import annotations

from action_coordinator import map_advice_to_action


def resolve_click(recommended, button_row, *, to_call_bb=None):
    """O que clicar, por SLOT (posição) + a ação LEGAL que o protobuf já dá — SEM depender do OCR do
    rótulo do botão (que falha no 4K: labels vêm None, mas as CAIXAS existem). Layout do PPPoker:
    [Fold | Check/Call | Bet/Raise] (3 botões) ou [Fold | Call] (2, short all-in). O MEIO é
    sempre Check (se to_call<=0) ou Call (se to_call>0) — o mesmo botão; o protobuf desambigua.
    never_fold_free também via to_call (não via label): fold DE GRAÇA -> check. PURA. Devolve:
      {'kind':'single','action':'FOLD'|'CHECK'|'CALL','box':[x,y,w,h],'slot':i}  -> 1 clique
      {'kind':'multistep','action':'BET'|'RAISE','caveats':[...]}                -> delega ao sizing
      {'kind':'none','reason':...}                                               -> não age (seguro)"""
    if not button_row or button_row.get('status') != 'EXPERIMENTAL_BUTTON_ROW':
        return {'kind': 'none', 'reason': 'SEM_BOTOES'}
    btns = button_row.get('buttons') or []            # já vêm ordenados esquerda->direita
    n = len(btns)
    if n not in (2, 3):
        return {'kind': 'none', 'reason': 'NUM_BOTOES:%d' % n}
    free = (to_call_bb is not None and to_call_bb <= 0)
    rec = 'check' if (str(recommended).strip().lower() == 'fold' and free) else recommended
    action, caveats = map_advice_to_action(rec)
    if action is None:
        return {'kind': 'none', 'reason': 'REC_NAO_MAPEIA:%s' % recommended}
    if 'REQUIRES_SIZING_MULTISTEP' in caveats:
        return {'kind': 'multistep', 'action': action, 'caveats': caveats}
    if action == 'FOLD':
        return {'kind': 'single', 'action': 'FOLD', 'box': btns[0].get('box'), 'slot': 0}
    if action in ('CHECK', 'CALL'):
        # consistência com o protobuf: CHECK exige de graça; CALL exige aposta a pagar.
        if to_call_bb is not None and action == 'CHECK' and to_call_bb > 0:
            return {'kind': 'none', 'reason': 'INCONSISTENTE_CHECK_COM_APOSTA'}
        if to_call_bb is not None and action == 'CALL' and to_call_bb <= 0:
            return {'kind': 'none', 'reason': 'INCONSISTENTE_CALL_SEM_APOSTA'}
        return {'kind': 'single', 'action': action, 'box': btns[1].get('box'), 'slot': 1}
    return {'kind': 'none', 'reason': 'ACAO_NAO_SINGLE:%s' % action}


def make_execute(hwnd, adapter, *, grab_frame, read_buttons=None, to_screen=None,
                 on_sizing=None, log=print):
    """Compõe o `execute(plan, table_key, entry)` do agente (camada VIVA; tudo injetável p/ teste).
      grab_frame(table_key, hwnd) -> VIEW da mesa (ppp_grab.build_view) ou None:
         {crop, origin:(ox,oy), window_rect:(x,y,w,h), full_size:(fw,fh)}
      read_buttons(crop) -> button_row  (default: table_reading.action_buttons.read_action_buttons)
      to_screen(box, window_rect, frame_size) -> rect na tela (default: screen_coords.rect_frame_to_screen)
      on_sizing(plan, table_key, entry, button_row) -> resultado  (RAISE/BET; default: NÃO clica)
    O botão vem em coords do CROP -> soma o `origin` do crop antes do to_screen (senão clica torto,
    igual operar_mesa). Single-click: move_to+click_once no CENTRO. Nunca lança por erro de leitura."""
    if read_buttons is None:
        from table_reading.action_buttons import read_action_buttons as read_buttons
    if to_screen is None:
        from screen_coords import rect_frame_to_screen as to_screen

    def execute(plan, table_key, entry):
        rec = (plan or {}).get('recommended')
        view = grab_frame(table_key, hwnd)
        if view is None:
            log('[PPPexec %s] sem view da mesa -> não clica' % table_key)
            return {'state': 'NO_VIEW'}
        br = read_buttons(view['crop'])
        r = resolve_click(rec, br, to_call_bb=(plan or {}).get('to_call_bb'))
        if r['kind'] == 'none':
            log('[PPPexec %s] não clica: %s' % (table_key, r['reason']))
            return {'state': r['reason']}
        if r['kind'] == 'multistep':
            if on_sizing is None:
                log('[PPPexec %s] %s multi-etapa (sizing): executor NÃO plugado -> não clica'
                    % (table_key, r['action']))
                return {'state': 'SIZING_NAO_PLUGADO', 'action': r['action']}
            # passa a VIEW (crop+origin) p/ o sizing re-capturar o painel na MESMA região da mesa
            return on_sizing(plan, table_key, entry, br, view)
        bx, by, bw, bh = r['box']
        ox, oy = view['origin']                              # offset do crop na janela
        full = (ox + bx, oy + by, bw, bh)                    # coord no FRAME CHEIO
        sx, sy, sw, sh = to_screen(tuple(full), window_rect=view['window_rect'],
                                   frame_size=view['full_size'])
        cx, cy = int(sx + sw / 2), int(sy + sh / 2)
        adapter.move_to(cx, cy)          # LEI: cursor físico (move antes do clique)
        adapter.click_once(cx, cy)
        log('[PPPexec %s] CLIQUE %s em (%d,%d)' % (table_key, r['action'], cx, cy))
        return {'state': 'CLICKED', 'action': r['action'], 'xy': (cx, cy)}

    return execute
