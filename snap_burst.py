"""Captura em RAJADA da janela PPPoker — pega painel de raise / linha de 2 botoes
transitorios durante a vez do hero. Uso:
    python snap_burst.py 0xae0902 20 0.25
(hwnd, n_frames, intervalo_s). Salva PNGs numerados + imprime o caminho. Passivo:
NAO clica, so captura."""
import sys
import time
from pathlib import Path

import cv2

from window_capture_engine import WindowCaptureEngine

OUT = Path(r'C:\Users\tacao\AppData\Local\Temp\claude\14f5907446636a6c'
           r'\d1d68cdb-3f89-455a-963d-07ea06048c7c\scratchpad\burst')


def main():
    hwnd = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0xae0902
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    gap = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
    OUT.mkdir(parents=True, exist_ok=True)
    eng = WindowCaptureEngine()
    saved = []
    for i in range(n):
        frame, meta = eng.capture_frame(hwnd=hwnd)
        if frame is not None:
            p = OUT / ('snap-%02d.png' % i)
            cv2.imwrite(str(p), frame)
            saved.append(str(p))
        time.sleep(gap)
    print('SALVOS %d frames em %s' % (len(saved), OUT))


if __name__ == '__main__':
    main()
