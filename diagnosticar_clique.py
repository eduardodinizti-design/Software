"""DIAGNÓSTICO do clique pós-leitura (Eduardo 19/11: "clique robusto").

O Henrique não clica quando `read_action_buttons` devolve NO_BUTTON_ROW — e a causa quase sempre
é o CROP da mesa (detect_table_crops) pegando o frame dividido (lobby+mesa) em vez da mesa.
Sem um FRAME REAL da sua vez é impossível consertar sem chutar. Esta ferramenta captura o
frame real com o PPPoker aberto NA SUA VEZ e mostra EXATAMENTE onde a detecção falha:

  python diagnosticar_clique.py            # acha o PPPoker, captura, roda o pipeline
  python diagnosticar_clique.py --frame X.png   # diagnostica um PNG salvo

Salva em logs/diag_clique/: o frame inteiro + cada crop + a linha de botões (se achada), e
imprime um relatório. Com isso eu finalizo o fix com DADO, não no escuro. Não clica nada."""
import argparse
import os
import sys
import time

import cv2
import numpy as np

REPO = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(REPO, 'logs', 'diag_clique')


def _save(name, rgb):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    cv2.imwrite(p, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return p


def _probe(rgb, label, from_action_buttons):
    """Roda read_action_buttons num crop e imprime o resultado."""
    br = from_action_buttons(rgb)
    st = br.get('status')
    extra = ''
    if br.get('buttons'):
        extra = ' | labels=%s' % [b.get('label') or b.get('ocr_readings') for b in br['buttons']]
    print('   %-34s %dx%d -> %s%s' % (label, rgb.shape[1], rgb.shape[0], st, extra))
    return st


def diagnose(rgb):
    from table_reading.automatic_table_crops import detect_table_crops
    from table_reading.action_buttons import read_action_buttons
    try:                                             # OCR precisa estar configurado (igual ao operador)
        from table_reading.pipeline import configure_ocr
        configure_ocr()
    except Exception:                                # noqa: BLE001
        print('[aviso] configure_ocr falhou — rótulos podem sair None')
    H, W = rgb.shape[:2]
    print('=' * 64)
    print('FRAME %dx%d (dividido lobby+mesa se W muito largo)' % (W, H))
    print('=' * 64)
    print(' frame inteiro ->', _save('frame.png', rgb))
    # 1) o caminho do operador: detect_table_crops -> read_action_buttons por crop
    try:
        from operar_mesa import find_buyin_badges
    except Exception:                                # noqa: BLE001
        find_buyin_badges = None
    crops = list(detect_table_crops(rgb, max_tables=6))
    print('\n[1] detect_table_crops: %d crop(s)' % len(crops))
    any_row = False
    for i, pr in enumerate(crops):
        x, y, w, h = map(int, pr.box)
        sub = rgb[y:y + h, x:x + w]
        _save('crop%d_%dx%d.png' % (i, w, h), sub)
        lob = ''
        if find_buyin_badges is not None:
            bgr = cv2.cvtColor(sub, cv2.COLOR_RGB2BGR)
            nb = len(find_buyin_badges(bgr))
            lob = '  [LOBBY: %d badges]' % nb if nb else '  [sem badge: mesa?]'
        st = _probe(sub, 'crop%d (x=%d y=%d)%s' % (i, x, y, lob), read_action_buttons)
        any_row = any_row or st == 'EXPERIMENTAL_BUTTON_ROW'
    # 2) fallbacks diretos no frame (quando o crop falha): metades/quadrantes/faixas
    print('\n[2] fallback (sub-regiões do frame, caso o crop falhe):')
    cands = {
        'frame inteiro': rgb,
        'metade direita': rgb[:, W // 2:],
        'metade esquerda': rgb[:, :W // 2],
        'terço direito': rgb[:, 2 * W // 3:],
        'centro-direita (33-66%)': rgb[:, W // 3: 2 * W // 3],
    }
    for name, sub in cands.items():
        if sub.shape[0] >= 250 and sub.shape[1] >= 150:
            st = _probe(sub, name, read_action_buttons)
            any_row = any_row or st == 'EXPERIMENTAL_BUTTON_ROW'
    print('\n>>> %s <<<' % ('LINHA DE BOTÕES ACHADA em algum recorte -> dá p/ clicar daí'
                            if any_row else 'NENHUM recorte achou a linha de botões '
                            '(é a sua vez? o painel está visível? mande o frame.png salvo)'))
    print('Artefatos em:', OUT)
    return any_row


def _capture_live():
    from table_discovery.pppoker import pppoker_table_hwnds
    from window_capture_engine import WindowCaptureEngine
    hs = pppoker_table_hwnds()
    if not hs:
        print('[X] PPPoker não encontrado. Abra o PPPoker (NA SUA VEZ, painel de ações visível).')
        return None
    frame, _ = WindowCaptureEngine().capture_frame(hwnd=hs[0])
    return frame


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--frame', help='diagnostica um PNG salvo em vez de capturar ao vivo')
    args = ap.parse_args(argv)
    if args.frame:
        bgr = cv2.imread(args.frame)
        if bgr is None:
            print('[X] não li', args.frame); return 1
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    else:
        rgb = _capture_live()
        if rgb is None:
            return 1
    diagnose(rgb)
    return 0


if __name__ == '__main__':
    sys.exit(main())
