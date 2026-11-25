"""Detector + watcher do modal de ADD-ON/RE-ENTRADA da Suprema (Eduardo 24/11 — "ensinar o Henrique
a fazer o add-on"). Add-on é habilitado ~5min antes de fechar o late reg; sobe um DRAWER à direita
da mesa com: "Entradas X/Y", o custo (ex. "30,00" + ícone de ficha) e um BOTÃO VERMELHO circular
"add-on/re-entrada" no rodapé. POLÍTICA: confirmar o add-on simples; fichas = play money.

CAPTURADO AO VIVO 24/11 (janela 897x798): o botão vermelho fica no CANTO INFERIOR-DIREITO e, numa
janela ESTREITA, aparece CORTADO pela borda (centro fora da janela) — por isso o detector marca
`clipped` e NÃO deixa clicar (clique na beirada é não-confiável); o agente deve ALARGAR a janela
antes. Detecção por OCR (keyword do drawer) + blob VERMELHO circular na faixa direita. READ-ONLY."""
from __future__ import annotations

import os
import re
import time

import cv2
import numpy as np

# padrão "Entradas X/Y" (ex. "1.932/2.223") — assinatura forte do drawer de add-on/re-entrada
_RATIO_RE = re.compile(r"\d[.\d]*\s*/\s*\d[.\d]*")

try:
    import pytesseract
    for _p in (r'C:\Program Files\Tesseract-OCR\tesseract.exe',
               r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'):
        if os.path.exists(_p):
            pytesseract.pytesseract.tesseract_cmd = _p
            break
except Exception:                                       # pragma: no cover
    pytesseract = None

__all__ = ["detect_addon", "watch_and_addon"]


def _win_rect(hwnd):
    """Rect EXTERNO da janela (left,top,right,bottom) via user32, ou None."""
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(r)):
            return (r.left, r.top, r.right, r.bottom)
    except Exception:
        pass
    return None


def _resize_width(hwnd, new_w):
    """Muda só a LARGURA da janela (mantém posição/altura). Devolve a largura anterior ou None."""
    r = _win_rect(hwnd)
    if not r:
        return None
    import ctypes
    left, top, right, bottom = r
    old_w, h = right - left, bottom - top
    SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
    ctypes.windll.user32.SetWindowPos(int(hwnd), 0, left, top, int(new_w), h,
                                      SWP_NOZORDER | SWP_NOACTIVATE)
    return old_w

# keywords que identificam o DRAWER de add-on/re-entrada (na faixa direita da mesa)
_KW = ("entradas", "add-on", "add on", "addon", "re-entrada", "reentrada", "adicional", "opcional")


def _ocr_lower(gray, psm=4):
    """OCR com threshold binário (o texto do drawer é claro sobre painel escuro -> binariza bem)."""
    if pytesseract is None:
        return ""
    try:
        _, th = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY)
        return " ".join(pytesseract.image_to_string(th, config="--psm %d" % psm).split()).lower()
    except Exception:
        return ""


