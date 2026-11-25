"""Transcritor da paleta CUSTOM Reg-Life (image.png: SB vs open, 4 paineis EP/MP/CO/BTN).
Centroides RGB medidos NESTA imagem. Mapa cor->acao (legenda):
  three_bet: verde, vermelho(3bet/fold), verde-claro(3bet/call ate30), laranja(ampliar), roxo(vs agro)
  call(flat): amarelo
  all_in(shove): azul forte
  fold: tan (celula sem acao)
Valida pela % combo-ponderada vs a legenda do chart.
"""
import numpy as np
import cv2

IMG = r'C:\Meus Projetos\Aplicativos\Ranges E TEORIAS\image.png'
RANKS = 'AKQJT98765432'
# bbox (gx,gy,gw,gh) por painel. gh=344 (NÃO 283): o grid é ~QUADRADO (célula ~26px); 283 dava
# ch=21.77 e as linhas de baixo amostravam a de cima (JTo lia JJ verde, ATo lia AJo). Medido pela
# varredura das bandas de cor (grid de y31 a y~375). Eduardo 24/11 — correção da precisão SB.
PANELS = [(9, 31, 349, 344), (377, 31, 349, 344), (745, 31, 349, 344), (1113, 31, 349, 344)]
PANEL_NAMES = ['SB x EP', 'SB x MP', 'SB x CO', 'SB x BTN']

# (centroide RGB, acao)
_CENT = [
    ((8, 144, 7), 'three_bet'),      # verde
    ((214, 9, 8), 'three_bet'),      # vermelho (3bet/fold)
    ((244, 5, 4), 'three_bet'),
    ((153, 251, 154), 'three_bet'),  # verde claro (3bet/call ate 30)
    ((212, 113, 18), 'three_bet'),   # laranja (ampliar)
    ((153, 153, 250), 'three_bet'),  # roxo (3bet-call vs agro)
    ((251, 251, 56), 'call'),        # amarelo (flat)
    ((229, 226, 63), 'call'),
    ((53, 53, 220), 'all_in'),       # azul forte (shove)
    ((234, 205, 185), 'fold'),       # tan (sem acao)
    ((216, 189, 172), 'fold'),
    ((207, 172, 155), 'fold'),
    ((194, 169, 154), 'fold'),
]


def hand_at(r, c):
    if r == c:
        return RANKS[r] * 2
    if c > r:
        return RANKS[r] + RANKS[c] + 's'
    return RANKS[c] + RANKS[r] + 'o'


def _combos(h):
    return 6 if h[0] == h[1] else (4 if h.endswith('s') else 12)


_CARR = np.array([c for c, _ in _CENT], dtype=float)
_CACT = [a for _, a in _CENT]


def _cell_freq(rgb, cx, cy, cw, ch):
    """Fração de cada AÇÃO na célula (pixels classificados por centroide mais próximo).
    Célula MISTA (ex.: TT metade flat/metade 3bet) vira {call:.5, three_bet:.5}. REFINADO 2x
    (precisão SB, Eduardo 24/11): amostra as FAIXAS LATERAIS (esquerda+direita) no meio vertical.
    Evita (a) o texto central (rótulo da mão), (b) as bordas topo/base — onde a célula de CIMA/BAIXO
    vazava quando o grid desalinha 1px (era o bug do JTo lido 3bet por estar abaixo do JJ verde)."""
    y0 = int(cy + 0.22 * ch); y1 = int(cy + 0.80 * ch)    # meio vertical (sem bleed topo/base)
    left = rgb[y0:y1, int(cx + 0.08 * cw):int(cx + 0.30 * cw)].reshape(-1, 3)   # faixa esq. (sem texto)
    right = rgb[y0:y1, int(cx + 0.70 * cw):int(cx + 0.92 * cw)].reshape(-1, 3)  # faixa dir. (sem texto)
    parts = [p for p in (left, right) if p.size]
    patch = np.concatenate(parts).astype(float) if parts else left.astype(float)
    mx = patch.max(1); mn = patch.min(1)
    keep = patch[(mx > 55) & ~((mx > 195) & ((mx - mn) < 30))]   # tira borda preta e texto branco
    if len(keep) < 8:
        return {'fold': 1.0}
    d = np.sqrt(((keep[:, None, :] - _CARR[None, :, :]) ** 2).sum(2))   # N x K
    idx = d.argmin(1)
    near = d.min(1) < 52
    freq = {}
    n = near.sum()
    if n < 8:
        return {'fold': 1.0}
    for k in np.unique(idx[near]):
        act = _CACT[int(k)]
        freq[act] = freq.get(act, 0.0) + float((idx[near] == k).sum()) / n
    return freq


def read_panel(rgb, bbox):
    gx, gy, gw, gh = bbox
    cw, ch = gw / 13.0, gh / 13.0
    hands = {}
    for r in range(13):
        for c in range(13):
            f = _cell_freq(rgb, gx + c * cw, gy + r * ch, cw, ch)
            hands[hand_at(r, c)] = {a: round(v, 3) for a, v in f.items() if v > 0.02}
    return hands


def pct(hands):
    agg = {}
    tot = 0.0
    for h, acts in hands.items():
        n = _combos(h)
        tot += n
        for a, v in acts.items():
            agg[a] = agg.get(a, 0.0) + n * v
    return {a: round(100 * v / tot, 2) for a, v in agg.items()}


def dominant(acts):
    return max(acts.items(), key=lambda kv: kv[1])[0] if acts else 'fold'


def read_all():
    bgr = cv2.imread(IMG)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(int)
    return {PANEL_NAMES[i]: read_panel(rgb, PANELS[i]) for i in range(4)}


if __name__ == '__main__':
    panels = read_all()
    probe = ['AA', 'AKs', 'AQs', 'KQs', 'AJo', 'KJs', 'TT', '99', '22', 'A5s', 'JTo', 'K9o', 'Q9o', '76o']
    _ab = {'three_bet': '3b', 'call': 'FLAT', 'all_in': 'SHOVE', 'fold': 'fold'}
    for name, hands in panels.items():
        print('\n==', name, '== %', pct(hands))
        print('  ', ' '.join('%s=%s' % (h, _ab[dominant(hands[h])]) for h in probe))
