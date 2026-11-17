"""Percepção + navegação da GRADE DE CLUBES do PPPoker (o seletor onde se troca de
clube clicando no NOME do tile).

Duas responsabilidades PURAS e testáveis:
  - limpeza/normalização e MATCH de nome de clube. Os nomes vêm TRUNCADOS ("AK
    AMAKHA cl...") e com ruído de ícone/emoji (") Karekas Yellow", "LALINHA�"),
    e há clubes PARECIDOS -> o match na grade é best-effort; a verificação final é
    o nome COMPLETO lido DENTRO do clube (club_switcher.read_current_club).
  - NAVEGAÇÃO rolar-e-buscar. A grade ROLA (mais clubes do que cabe) e a ORDEM MUDA
    entre aberturas (operador, 17/11) -> nunca confiar em posição fixa; RE-LER a cada
    rolagem e buscar pelo NOME, até achar o alvo ou acabar a lista.

A leitura de pixels (OCR dos tiles) e as ações (rolar/clicar) são INJETADAS — aqui
mora só a lógica. O coordenador de alto nível (idempotência + gate + verificação pós
-clique) é o club_switcher.ClubSwitcher; este navegador é o executor do `do_switch`.
"""
import re

_WORD = r'0-9A-Za-zÀ-ÿ'
_ELLIPSIS = re.compile(r'(\.\.\.|…)\s*$')


def clean_club_name(raw):
    """(nome_limpo, truncado). Troca caractere inválido por espaço, colapsa espaços,
    marca truncamento final ("..."/"…") e apara ruído não-alfanumérico nas pontas
    (ícone ")" à esquerda etc.). Não inventa: ('', False) se vazio/None."""
    if not isinstance(raw, str):
        return '', False
    s = re.sub(r'\s+', ' ', raw.replace('�', ' ')).strip()
    truncated = bool(_ELLIPSIS.search(s))
    s = _ELLIPSIS.sub('', s).strip()
    s = re.sub(r'^[^%s]+' % _WORD, '', s)        # ruído à esquerda (ícone)
    s = re.sub(r'[^%s]+$' % _WORD, '', s)        # ruído à direita
    return re.sub(r'\s+', ' ', s).strip(), truncated


def normalize(s):
    """Forma canônica p/ comparar nomes (limpo + casefold)."""
    return clean_club_name(s)[0].casefold()


def match_club(target, candidates):
    """Acha o tile que corresponde ao `target` (nome COMPLETO desejado). Devolve
    dict(index, name, ambiguous, reason). Ordem das regras:
      1) match EXATO normalizado;
      2) candidato TRUNCADO cujo prefixo inicia o target (nome cortado pelo tile).
    Se mais de um candidato casa igualmente, ambiguous=True e index=None — NÃO chuta
    entre clubes parecidos (ex.: dois 'AK ...'); quem resolve é a verificação dentro
    do clube ou uma busca exata."""
    tgt = normalize(target)
    if not tgt:
        return dict(index=None, name=None, ambiguous=False, reason='ALVO_VAZIO')
    norms = [normalize(c) for c in candidates]
    trunc = [clean_club_name(c)[1] for c in candidates]

    exact = [i for i, n in enumerate(norms) if n and n == tgt]
    if len(exact) == 1:
        return dict(index=exact[0], name=candidates[exact[0]], ambiguous=False, reason='EXATO')
    if len(exact) > 1:
        return dict(index=None, name=None, ambiguous=True, reason='EXATO_AMBIGUO')

    pref = [i for i, n in enumerate(norms) if n and trunc[i] and tgt.startswith(n)]
    if len(pref) == 1:
        return dict(index=pref[0], name=candidates[pref[0]], ambiguous=False, reason='PREFIXO_TRUNCADO')
    if len(pref) > 1:
        return dict(index=None, name=None, ambiguous=True, reason='PREFIXO_AMBIGUO')

    return dict(index=None, name=None, ambiguous=False, reason='NAO_ENCONTRADO')


# --------------------------------------------------------------------------- #
# Percepção dos TILES (pixels) — calibrado no gabarito v228 (recorte 760x1415). #
# --------------------------------------------------------------------------- #
# As pílulas verdes de contagem de membros (uma por tile, topo-direito) são a
# ÂNCORA: distintas, uma por clube, robustas à ordem/scroll. O nome fica num
# offset fixo abaixo-à-esquerda, medido em MÚLTIPLOS do tamanho da pílula (então
# escala com o DPI/zoom). cv2/numpy são importados dentro das funções para manter
# a lógica pura (clean/match/navigator) testável sem esses pesos.
_PILL_H = (35, 95)          # matiz verde (OpenCV H 0-179)
_PILL_S_MIN, _PILL_V_MIN = 60, 120
_NAME_DY_TOP, _NAME_DY_BOT = 10.1, 11.6    # * altura_pílula, abaixo do TOPO da pílula
_NAME_DX_L, _NAME_DX_R = 2.83, 0.98        # * largura_pílula (p/ esquerda / direita)


