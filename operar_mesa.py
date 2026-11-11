"""Operar a mesa (passo 3) — lê, decide e CLICA Fold/Call/Check, com travas.

DEFAULT = DRY-RUN (não envia clique; só mostra a intenção). Com `--arm` usa o
cursor REAL, mas só clica com o BotControl em RUNNING. Começa PAUSADO: aperte
Ctrl+Alt+R para ARMAR, Ctrl+Alt+P para pausar (você assume), Ctrl+Alt+D desabilita.
Só Fold/Call/Check (clique único); Raise/Bet/all-in ficam de fora (sizing depois).
Uma ação por mão. Revalida na chegada e verifica o efeito.

Uso:
  python operar_mesa.py --hwnd 0x...              # dry-run (seguro)
  python operar_mesa.py --hwnd 0x... --arm        # arma (ainda precisa Ctrl+Alt+R)
"""
import argparse
import sys
import time

import cv2

from table_reading.pipeline import configure_ocr
from table_reading.automatic_table_crops import detect_table_crops
from table_reading.action_buttons import read_action_buttons
from table_reading.hand_tracking import read_hand_id
from table_advisor import advise_table
from postflop_advisor import advise_postflop
from preflop_advisor import PreflopAdvisor, infer_spread
from preflop_context import PreflopAggressorTracker, villain_postflop_range
from action_executor import ActionExecutor
from action_coordinator import DryRunInput, map_advice_to_action, decision_identity
from position_stabilizer import PositionStabilizer
from screen_coords import rect_frame_to_screen
from raise_panel import target_multiplier, map_multiplier_to_preset, read_raise_panel
from raise_sequencer import RaiseSequencer
from cursor_input_win import WindowsCursorInput
from bot_control import BotControl, HotkeyListener, DISABLED, PAUSED, RUNNING
from window_capture_engine import WindowCaptureEngine
from table_discovery.pppoker import discover_pppoker

DEFAULT_RANGES = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEFAULT_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _discover_rect(hwnd):
    """Geometria lógica ATUAL da janela (None se sumiu) — p/ continuidade entre etapas."""
    ws = [w for w in discover_pppoker().get('windows', []) if w['hwnd'] == hwnd]
    return (ws[0]['x'], ws[0]['y'], ws[0]['w'], ws[0]['h']) if ws else None


def _table_key(x, y):
    """Chave estável de mesa pela origem do crop (robusta a jitter de poucos px).
    NÃO é índice do recorte (que pode reordenar)."""
    return '%dx%d' % (x // 100, y // 100)


def _first_button_row(frame, max_tables):
    """(crop_origin, buttons_result) do 1º crop que é vez do hero, ou (None,None)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    for prop in detect_table_crops(rgb, max_tables=max_tables):
        x, y, bw, bh = map(int, prop.box)
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
            return (x, y), br
    return None, None


def _find_table_by_key(frame, max_tables, want_key):
    """Acha o crop cuja chave bate com `want_key` (a MESMA mesa), ou None. Não usa
    a 1ª linha de botões qualquer — não valida uma mesa com os botões de outra."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    for prop in detect_table_crops(rgb, max_tables=max_tables):
        x, y, bw, bh = map(int, prop.box)
        if _table_key(x, y) == want_key:
            return (x, y, bw, bh)
    return None


def make_validator(engine, hwnd, max_tables):
    """Revalidação ligada à INTENÇÃO: mesma janela (geometria FRESCA), MESMA mesa
    (por chave), vez do hero, o botão da ação e o VALOR esperado. Devolve
    `target_rect` (coord de tela com a geometria atual) e `identity` (assinatura da
    decisão) — o CursorController cancela em TARGET_MOVED/IDENTITY_CHANGED, inclusive
    quando o valor do Call muda com o botão na mesma coordenada."""
    def validator(intent, now):
        exp = intent.expected or {}
        want_key = exp.get('table_key')
        wins = [w for w in discover_pppoker().get('windows', []) if w['hwnd'] == hwnd]
        if not wins:
            return dict(ok=False, reasons=['JANELA_SUMIU'])         # geometria velha não vale
        w = wins[0]
        win_rect = (w['x'], w['y'], w['w'], w['h'])
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, reasons=['RECAPTURE_FAILED'])
        fh, fw = frame.shape[:2]
        box = _find_table_by_key(frame, max_tables, want_key)
        if box is None:
            return dict(ok=False, reasons=['MESA_ALVO_NAO_ENCONTRADA'])
        x, y, bw, bh = box
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        if br['status'] != 'EXPERIMENTAL_BUTTON_ROW':
            return dict(ok=False, reasons=['NAO_E_VEZ_DO_HERO'])
        btn = next((b for b in br['buttons'] if b.get('action') == intent.action), None)
        if btn is None:
            return dict(ok=False, reasons=['BOTAO_SUMIU'])
        tx, ty, tw, th = btn['box']
        rect = rect_frame_to_screen((x + tx, y + ty, tw, th), window_rect=win_rect,
                                    frame_size=(fw, fh))
        # RELÊ a mão na chegada (não ecoa a esperada): se a mão mudou, a identidade
        # diverge do source_key e o controlador cancela (IDENTITY_CHANGED) — não clica
        # numa mão nova. Mão ilegível vira identidade != esperada -> também cancela.
        cur = read_hand_id(frame[y:y + bh, x:x + bw])
        cur_hand = cur.get('hand_id') or cur.get('hand_number')
        identity = decision_identity(want_key, cur_hand, intent.action,
                                     btn.get('amount'), btn.get('unit'))
        return dict(ok=True, target_rect=rect, identity=identity)
    return validator


