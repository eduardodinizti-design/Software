"""Leitura por ROI da grade organizada (PPPoker Unity, mesas tiladas).

PROBLEMA: depois do auto-organizar, as mesas do PPPoker ficam menores e COLADAS
dentro da mesma janela Unity; `detect_table_crops` (calibrado p/ mesa portrait em
tamanho cheio) OSCILA — ora acha, ora pega o lobby. A leitura em si (advise_table)
é correta quando recebe o recorte certo; o que falha é ACHAR o recorte.

SOLUÇÃO: ancorar no FELT AZUL das mesas. Máscara de azul (B dominante) + projeção
de COLUNAS: cada corrida contínua de colunas "cheias" de felt é uma mesa (mesas
coladas não separam por morfologia, mas o vale entre elas na projeção, sim). A
bbox de cada corrida, expandida p/ pegar título (cima) e hero+botões (baixo), é a
ROI daquela mesa. Determinístico frame-a-frame (validado ao vivo 12/11: 14/14).

`x_min` exclui a janela do lobby (à esquerda). Calibrado no layout 2-up do club
Karekas (v228, DPI 1.5, frame 5760×2160). Outro layout pode exigir ajustar os
limiares; a técnica (felt azul + projeção de colunas) é geral.
"""
import numpy as np


def felt_table_rois(frame_bgr, *, x_min=2760, col_thr=180, min_w=420, gap_tol=40,
                    row_thr=50):
    """ROIs (x, y, w, h) das mesas por felt azul, segmentando por projeção de
    colunas. Retorna da esquerda p/ direita. Não lê nada; só localiza."""
    fh, fw = frame_bgr.shape[:2]
    b = frame_bgr[:, :, 0].astype(int)
    g = frame_bgr[:, :, 1].astype(int)
    r = frame_bgr[:, :, 2].astype(int)
    blue = ((b > 90) & (b > r + 25) & (b > g + 10) & (g > 40)).astype(np.uint8)
    if x_min:
        blue[:, :min(x_min, fw)] = 0
    col = blue.sum(axis=0)
    full = col >= col_thr

    # corridas contínuas de colunas cheias, tolerando buracos <= gap_tol
    runs, start, gap = [], None, 0
    for xi in range(fw):
        if full[xi]:
            if start is None:
                start = xi
            gap = 0
        elif start is not None:
            gap += 1
            if gap > gap_tol:
                runs.append((start, xi - gap))
                start = None
    if start is not None:
        runs.append((start, fw - 1))

    rois = []
    for x0, x1 in runs:
        w = x1 - x0
        if w < min_w:
            continue
        band = blue[:, x0:x1]
        rows = np.where(band.sum(axis=1) > row_thr)[0]
        if rows.size == 0:
            continue
        y0, y1 = int(rows.min()), int(rows.max())
        h = y1 - y0
        ex, etop, ebot = int(0.04 * w), int(0.10 * h), int(0.16 * h)
        X, Y = max(0, x0 - ex), max(0, y0 - etop)
        W, H = min(fw - X, w + 2 * ex), min(fh - Y, h + etop + ebot)
        rois.append((X, Y, W, H))
    return sorted(rois, key=lambda bb: bb[0])


def _cli():
    import argparse
    import time
    import cv2
    from table_reading.pipeline import configure_ocr
    from table_reading.action_buttons import read_action_buttons
    from window_capture_engine import WindowCaptureEngine
    from table_advisor import advise_table
    from preflop_advisor import PreflopAdvisor

    DEFAULT_RANGES = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
    p = argparse.ArgumentParser(description='Leitura ao vivo por ROI de felt (mesas organizadas)')
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True)
    p.add_argument('--ranges', default=DEFAULT_RANGES)
    p.add_argument('--x-min', type=int, default=2760, help='corta o lobby à esquerda')
    p.add_argument('--frames', type=int, default=20)
    p.add_argument('--intervalo', type=float, default=0.8)
    args = p.parse_args()

    configure_ocr()
    advisor = PreflopAdvisor.from_file(args.ranges)
    eng = WindowCaptureEngine()
    for n in range(1, args.frames + 1):
        fr, _ = eng.capture_frame(hwnd=args.hwnd)
        if fr is None:
            print('[%02d] sem frame' % n)
            time.sleep(args.intervalo)
            continue
        parts = []
        for (x, y, w, h) in felt_table_rois(fr, x_min=args.x_min):
            crop = fr[y:y + h, x:x + w]
            try:
                res = advise_table(crop, advisor, table_key='x%d' % x)
            except Exception as e:  # noqa: BLE001
                parts.append('(%d) ERRO %s' % (x, str(e)[:28]))
                continue
            if not res.get('is_table'):
                parts.append('(%d) nao-mesa' % x)
                continue
            br = read_action_buttons(crop)
            vez = br['status'] == 'EXPERIMENTAL_BUTTON_ROW'
            ts = res.get('table_state') or {}
            board = ts.get('board')
            board = board.get('cards') if isinstance(board, dict) else board
            adv = res.get('advice') or {}
            pos = (ts.get('positions') or {}).get('hero')
            parts.append('(%d) hero=%s pos=%s board=%s %s' % (
                x, res.get('hero_cards'), pos, board,
                ('VEZ!->%s %s' % (adv.get('status'),
                                  adv.get('recommended') or adv.get('reason') or '')) if vez else ''))
        print('[%02d] mesas=%d | %s' % (n, len(parts), '  ||  '.join(parts) or '(nenhuma)'), flush=True)
        time.sleep(args.intervalo)


if __name__ == '__main__':
    _cli()
