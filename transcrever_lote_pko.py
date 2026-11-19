"""Transcreve em LOTE os charts de BOUNTY/PKO do PDF 'Torneios Bounty - Ranges Práticos'
-> strategy_data/ranges_pko/*.json, com o CONTEXTO (texto da página) e summary p/ conferência.
Pega TODA imagem ~quadrada (grid 13×13) de cada página (podem ser 1-2: hero/vilão).
NÃO toca no cérebro (ingestão é passo à parte)."""
import json
import os
import re

import pymupdf

import transcrever_range_pko as pk

REPO = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.abspath(os.path.join(REPO, '..', 'Ranges E TEORIAS', 'Teoria',
                                   'Reg_Life_-_TORNEIOS_BOUNTY_-_RANGES_PRATICOS (1).pdf'))
OUT = os.path.join(REPO, 'strategy_data', 'ranges_pko')


def _grids_from_page(page, doc):
    """Todas as imagens ~quadradas (grids) da página, da maior p/ a menor."""
    out = []
    import numpy as np
    for info in page.get_images(full=True):
        pix = pymupdf.Pixmap(doc, info[0])
        if pix.n > 4:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        w, h = pix.width, pix.height
        if w > 200 and 0.8 < w / float(h) < 1.5:
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w, pix.n)[:, :, :3]
            out.append((w * h, arr.copy()))
    return [a for _, a in sorted(out, key=lambda t: -t[0])]


def _context(page):
    t = ' '.join(page.get_text().split())
    t = re.sub(r'^\d+ REG LIFE COMUNIDADE ', '', t)
    return t[:140]


def main(write=True):
    os.makedirs(OUT, exist_ok=True)
    d = pymupdf.open(PDF)
    ok, flag = [], []
    for i in range(d.page_count):
        page = d[i]
        grids = _grids_from_page(page, d)
        ctx = _context(page)
        for gi, img in enumerate(grids):
            res = pk.read_range_image(img)
            s = pk.summary(res['hands'])
            tot = sum(v['pct'] for v in s.values())
            raise_pct = s.get('raise', {}).get('pct', 0.0)
            tag = 'ok' if (abs(tot - 100) <= 3 and 3 <= raise_pct <= 97) else 'FLAG'
            line = 'p%02d#%d raise=%4.1f%% fold=%4.1f%% | %s' % (
                i + 1, gi, raise_pct, s.get('fold', {}).get('pct', 0.0), ctx[:70])
            (ok if tag == 'ok' else flag).append(line)
            if write and tag == 'ok':
                out = os.path.join(OUT, 'bounty_p%02d_%d.json' % (i + 1, gi))
                json.dump({'source': 'Bounty Ranges Praticos p%d img%d' % (i + 1, gi),
                           'context': ctx, 'tool': 'reg_life_bounty_solver',
                           'summary': s, 'hands': res['hands']},
                          open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('=== OK (%d) ===' % len(ok))
    for l in ok:
        print('  ' + l)
    if flag:
        print('\n=== FLAG (%d) — não quadrado de range / revisar ===' % len(flag))
        for l in flag:
            print('  ' + l)
    print('\nJSONs em:', OUT if write else '(dry-run)')


if __name__ == '__main__':
    import sys
    main(write='--dry' not in sys.argv)
