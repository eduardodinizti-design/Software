"""ANTI-SIT-OUT da Suprema: detecta o hero em SIT-OUT e clica "Estou de volta" para reentrar — na
hora, INDEPENDENTE do hook de rede (funciona até quando o hook muta, que é justo quando o sit-out
acontece: sem eventos o agente perde a vez -> a Suprema sita o hero).

SINAL (calibrado 23/11 em captura real, 2 telas): quando o hero está sit-out, a Suprema mostra um
BOTÃO VERDE VIVO "Estou de volta" no rodapé de cada mesa. A presença desse botão É o sinal de sit-out
(e é o que se clica). Detecção por COR (verde vivo, distinto do feltro escuro) na faixa inferior do
tile — robusta, sem OCR. Jogando (sem sit-out) = 0 px de verde vivo ali (sem falso-positivo).

Camadas:
  - PURA/testável: _green_button_px / is_sitout (recebem a imagem do tile).
  - IO/loop: sitout_watch (thread) captura cada coluna, detecta e clica "Estou de volta". Gated por
    control.execution_allowed() (só reentra quando ARMADO; pausado = Eduardo assumiu, não força volta).
"""
from __future__ import annotations

# Botão "Estou de volta": centro em fração do TILE (constante p/ 1/2/3/4 telas — mesmo layout de tile).
SITOUT_BTN_FRAC = (0.823, 0.929)
_MIN_PX = 200                 # px de verde-vivo mínimos p/ considerar o botão presente (sit-out=1259; jogando=0)
_BAND_TOP_FRAC = 0.85         # faixa inferior do tile onde o botão vive


def _white_text_px(tile_rgb):
    """Nº de px de TEXTO BRANCO na faixa do botão (fy 0.90-0.97). PURO. Gate barato antes do OCR
    (sem texto branco = sem botão = não vale OCR)."""
    import numpy as np
    im = np.asarray(tile_rgb)
    if im.ndim != 3 or im.shape[2] < 3:
        return None, 0
    im = im[..., :3]
    h = im.shape[0]
    band = im[int(0.90 * h):int(0.97 * h), :, :]
    R, G, B = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    white = ((R > 170) & (G > 170) & (B > 170)).astype('uint8') * 255
    return white, int((white > 0).sum())


def _ocr_button_text(tile_rgb):
    """Texto do BOTÃO no rodapé do tile, lendo só os pixels BRANCOS (robusto ao fundo verde).
    Sit-out -> 'Estou de volta'; sua vez -> 'Desistir Pagar ...'; entre mãos -> ''. Minúsculas."""
    white, px = _white_text_px(tile_rgb)
    if px < 300:                      # sem texto branco suficiente -> nada a ler (entre mãos)
        return ""
    try:
        import pytesseract
        from PIL import Image
        import os
        for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"):
            if os.path.exists(c):
                pytesseract.pytesseract.tesseract_cmd = c
                break
        pim = Image.fromarray(white).resize((white.shape[1] * 2, white.shape[0] * 2))
        return " ".join(pytesseract.image_to_string(pim, config="--psm 7").split()).lower()
    except Exception:
        return ""


def is_sitout(tile_rgb):
    """True SE E SÓ SE o botão 'Estou de volta' está presente = hero SIT-OUT. Distingue dos botões de
    AÇÃO (Pagar/Desistir/Aumentar, que são verdes mas o texto NÃO tem 'volta'). Autoridade = o TEXTO,
    não a cor (a cor dava falso-positivo nos botões de ação — Eduardo 23/11)."""
    return "volta" in _ocr_button_text(tile_rgb)


def sitout_watch(hwnd, control, stop, *, seconds=0.0, period=3.0, cooldown=6.0, click=None, detect=None):
    """THREAD anti-sit-out: a cada `period`s, varre cada COLUNA; se detectar 'Estou de volta' (hero
    sit-out, por OCR do texto) E o controle estiver RUNNING, clica o botão (reentra). Cooldown por
    coluna evita re-clique. Independente do hook. `click`/`detect` injetáveis p/ teste."""
    import time
    import suprema_click as C
    from PIL import ImageGrab
    if click is None:
        click = C._click_sendinput
    if detect is None:
        detect = is_sitout
    last = {}
    t0 = time.time()
    while not stop.is_set() and (seconds <= 0 or time.time() - t0 < seconds):
        try:
            n = max(1, C.columns_from_window(hwnd))
            for i in range(n):
                tx, ty, tw, th = C.table_rect_for_room(hwnd, i, n)
                tile = ImageGrab.grab(bbox=(tx, ty, tx + tw, ty + th), all_screens=True)
                if not detect(tile):
                    continue
                if control is not None and not control.execution_allowed():
                    continue                      # pausado/off: Eduardo assumiu, não força a volta
                if (time.time() - last.get(i, 0.0)) < cooldown:
                    continue
                fx, fy = SITOUT_BTN_FRAC
                x, y = C.frac_to_screen_room(hwnd, fx, fy, i, n)
                print("[AG] SIT-OUT detectado (coluna %d/%d) -> clico 'Estou de volta' em (%d,%d)"
                      % (i, n, x, y), flush=True)
                click(x, y)
                last[i] = time.time()
        except Exception:
            pass
        stop.wait(period)
