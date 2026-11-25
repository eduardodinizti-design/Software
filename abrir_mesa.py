"""Clica um BOTAO VERDE por texto (ex.: "Entrar" p/ abrir a mesa, "Voltar" p/
voltar ao lobby). REGRA do Eduardo: SEMPRE apos registrar -> Entrar -> Voltar ->
organizar. Mesmo motor gated; --auto-arm arma direto (RUNNING). NAO gasta ficha."""
import argparse
import sys

import cv2
import numpy as np

from bot_control import BotControl
from cursor_input_win import WindowsCursorInput
from window_capture_engine import WindowCaptureEngine
from table_reading.pipeline import configure_ocr
from registrar_armado import _ocr_line, _click_step


def find_green_button(frame, needle):
    """(x,y,w,h) do botao verde cujo texto contem `needle` (minusculo), ou None."""
    needle = needle.lower()
    fh, fw = frame.shape[:2]
    b = frame[:, :, 0].astype(int)
    g = frame[:, :, 1].astype(int)
    r = frame[:, :, 2].astype(int)
    green = ((g > 110) & (g > r + 30) & (g > b + 10) & (r < 150)).astype(np.uint8) * 255
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(green, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w > 0.05 * fw and h > 0.015 * fh and w > 3 * h and y > 0.5 * fh:
            txt = _ocr_line(cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY))
            if needle in txt.lower():
                if best is None or area > best[4]:
                    best = (int(x), int(y), int(w), int(h), int(area))
    return best[:4] if best else None


def main(argv=None):
    p = argparse.ArgumentParser(description='Clica um botao verde por texto (Entrar/Voltar).')
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True)
    p.add_argument('--button', default='entrar', help='texto do botao: entrar | voltar | ...')
    p.add_argument('--auto-arm', action='store_true')
    args = p.parse_args(argv)

    configure_ocr()
    engine = WindowCaptureEngine()
    adapter = WindowsCursorInput()
    control = BotControl()
    if args.auto_arm:
        control.resume()

    needle = args.button.lower()
    frame, _ = engine.capture_frame(hwnd=args.hwnd)
    if frame is None:
        print('SEM FRAME'); return 1
    if find_green_button(frame, needle) is None:
        print('Botao "%s" NAO encontrado na tela.' % args.button); return 1

    def locator(f):
        return find_green_button(f, needle)

    def verify_gone(_i, _n):
        f, _ = engine.capture_frame(hwnd=args.hwnd)
        if f is None:
            return dict(confirmed=False)
        return dict(confirmed=find_green_button(f, needle) is None)

    print('[%s] clicando...' % args.button)
    r = _click_step(engine, args.hwnd, locate_frame_rect=locator,
                    source_key='btn:%s' % needle, adapter=adapter, control=control,
                    verifier=verify_gone, label=needle)
    print('   ->', r['state'], r.get('reasons') or '')
    ok = r['state'] in ('DONE', 'UNKNOWN_RESULT')
    print('*** OK: "%s" clicado ***' % args.button if ok else '*** "%s" NAO confirmado ***' % args.button)
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
