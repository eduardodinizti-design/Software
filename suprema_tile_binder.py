"""BINDING roomID -> COLUNA na tela, ANCORADO NA REALIDADE VISUAL (não em palpite de ordem).

PROBLEMA: a Suprema tila N mesas lado a lado numa única janela OS. Sabemos a geometria das colunas
(esquerda->direita, suprema_click._tile_rect) e o estado por roomID (hook de rede). MAS o protocolo
NÃO diz qual roomID está em qual coluna (varredura confirmou). A heurística antiga (ordem de 1ª
aparição == L->R) FALHOU ao vivo (23/11): clicava na mesa espelhada ("confusão entre as mesas").

SOLUÇÃO: o ID da mesa está RENDERIZADO NO FELTRO de cada tile (texto cinza "ID: ..._<tabela>_..."),
provado por captura. Lemos (OCR) o ID de cada coluna e casamos com o roomID do stream pelo token da
MESA. Determinístico, estável (o ID não muda na sessão), independente de carta/estado. Vale p/ 2/3/4
telas (os tiles têm largura constante ~758px; a janela cresce na horizontal).

Camadas:
  - PURA/testável: _mid_token / match_rooms_to_columns (casa {coluna: id_lido} com [roomIDs]).
  - IO: read_tile_ids(hwnd) captura a janela, recorta a faixa do ID de cada coluna e faz OCR.
  - TileBinder: cacheia o mapa e re-liga quando as mesas/colunas mudam (re-tile).
"""
from __future__ import annotations
import re

# faixa do ID no tile (frações), validada nas capturas 2 e 4 telas (tile 758x1348):
ID_BAND_FRAC = (0.12, 0.50, 0.88, 0.64)   # (fx0, fy0, fx1, fy1)

_TOKENS = re.compile(r"\d{5,}")
_NONDIGIT = re.compile(r"\D")


def _mid_token(id_str):
    """Token da MESA de um roomID LIMPO (do stream) ou de um ID de feltro limpo. Formato
    '<torneio>_<TABELA>_<seat>' -> devolve a TABELA (parte do meio): '14625_50813539_5' -> '50813539';
    '112314625_50050813539_172315' -> '50050813539'. Sem a estrutura de 3 partes, cai no maior número.
    NÃO usar direto no OCR cru da coluna (ruído) — lá usa-se _matches (substring nos dígitos)."""
    if not id_str:
        return ""
    s = str(id_str)
    parts = [p for p in re.split(r"[_\s]+", s) if p.isdigit()]
    if len(parts) >= 3:
        return parts[1]                      # <torneio>_<TABELA>_<seat>
    nums = _TOKENS.findall(s)
    return max(nums, key=len) if nums else ""


def _matches(col_ocr, room):
    """A sala do stream casa com o OCR (possivelmente ruidoso) de uma coluna? Extrai o token da MESA
    do roomID LIMPO (stream) e procura-o como SUBSTRING nos DÍGITOS do OCR cru da coluna. Robusto a
    ruído de OCR (blinds/timer grudados): o token da mesa (≥6 díg.) é específico e não vem do ruído."""
    tok = _mid_token(room)
    if not tok or len(tok) < 6:
        return False
    digits = _NONDIGIT.sub("", str(col_ocr or ""))
    return tok in digits


def match_rooms_to_columns(col_ids, rooms):
    """PURA. col_ids = {coluna(int): ocr_cru_da_coluna(str)}; rooms = [roomID(str) do stream]. Devolve
    {roomID: coluna} só para as salas casadas de forma ÚNICA (1 coluna). Salas ambíguas/sem casar ficam
    de fora (o chamador usa o fallback antigo só p/ essas). Nunca mapeia 2 salas na mesma coluna."""
    out = {}
    used = set()
    for room in rooms:
        hits = [c for c, cid in col_ids.items() if c not in used and _matches(cid, room)]
        if len(hits) == 1:
            out[room] = hits[0]
            used.add(hits[0])
    return out


# ----------------------------- camada IO (captura + OCR) -----------------------------
def _tesseract():
    import os
    import pytesseract
    for cand in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"):
        if os.path.exists(cand):
            pytesseract.pytesseract.tesseract_cmd = cand
            break
    return pytesseract