def detect_club_pills(crop):
    """(x, y, w, h) de cada pílula de contagem, em ordem de leitura (linhas, colunas).
    Filtra a barra do topo (larga demais) por tamanho relativo."""
    import cv2
    import numpy as np
    h, w = crop.shape[:2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    lo, hi = _PILL_H
    mask = ((H > lo) & (H < hi) & (S > _PILL_S_MIN) & (V > _PILL_V_MIN)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    pills = []
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if 0.05 * w < bw < 0.12 * w and 0.012 * h < bh < 0.04 * h and area > 400:
            pills.append((int(x), int(y), int(bw), int(bh)))
    row_h = max(1.0, 0.04 * h)
    pills.sort(key=lambda b: (round(b[1] / row_h), b[0]))   # linha, depois coluna
    return pills


def _name_band(pill):
    px, py, pw, ph = pill
    return (px - int(_NAME_DX_L * pw), py + int(_NAME_DY_TOP * ph),
            px + int(_NAME_DX_R * pw), py + int(_NAME_DY_BOT * ph))


def read_club_grid(crop, *, ocr):
    """[{name, name_raw, truncated, click, name_rect, pill}] por tile VISÍVEL, em
    ordem de leitura. `ocr` é callable(imagem_cinza)->str (injetado p/ testar sem
    Tesseract). Tiles cujo nome cai FORA do crop (parciais no rodapé) são omitidos.
    Coordenadas no espaço do CROP — o chamador soma a origem p/ chegar à tela."""
    import cv2
    h, w = crop.shape[:2]
    out = []
    for pill in detect_club_pills(crop):
        x0, y0, x1, y1 = _name_band(pill)
        if y1 > h or x0 < 0 or x1 > w:            # nome parcial/fora -> omite (não chuta)
            continue
        raw = ' '.join(ocr(cv2.cvtColor(crop[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)).split())
        name, trunc = clean_club_name(raw)
        out.append(dict(name=name, name_raw=raw, truncated=trunc,
                        click=((x0 + x1) // 2, (y0 + y1) // 2),
                        name_rect=(x0, y0, x1, y1), pill=pill))
    return out


def list_visible_from_crop(crop, *, ocr, origin=(0, 0)):
    """Formato que o ClubGridNavigator consome: [{'name', 'click'}], com o clique já
    deslocado pela `origin` (origem do crop na janela/tela). Adaptador de `list_visible`."""
    ox, oy = origin
    return [dict(name=t['name'], click=(t['click'][0] + ox, t['click'][1] + oy))
            for t in read_club_grid(crop, ocr=ocr)]


def _green_components(frame):
    """(x, y, w, h) de todo componente verde (pílula + ruído) — base do find_grid_crop."""
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    lo, hi = _PILL_H
    mask = ((H > lo) & (H < hi) & (S > _PILL_S_MIN) & (V > _PILL_V_MIN)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    return [(int(stats[i][0]), int(stats[i][1]), int(stats[i][2]),
             int(stats[i][3]), int(stats[i][4])) for i in range(1, n)]   # x,y,w,h,area


def find_grid_crop(frame, *, margin=22):
    """Localiza o painel da GRADE DE CLUBES numa captura de janela/tela CHEIA, pela
    âncora das pílulas de contagem — sem depender da geometria da janela (robusto a
    posição/DPI, pois usa o tamanho DOMINANTE das pílulas, não pixels absolutos).

    Devolve dict(ok, crop, origin=(x, y), pills, reason). `crop` entra direto no
    read_club_grid/list_visible_from_crop; `origin` mapeia os cliques de volta à tela
    (clique_tela = clique_no_crop + origin). ok=False quando não há grade à vista."""
    import numpy as np
    H, W = frame.shape[:2]
    # pílula = retângulo PREENCHIDO, mais largo que alto, tamanho plausível. O filtro
    # de ÁREA é o que descarta texto/ícones verdes finos (senão a âncora erra).
    cand = [(x, y, w, h) for (x, y, w, h, area) in _green_components(frame)
            if 14 < h < 70 and 28 < w < 170 and 1.3 < w / max(h, 1) < 4.0
            and area > 350 and area > 0.45 * w * h]
    if len(cand) < 2:
        return dict(ok=False, crop=None, origin=None, pills=[], reason='SEM_PILULAS')
    # mantém só o tamanho DOMINANTE (mediana ±40%): descarta barras/ícones verdes avulsos
    wmed = float(np.median([w for (_, _, w, _) in cand]))
    hmed = float(np.median([h for (_, _, _, h) in cand]))
    pills = [(x, y, w, h) for (x, y, w, h) in cand
             if 0.6 * wmed <= w <= 1.6 * wmed and 0.6 * hmed <= h <= 1.6 * hmed]
    if len(pills) < 2:
        return dict(ok=False, crop=None, origin=None, pills=[], reason='PILULAS_INCONSISTENTES')
    pw = int(round(np.median([w for (_, _, w, _) in pills])))
    ph = int(round(np.median([h for (_, _, _, h) in pills])))
    left = max(0, min(x for (x, _, _, _) in pills) - int(_NAME_DX_L * pw) - margin)
    right = min(W, max(x + w for (x, _, w, _) in pills) + margin)
    top = max(0, min(y for (_, y, _, _) in pills) - 2 * ph)
    bottom = min(H, max(y for (_, y, _, _) in pills) + int(_NAME_DY_BOT * ph) + margin)
    if right - left < 2 * pw or bottom - top < 2 * ph:
        return dict(ok=False, crop=None, origin=None, pills=pills, reason='AREA_DEGENERADA')
    return dict(ok=True, crop=frame[top:bottom, left:right], origin=(left, top),
                pills=sorted(pills, key=lambda b: (b[1], b[0])), reason='OK')


# Cabeçalho DENTRO do clube: caixa "Nome do clube / ID do clube: N" no topo-esquerda
# do painel de torneios. Frações do painel — calibrado p/ funcionar em DOIS aspectos
# (gabarito 1005x1787 E o crop do find_lobby_crop ao vivo 839x1266); x0=0.18 evita
# clipar a 1ª letra no aspecto mais estreito (bug 'arekas Yellow' achado ao vivo 17/11).
_HEADER_ROI = (0.180, 0.158, 0.520, 0.186)   # x0, y0, x1, y1 (y1 exclui a linha do ID)


def read_current_club(panel_crop, *, ocr):
    """Nome do clube ABERTO, lido do cabeçalho do painel de torneios (caixa 'Nome /
    ID do clube' no topo), já limpo — ou None se não leu. É a VERIFICAÇÃO do
    club_switcher: confirma que de fato entrou no clube certo após clicar o tile."""
    import cv2
    h, w = panel_crop.shape[:2]
    fx0, fy0, fx1, fy1 = _HEADER_ROI
    roi = panel_crop[int(fy0 * h):int(fy1 * h), int(fx0 * w):int(fx1 * w)]
    raw = ' '.join(ocr(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)).split())
    return clean_club_name(raw)[0] or None


class ClubGridNavigator:
    """Rola a grade e clica no tile do clube-alvo. Primitivas injetadas:
      list_visible() -> [{'name': str, 'click': (x, y)}]   tiles visíveis AGORA
      scroll()       -> bool                               rola p/ baixo; True se moveu
      click(point)   -> qualquer                           clica no ponto

    Trata: ordem-muda (relê a cada passo), alvo não-visível (rola), fim-da-lista
    (scroll não moveu, ou tela repetida) e ambiguidade (para, não chuta)."""

    def __init__(self, *, list_visible, scroll, click, max_scrolls=12):
        for fn, nm in ((list_visible, 'list_visible'), (scroll, 'scroll'), (click, 'click')):
            if not callable(fn):
                raise TypeError('%s deve ser callable' % nm)
        self._list = list_visible
        self._scroll = scroll
        self._click = click
        self.max_scrolls = max(0, int(max_scrolls))

    def find_and_click(self, target):
        prev = None
        for step in range(self.max_scrolls + 1):
            tiles = self._list() or []
            names = [t.get('name') for t in tiles]
            m = match_club(target, names)
            if m['ambiguous']:
                return dict(ok=False, action='AMBIGUO', reason=m['reason'], scrolls=step)
            if m['index'] is not None:
                point = tiles[m['index']].get('click')
                self._click(point)
                return dict(ok=True, action='CLICOU', clicked=point,
                            name=names[m['index']], reason=m['reason'], scrolls=step)
            cur = tuple(normalize(n) for n in names if n)
            if cur and cur == prev:                      # rolou mas nada mudou
                return dict(ok=False, action='NAO_ENCONTRADO', reason='SEM_PROGRESSO', scrolls=step)
            prev = cur
            if step == self.max_scrolls:
                return dict(ok=False, action='NAO_ENCONTRADO', reason='MAX_SCROLLS', scrolls=step)
            if not self._scroll():                       # não moveu = fim da lista
                return dict(ok=False, action='NAO_ENCONTRADO', reason='FIM_DA_LISTA', scrolls=step)
        return dict(ok=False, action='NAO_ENCONTRADO', reason='MAX_SCROLLS', scrolls=self.max_scrolls)
