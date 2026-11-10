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
from table_advisor import advise_table
from preflop_advisor import PreflopAdvisor
from action_executor import ActionExecutor
from action_coordinator import DryRunInput, map_advice_to_action
from position_stabilizer import PositionStabilizer
from raise_panel import target_multiplier, map_multiplier_to_preset, read_raise_panel
from raise_sequencer import RaiseSequencer
from cursor_input_win import WindowsCursorInput
from bot_control import BotControl, HotkeyListener, DISABLED, PAUSED, RUNNING
from window_capture_engine import WindowCaptureEngine
from table_discovery.pppoker import discover_pppoker

DEFAULT_RANGES = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEFAULT_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _first_button_row(frame, max_tables):
    """(crop_origin, buttons_result) do 1º crop que é vez do hero, ou (None,None)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    for prop in detect_table_crops(rgb, max_tables=max_tables):
        x, y, bw, bh = map(int, prop.box)
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
            return (x, y), br
    return None, None


def make_validator(engine, hwnd, max_tables):
    """Revalidação na chegada: a ação ainda está disponível (botão presente, vez
    do hero)? ok=True sem target_rect (usa o alvo original, evita jitter)."""
    def validator(intent, now):
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, reasons=['RECAPTURE_FAILED'])
        _, br = _first_button_row(frame, max_tables)
        if br and any(b.get('action') == intent.action for b in br['buttons']):
            return dict(ok=True)
        return dict(ok=False, reasons=['BOTAO_SUMIU_OU_NAO_E_VEZ'])
    return validator


def make_verifier(engine, hwnd, max_tables):
    """Efeito: após o clique, a linha de botões deve sumir (ação registrada)."""
    def verifier(intent, now):
        time.sleep(0.3)
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(confirmed=False)
        origin, br = _first_button_row(frame, max_tables)
        return dict(confirmed=(br is None))   # sem botões = sua vez acabou = agiu
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
                try:
                    result = advise_table(crop, advisor, stabilizer=stabilizer,
                                          table_key='%dx%d' % (x // 100, y // 100))
                except Exception:                      # noqa: BLE001
                    continue
                if not result.get('is_table'):
                    continue
                br = read_action_buttons(crop)
                if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    hero_turn_seen = True
                hand = result.get('hand') or {}
                hid = hand.get('hand_id') or hand.get('hand_number')
                adv = result.get('advice') or {}
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
                    else:
                        seq = RaiseSequencer(capture=lambda: engine.capture_frame(hwnd=args.hwnd),
                                             window_rect=win_rect, input_adapter=adapter,
                                             target_mult=tmult, bot_control=control,
                                             max_tables=args.max_tables)
                        res = seq.run()
                        raise_done.add(hid)
                        print('[%03d] >>> RAISE sequencia: %s' % (n, res.get('reason')
                              or ('preset %sx confirmado=%s' % (res.get('preset'), res.get('confirmed')))), flush=True)
                    continue
                out = executor.execute(result, br, origin=(x, y), frame_size=(fw, fh),
                                       input_adapter=adapter, validator=validator,
                                       verifier=verifier, hand_id=hid)
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