def _ocr_id_band(pil_tile):
    """OCR da faixa do ID de UM tile (PIL.Image). Devolve o ID lido (string com dígitos/_) ou ''."""
    import numpy as np
    from PIL import Image
    pt = _tesseract()
    w, h = pil_tile.size
    fx0, fy0, fx1, fy1 = ID_BAND_FRAC
    band = pil_tile.crop((int(fx0 * w), int(fy0 * h), int(fx1 * w), int(fy1 * h)))
    g = band.convert("L")
    g = g.resize((g.width * 3, g.height * 3))
    a = np.array(g)
    b = (a > a.mean() + 10).astype("uint8") * 255
    txt = pt.image_to_string(Image.fromarray(b),
                             config="--psm 6 -c tessedit_char_whitelist=0123456789_ID:")
    return "".join(txt.split())


def read_tile_ids(hwnd, n_cols=None):
    """IO. Captura a janela da Suprema e lê o ID do feltro de CADA coluna. Devolve {coluna: id_lido}.
    n_cols: se None, deduz por suprema_click.columns_from_window. Nunca lança (erros -> coluna omitida)."""
    import suprema_click as C
    from PIL import ImageGrab
    if n_cols is None:
        n_cols = C.columns_from_window(hwnd)
    out = {}
    for i in range(max(1, int(n_cols))):
        try:
            tx, ty, tw, th = C.table_rect_for_room(hwnd, i, n_cols)
            tile = ImageGrab.grab(bbox=(tx, ty, tx + tw, ty + th), all_screens=True)
            cid = _ocr_id_band(tile)
            if _mid_token(cid):
                out[i] = cid
        except Exception:
            pass
    return out


class TileBinder:
    """Mapa roomID->coluna por VISÃO, com cache e re-ligação quando a grade muda.

    Uso no agente (substitui a heurística de ordem):
        binder = TileBinder(hwnd)
        binder.ensure(live_rooms)          # re-liga se o conjunto de salas/colunas mudou
        col = binder.column_of(room)       # coluna 0-based (ou None se não casou)
        n   = binder.n_cols                # nº de colunas atual
    """
    def __init__(self, hwnd, *, reader=read_tile_ids, columns_fn=None, max_age=20.0):
        self.hwnd = hwnd
        self._reader = reader
        if columns_fn is None:
            import suprema_click as C
            columns_fn = lambda: C.columns_from_window(hwnd)
        self._columns_fn = columns_fn
        self._max_age = float(max_age)
        self.n_cols = 0
        self._map = {}            # roomID -> coluna
        self._key = None          # assinatura da grade p/ saber se mudou
        self._ts = 0.0            # quando ligou pela última vez (staleness de segurança)

    def ensure(self, rooms):
        """Re-liga se o nº de colunas ou o conjunto de salas vivas mudou, OU se passou max_age (re-tile
        físico sem mudar as salas). Barato quando estável. 1 coluna = atalho (sem OCR: tudo coluna 0)."""
        import time as _t
        rooms = sorted(set(rooms or []))
        try:
            n = max(1, int(self._columns_fn()))
        except Exception:
            n = self.n_cols or 1
        if n <= 1:                                   # 1 mesa: sempre coluna 0, NÃO precisa de OCR
            self.n_cols = 1
            self._map = {r: 0 for r in rooms}
            self._key = (1, tuple(rooms))
            self._ts = _t.time()
            return self._map
        key = (n, tuple(rooms))
        fresh = (_t.time() - self._ts) < self._max_age
        if key == self._key and self._map and fresh:
            return self._map
        col_ids = {}
        try:
            col_ids = self._reader(self.hwnd, n)
        except Exception:
            col_ids = {}
        new_map = match_rooms_to_columns(col_ids, rooms)
        # KEEP-LAST-GOOD: se o OCR falhou p/ alguma sala NESTA passada, mantém o casamento BOM anterior
        # (o binding é ESTÁVEL; um blip de OCR não deve derrubar p/ o fallback de ORDEM, que pode TROCAR
        # as mesas). O OCR novo tem prioridade (pega re-tile real); só salas ainda vivas são mantidas.
        merged = {r: self._map.get(r) for r in rooms if self._map.get(r) is not None}
        merged.update(new_map)
        self._map = merged
        self.n_cols = n
        self._key = key
        self._ts = _t.time()
        return self._map

    def column_of(self, room):
        return self._map.get(room)