def _red_button(frame, x_from):
    """Maior blob VERMELHO (o botão de add-on) na faixa direita x>=x_from. Retorna
    (cx, cy, w, h, touches_right) ou None. `touches_right`=o blob encosta na borda direita
    (botão CORTADO -> centro real fora da janela)."""
    b = frame[:, :, 0].astype(int)
    g = frame[:, :, 1].astype(int)
    r = frame[:, :, 2].astype(int)
    red = ((r > 170) & (r - g > 55) & (r - b > 55)).astype(np.uint8) * 255
    red[:, :x_from] = 0
    cs, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fh, fw = frame.shape[:2]
    best = None
    for c in cs:
        x, y, w, h = cv2.boundingRect(c)
        if w >= 10 and h >= 22 and cv2.contourArea(c) > 180 and 0.25 <= w / float(h) <= 2.4:
            if best is None or y > best[1]:              # botão fica no RODAPÉ do drawer
                best = (x + w // 2, y + h // 2, w, h, (x + w) >= fw - 2)
    return best


def detect_addon(frame) -> dict:
    """Detecta o drawer de add-on. Retorna:
      detected  (bool): drawer de add-on presente (keyword + botão vermelho).
      clickable (bool): o botão está INTEIRO na janela (seguro clicar).
      clipped   (bool): o botão está cortado pela borda (janela estreita -> alargar antes).
      confirm   ((fx,fy)|None): fração do centro do botão (só confiável se clickable).
      raw       (str): OCR da faixa direita (debug)."""
    fh, fw = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    xr = int(fw * 0.74)
    txt = _ocr_lower(gray[:, xr:])
    # assinatura do drawer: keyword de add-on OU o padrão "Entradas X/Y" (forte, numérico)
    sig = any(k in txt for k in _KW) or bool(_RATIO_RE.search(txt))
    btn = _red_button(frame, xr) if sig else None
    clipped = bool(btn and btn[4])
    confirm = (btn[0] / fw, btn[1] / fh) if btn else None
    return dict(detected=bool(sig and btn), clickable=bool(btn and not clipped),
                clipped=clipped, confirm=confirm, raw=txt[:120])


def watch_and_addon(hwnd, C, *, armed=False, timeout_s=480.0, poll_s=1.5, cooldown_s=40.0,
                    widen_px=240, on_save=None, stop=None):
    """Vigia a janela, detecta o add-on e clica o botão. `C`=suprema_click. Se o botão estiver
    CORTADO por janela estreita (`clipped`), ALARGA a janela temporariamente (+`widen_px`), re-detecta,
    clica e RESTAURA a largura — assim o Henrique IDENTIFICA e CLICA mesmo em janela estreita (Eduardo
    24/11). `on_save(frame)` opcional. Para em `stop` (Event)."""
    from PIL import ImageGrab
    t0 = time.time()
    last = 0.0

    def _grab_detect():
        left, top, w, h = C.client_rect_screen(hwnd)
        img = ImageGrab.grab(bbox=(left, top, left + w, top + h), all_screens=True)
        fr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return fr, detect_addon(fr)

    while (stop is None or not stop.is_set()) and time.time() - t0 < timeout_s:
        try:
            frame, d = _grab_detect()
        except Exception as e:
            frame, d = None, dict(detected=False, clickable=False, clipped=False, confirm=None,
                                  raw="erro:%s" % e)
        if d["detected"] and on_save and frame is not None:
            try:
                on_save(frame)
            except Exception:
                pass
        if d["detected"] and (time.time() - last) > cooldown_s:
            restore_w = None
            # botão cortado pela janela estreita -> alarga p/ caber, re-detecta (só quando vai clicar).
            if d["clipped"] and not d["clickable"] and armed:
                outer = _win_rect(hwnd)
                if outer:
                    restore_w = outer[2] - outer[0]
                    print("[ADDON] %s botão cortado — alargando janela +%dpx p/ clicar."
                          % (time.strftime("%H:%M:%S"), widen_px), flush=True)
                    _resize_width(hwnd, restore_w + widen_px)
                    time.sleep(0.4)
                    try:
                        frame, d = _grab_detect()
                    except Exception:
                        pass
            if d["clickable"]:
                fx, fy = d["confirm"]
                x, y = C.frac_to_screen(hwnd, fx, fy)
                print("[ADDON] %s drawer detectado -> add-on (%d,%d)%s"
                      % (time.strftime("%H:%M:%S"), x, y, "" if armed else " [DRY]"), flush=True)
                if armed:
                    C._click_sendinput(x, y)
                    print("[ADDON] >>> CLIQUE add-on executado.", flush=True)
                last = time.time()
            elif d["clipped"]:
                print("[ADDON] %s botão cortado e não consegui alargar — ALARGUE a janela manualmente."
                      % time.strftime("%H:%M:%S"), flush=True)
            if restore_w is not None:                    # restaura a largura original da janela
                time.sleep(0.2)
                _resize_width(hwnd, restore_w)
        time.sleep(poll_s)
