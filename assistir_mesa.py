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


def advise_frame(frame_bgr, meta, advisor, max_tables=6):
    """Detect the tables in one captured frame and advise each. Returns a list of
    {table_index, box, result}. Pure read; the full table identity still comes
    from the capture metadata upstream."""
    proposals = detect_table_crops(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB),
                                   blockers=meta.get('blockers', ()), max_tables=max_tables)
    out = []
    for i, proposal in enumerate([p for p in proposals if p.status == 'COMPLETE_CANDIDATE'], 1):
        x, y, w, h = map(int, proposal.box)
        crop = frame_bgr[y:y + h, x:x + w]
        with ocr_frame():
            result = advise_table(crop, advisor)
        out.append(dict(table_index=i, box=[x, y, w, h], result=result))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True, help='HWND da janela PPPoker')
    p.add_argument('--ranges', required=True, help='nvt-ranges-validados.json')
    p.add_argument('--deep', default=None, help='Pacote deep 40/100bb opcional (reference, nao validado)')
    p.add_argument('--intervalo', type=float, default=2.0, help='Segundos entre leituras')
    p.add_argument('--max-tables', type=int, default=6)
    args = p.parse_args(argv)
    advisor = PreflopAdvisor.from_files(args.ranges, args.deep) if args.deep else PreflopAdvisor.from_file(args.ranges)
    from window_capture_engine import WindowCaptureEngine
    engine = WindowCaptureEngine()
    configure_ocr()
    print('CONSELHEIRO AO VIVO: somente leitura, sem cliques, sem execucao. Ctrl+C encerra.', flush=True)
    try:
        while True:
            started = time.monotonic()
            frame, meta = engine.capture_frame(hwnd=args.hwnd)
            if frame is None:
                print('SEM LEITURA:', meta.get('status', 'CAPTURE_FAILED'), flush=True)
            else:
                tables = advise_frame(frame, meta, advisor, max_tables=args.max_tables)
                if not tables:
                    print('Nenhuma mesa completa localizada neste frame.', flush=True)
                for row in tables:
                    print('--- Mesa %d ---' % row['table_index'], flush=True)
                    print(_summary(row['result']), flush=True)
            time.sleep(max(0.1, args.intervalo - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print('Encerrado. Nenhuma imagem salva, nenhum clique enviado.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
