"""Live advisor: observe a PPPoker window and print the recommendation per frame.

Reuses the validated capture + table detection; for each complete table it runs
table_advisor and prints the read-out and an exploratory recommendation. It
never clicks, never sends input, and only reads. Ctrl+C stops.
"""
import argparse
import time

import cv2

from table_reading.pipeline import configure_ocr
from table_reading.ocr_runtime import ocr_frame
from table_reading.automatic_table_crops import detect_table_crops
from preflop_advisor import PreflopAdvisor
from table_advisor import advise_table, _summary
from bot_control import BotControl, HotkeyListener, RUNNING, PAUSED, DISABLED
from state_observer import StateObserver, render


def advise_frame(frame_bgr, meta, advisor, max_tables=6):
    """Detect the tables in one captured frame and advise each. Returns a list of
    {table_index, box, result}. Pure read; the full table identity still comes
    from the capture metadata upstream."""
    proposals = detect_table_crops(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB),
                                   blockers=meta.get('blockers', ()), max_tables=max_tables)
    out = []
    for proposal in [p for p in proposals if p.status == 'COMPLETE_CANDIDATE']:
        x, y, w, h = map(int, proposal.box)
        crop = frame_bgr[y:y + h, x:x + w]
        with ocr_frame():
            result = advise_table(crop, advisor)
        if result.get('is_table'):   # skip lobby/non-table false positives
            out.append(dict(table_index=len(out) + 1, box=[x, y, w, h], result=result))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True, help='HWND da janela PPPoker')
    p.add_argument('--ranges', required=True, help='nvt-ranges-validados.json')
    p.add_argument('--deep', default=None, help='Pacote deep 40/100bb opcional (reference, nao validado)')
    p.add_argument('--intervalo', type=float, default=2.0, help='Segundos entre leituras')
    p.add_argument('--max-tables', type=int, default=6)
    p.add_argument('--no-hotkeys', dest='hotkeys', action='store_false',
                   help='Desliga as hotkeys de pausa/takeover (Ctrl+Alt+P/R/D)')
    args = p.parse_args(argv)
    advisor = PreflopAdvisor.from_files(args.ranges, args.deep) if args.deep else PreflopAdvisor.from_file(args.ranges)
    from window_capture_engine import WindowCaptureEngine
    engine = WindowCaptureEngine()
    configure_ocr()
    # Pause/takeover control. The observer only reads, but the same gate is what a
    # future executor must consult before sending any input. Start armed (RUNNING).
    control = BotControl(on_change=lambda s: print('\n>>> BOT %s%s <<<\n' % (
        s, {'PAUSED': ' (voce no controle; Ctrl+Alt+R reativa)',
            'DISABLED': ' (desabilitado; Ctrl+Alt+R reativa)'}.get(s, '')), flush=True))
    control.resume()
    listener = HotkeyListener(control) if args.hotkeys else None
    if listener:
        listener.start()
    print('CONSELHEIRO AO VIVO: somente leitura, sem cliques, sem execucao. '
          'Ctrl+Alt+P pausa, R reativa, D desabilita. Ctrl+C encerra.', flush=True)
    last = {}   # per table: last printed signature, so an unchanged hand is not reprinted
    observer = StateObserver()   # estado temporal integrado (Camada A); sem cliques
    try:
        while True:
            started = time.monotonic()
            if control.state == DISABLED:
                print('Bot desabilitado. Encerrando. Nenhum clique foi enviado.', flush=True)
                break
            if control.state == PAUSED:
                # You have the tables: stay quiet (no advice). A future executor
                # gates on control.execution_allowed() here and sends nothing.
                if last.get('_control') != PAUSED:
                    last['_control'] = PAUSED
                time.sleep(max(0.1, args.intervalo - (time.monotonic() - started)))
                continue
            last.pop('_control', None)
            frame, meta = engine.capture_frame(hwnd=args.hwnd)
            if frame is None:
                if last.get('_capture') != meta.get('status'):
                    last['_capture'] = meta.get('status')
                    print('SEM LEITURA:', meta.get('status', 'CAPTURE_FAILED'), flush=True)
            else:
                last.pop('_capture', None)
                for row in advise_frame(frame, meta, advisor, max_tables=args.max_tables):
                    # Estado temporal integrado: amarra mesa/mão/campos e explica
                    # o que mudou/ficou pendente. Imprime só quando o estado muda.
                    key = '%s#%d' % (meta.get('source_key', args.hwnd), row['table_index'])
                    view = observer.observe(row['result'], table_key=key)
                    if view.get('changed'):
                        print(render(view), flush=True)
            time.sleep(max(0.1, args.intervalo - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print('Encerrado. Nenhuma imagem salva, nenhum clique enviado.', flush=True)
    finally:
        if listener:
            listener.stop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