# Leituras que PROVAM positivamente que a linha de ação sumiu numa mesa legível
# (não é a vez do hero). Erros de leitura (INVALID_CROP/CROP_TOO_SMALL) e a linha
# ainda presente NÃO contam — ausência por OCR/cobertura != ação executada.
_ROW_GONE_STATUSES = ('NO_BUTTON_ROW', 'PRESELECTION_ROW')


def make_verifier(engine, hwnd, max_tables):
    """Efeito na MESMA mesa: a linha de ação sumiu, com evidência POSITIVA. Ausência
    de botões por OCR/cobertura/troca de tela NÃO confirma (confirmed=False) — só um
    read limpo sem linha de ação (NO_BUTTON_ROW/PRESELECTION_ROW) confirma. O
    controlador trata não-confirmado como UNKNOWN_RESULT e não repete."""
    def verifier(intent, now):
        time.sleep(0.3)
        exp = intent.expected or {}
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(confirmed=False)
        box = _find_table_by_key(frame, max_tables, exp.get('table_key'))
        if box is None:
            return dict(confirmed=False)                 # não achei a mesa -> não confirmo
        x, y, bw, bh = box
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        return dict(confirmed=br.get('status') in _ROW_GONE_STATUSES)
    return verifier


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True)
    p.add_argument('--ranges', default=DEFAULT_RANGES)
    p.add_argument('--deep', default=None)
    p.add_argument('--frames', type=int, default=0, help='0 = até Ctrl+C/Disable')
    p.add_argument('--intervalo', type=float, default=1.0)
    p.add_argument('--max-tables', type=int, default=6)
    p.add_argument('--arm', action='store_true', help='Usa o cursor REAL (ainda gated)')
    p.add_argument('--no-hotkeys', dest='hotkeys', action='store_false')
    args = p.parse_args(argv)

    import os
    configure_ocr()
    deep = args.deep or (DEFAULT_DEEP if os.path.exists(DEFAULT_DEEP) else None)
    advisor = (PreflopAdvisor.from_files(args.ranges, deep) if deep
               else PreflopAdvisor.from_file(args.ranges))
    wins = [w for w in discover_pppoker()['windows'] if w['hwnd'] == args.hwnd]
    if not wins:
        print('Janela nao encontrada.'); return 1
    w = wins[0]
    win_rect = (w['x'], w['y'], w['w'], w['h'])

    engine = WindowCaptureEngine()
    control = BotControl(on_change=lambda s: print('\n>>> BOT %s <<<\n' % s, flush=True))
    listener = HotkeyListener(control) if args.hotkeys else None
    if listener:
        listener.start()
    adapter = WindowsCursorInput() if args.arm else DryRunInput()
    executor = ActionExecutor(window_rect=win_rect, bot_control=control, armed=args.arm)
    raise_done = set()   # uma sequência de aumento por mão
    stabilizer = PositionStabilizer()   # suaviza posições (anti-flicker HJ<->UTG+2)
    aggr_tracker = PreflopAggressorTracker()   # lembra o agressor pré-flop (p/ equity pós-flop)
    validator = make_validator(engine, args.hwnd, args.max_tables)
    verifier = make_verifier(engine, args.hwnd, args.max_tables)

    print('OPERAR MESA | modo=%s | %s' % (
        'ARMADO (cursor REAL)' if args.arm else 'DRY-RUN (sem clique)',
        'comeca PAUSADO: Ctrl+Alt+R arma, P pausa, D desabilita' if args.hotkeys
        else 'sem hotkeys'), flush=True)
    print('Travas: so Fold/Call/Check; 1 acao por mao; revalida na chegada; verifica efeito.',
          flush=True)

    n = 0
    try:
        while args.frames == 0 or n < args.frames:
            n += 1
            t0 = time.monotonic()
            if control.state == DISABLED:
                print('Desabilitado. Encerrando. Nenhum clique a mais.', flush=True)
                break
            frame, meta = engine.capture_frame(hwnd=args.hwnd)
            if frame is None:
                time.sleep(max(0.1, args.intervalo - (time.monotonic() - t0)))
                continue
            fh, fw = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            crops = list(detect_table_crops(rgb, max_tables=args.max_tables))
            hero_turn_seen = False
            for prop in crops:
                x, y, bw, bh = map(int, prop.box)
                crop = frame[y:y + bh, x:x + bw]
                tkey = _table_key(x, y)
                try:
                    result = advise_table(crop, advisor, stabilizer=stabilizer, table_key=tkey)
                except Exception:                      # noqa: BLE001
                    continue
                if not result.get('is_table'):
                    continue
                # Rastreia o agressor pré-flop e, no pós-flop HU (pote de um raise só),
                # recalcula o conselho com EQUITY vs o range de open do vilão. O contexto
                # usado vem dos frames ANTERIORES (o agressor é fixado no pré-flop); depois
                # atualiza o rastreador com este frame.
                tstate = result.get('table_state') or {}
                rboard = result.get('board') or {}
                has_board = bool(rboard.get('cards'))
                rhand = result.get('hand') or {}
                hkey = rhand.get('hand_id') or rhand.get('hand_number')
                # ATUALIZA o rastreador ANTES de consultar o contexto: numa nova mão
                # cujo 1o frame legível já é o flop, o update reinicia a identidade e
                # o contexto não vaza agressor/range da mão anterior (#2).
                aggr_tracker.update(table_key=tkey, hand_key=hkey,
                                    table_state=tstate, has_board=has_board)
                if has_board and result.get('hero_cards') and \
                        (result.get('advice') or {}).get('phase') == 'postflop':
                    ctx = aggr_tracker.context(tkey)
                    cmode = (result.get('context') or {}).get('mode', 'chip_ev')
                    cstage = (result.get('context') or {}).get('stage', 'mid')
                    seats = tstate.get('seats') or {}
                    spread = (infer_spread({p: (seats.get(s) or {}).get('stack_bb')
                                            for s, p in (tstate.get('positions') or {}).items()})
                              if cmode in ('icm', 'pko_icm') else None)
                    # Tipo de pote (gating honesto): 3bet/multiway -> abstém rotulado;
                    # um raise só -> equity (se houver range) ou Fase 1; desconhecido -> Fase 1.
                    if ctx is None:
                        ptype = 'unknown'
                    elif not ctx['heads_up']:
                        ptype = 'multiway'
                    elif ctx['raises'] >= 2:
                        ptype = 'three_bet'
                    elif ctx['raises'] == 1:
                        ptype = 'single_raised'
                    else:
                        ptype = 'unknown'
                    combos, meta = villain_postflop_range(
                        advisor, ctx, mode=cmode, stage=cstage, spread=spread,
                        hero_stack_bb=(seats.get('hero') or {}).get('stack_bb'))
                    result['advice'] = advise_postflop(
                        tstate, result['hero_cards'], rboard['cards'],
                        street=rboard.get('street'), mode=cmode, stage=cstage,
                        aggressor=(ctx or {}).get('aggressor'),
                        villain_range=(combos or None), pot_type=ptype)
                br = read_action_buttons(crop)
                if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    hero_turn_seen = True
                hand = result.get('hand') or {}
                hid = hand.get('hand_id') or hand.get('hand_number')
                adv = result.get('advice') or {}
                if adv.get('phase') == 'postflop':
                    # Pós-flop é SÓ conselho exploratório. O operador armado joga
                    # pré-flop apenas e NUNCA executa pós-flop (sem clique, sem
                    # sequência de aumento) até ser validado à parte.
                    if br['status'] == 'EXPERIMENTAL_BUTTON_ROW' and adv.get('status') == 'ADVICE':
                        eqtxt = ''
                        if adv.get('equity') is not None:
                            eqtxt = ' | eq=%.0f%% vs pot_odds=%.0f%%' % (
                                adv['equity'] * 100, (adv.get('pot_odds') or 0) * 100)
                        print('[%03d] vez do hero PÓS-FLOP (%s): %s %s%s | sem execucao (exploratorio)'
                              % (n, adv.get('street'), str(adv.get('recommended')).upper(),
                                 adv.get('made') or '', eqtxt), flush=True)
                    elif br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                        print('[%03d] vez do hero PÓS-FLOP (%s): ABSTEM %s | mao=%s | sem execucao'
                              % (n, adv.get('street'), adv.get('reason'), adv.get('made')), flush=True)
                    continue
                _, caveats = map_advice_to_action(adv.get('recommended'))
                is_raise = 'REQUIRES_SIZING_MULTISTEP' in caveats
                # RAISE = fluxo multi-etapa (sequenciador). Só executa ARMADO (em
                # dry-run os cliques não abrem o painel de verdade).
                if (br['status'] == 'EXPERIMENTAL_BUTTON_ROW' and adv.get('status') == 'ADVICE'
                        and is_raise and hid not in raise_done):
                    tmult = target_multiplier(adv, result.get('table_state'))
                    if tmult is None:
                        print('[%03d] vez do hero: RAISE sem target de size -> abstem' % n, flush=True)
                    elif not args.arm:
                        pr = map_multiplier_to_preset(tmult, read_raise_panel(crop).get('presets') or [])
                        print('[%03d] vez do hero: RAISE alvo %.2fx (preset %s) | DRY-RUN: sequencia so executa armada'
                              % (n, tmult, (pr and pr['label']) or '?'), flush=True)
                    elif not control.execution_allowed():
                        print('[%03d] RAISE mas BOT PAUSADO' % n, flush=True)
                    elif not adv.get('validated'):
                        # Autorização única também no RAISE: nó não validado
                        # (referência/deep) não dispara a sequência armada (só estuda).
                        print('[%03d] RAISE de no NAO VALIDADO -> nao executa (so estuda)' % n, flush=True)
                    else:
                        seq = RaiseSequencer(capture=lambda: engine.capture_frame(hwnd=args.hwnd),
                                             window_rect=lambda: _discover_rect(args.hwnd),
                                             input_adapter=adapter, target_mult=tmult,
                                             bot_control=control, table_key=tkey, hand=hid,
                                             max_tables=args.max_tables)
                        res = seq.run()
                        raise_done.add(hid)
                        print('[%03d] >>> RAISE sequencia: %s' % (n, res.get('reason')
                              or ('preset %sx confirmado=%s' % (res.get('preset'), res.get('confirmed')))), flush=True)
                    continue
                out = executor.execute(result, br, origin=(x, y), frame_size=(fw, fh),
                                       input_adapter=adapter, validator=validator,
                                       verifier=verifier, hand_id=hid, table_key=tkey)
                if out.get('acted'):
                    pl = out['plan']
                    print('[%03d] >>> AGIU: %s em %s | estado=%s %s %s' % (
                        n, pl['action'],
                        tuple(round(c) for c in pl.get('screen_center', pl['center'])),
                        out['state'], 'DRY-RUN' if out['dry_run'] else 'REAL',
                        out['reasons'] or ''), flush=True)
                elif br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    # Vez do hero mas NÃO agiu (raise multi-etapa / abstenção / já agiu):
                    # mostra a decisão para a demo.
                    adv = result.get('advice') or {}
                    pos = (result.get('table_state', {}).get('positions') or {}).get('hero')
                    print('[%03d] vez do hero: %s %s | conselho=%s %s | executor: %s' % (
                        n, result.get('hero_cards'), pos, adv.get('status'),
                        adv.get('recommended') or adv.get('reason') or '',
                        out.get('reason')), flush=True)
            # heartbeat: a cada ~8 frames sem vez-do-hero, mostra que está vivo
            if not hero_turn_seen and n % 8 == 0:
                print('[%03d] . vivo | mesas=%d | sua vez: nao | estado=%s'
                      % (n, len(crops), control.state), flush=True)
            time.sleep(max(0.1, args.intervalo - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        print('Encerrado pelo usuario.', flush=True)
    finally:
        if listener:
            listener.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
