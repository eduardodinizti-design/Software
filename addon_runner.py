"""Rotina de ADD-ON de torneio (PPPoker) — detectar o pop-up e fazer o add-on.

Promove a rotina provada ao vivo em 20/11/2026 (torneio BINGO) de um script solto
para um módulo com detector testável + clique armado revalidado + watcher.

CONTEXTO (ver memória [[nvt-rotina-addon-torneio]]):
  - O add-on de um torneio é habilitado ~5 min antes de encerrar o late registration.
    Nessa janela curta aparece um POP-UP de add-on. O Henrique deve detectá-lo e confirmar.
  - Anatomia do modal (capturado ao vivo): título "Add-on", texto
    "Você tem N fichas. Adicionar M fichas com C Fichas PP? (mm:ss)", e dois botões
    VERDES: "Confirmar" (esquerda) e "Cancelar" (direita). Variantes Add-on/Duplo/Triplo.
  - Add-on SIMPLES = o de 10 Fichas PP (padrão do Eduardo). Fichas = play money
    ([[nvt-fichas-ficticias-sem-receio]]): NÃO hesitar, apenas acertar o botão.

GUARDA técnica: nunca clicar em "Cancelar". O alvo é localizado por máscara-de-verde
+ OCR do texto 'confirm' em cada revalidação (via _click_step do registrar_armado),
então um alvo que sumiu/moveu CANCELA o clique.
"""
from __future__ import annotations

import re
import time

import cv2
import numpy as np

from table_reading.ocr_runtime import image_to_string

__all__ = ["detect_addon_popup", "confirm_addon", "watch_and_addon"]


def _ocr(gray, psm: int = 7) -> str:
    return " ".join(image_to_string(gray, config="--psm %d" % psm).split())


def _green_buttons(frame):
    """Lista de botões verdes plausíveis: (x, y, w, h, area, texto_minúsculo)."""
    fh, fw = frame.shape[:2]
    b = frame[:, :, 0].astype(int)
    g = frame[:, :, 1].astype(int)
    r = frame[:, :, 2].astype(int)
    green = ((g > 110) & (g > r + 30) & (g > b + 10) & (r < 150)).astype(np.uint8) * 255
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(green, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < 120 or h < 40 or w > fw * 0.9 or w / max(1, h) < 1.8:
            continue
        txt = _ocr(cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)).lower()
        out.append((int(x), int(y), int(w), int(h), int(area), txt))
    return out


_COST_RE = re.compile(r"com\s+([\d.,]+)\s*fichas?\s*pp", re.I)
_ADD_RE = re.compile(r"adicionar\s+([\d.,]+)\s*fichas", re.I)


def _to_int(num: str):
    try:
        return int(num.replace(".", "").replace(",", "").strip())
    except Exception:
        return None


def detect_addon_popup(frame) -> dict:
    """Detecta o modal de add-on no frame FÍSICO. Retorna:
      present (bool), cost_pp (int|None), add_chips (int|None),
      confirm_rect ((x,y,w,h)|None), cancel_rect, raw (texto).
    `present` exige: texto de add-on + 'Fichas PP' + botão verde 'Confirmar' visível.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    full = _ocr(gray, psm=6)
    low = full.lower()
    looks_addon = ("add-on" in low or "add on" in low or "addon" in low)
    has_pp = ("fichas pp" in low) or ("ficha pp" in low)

    confirm_rect = cancel_rect = None
    for x, y, w, h, _area, txt in _green_buttons(frame):
        if "confirm" in txt and confirm_rect is None:
            confirm_rect = (x, y, w, h)
        elif "cancel" in txt and cancel_rect is None:
            cancel_rect = (x, y, w, h)

    cost_m = _COST_RE.search(full)
    add_m = _ADD_RE.search(full)
    present = bool(looks_addon and has_pp and confirm_rect is not None)
    return dict(
        present=present,
        cost_pp=_to_int(cost_m.group(1)) if cost_m else None,
        add_chips=_to_int(add_m.group(1)) if add_m else None,
        confirm_rect=confirm_rect,
        cancel_rect=cancel_rect,
        raw=full,
    )


def confirm_addon(engine, hwnd, *, control, adapter, max_cost_pp=None, deadline_s=6.0) -> dict:
    """Confirma o add-on: clique armado+revalidado em 'Confirmar'. Reusa o motor do
    registrar (_click_step). `max_cost_pp` barra add-on mais caro que o esperado
    (guarda contra pegar Duplo/Triplo por engano). Retorna o dict do CursorController
    (ou {state:'NO_POPUP'|'COST_EXCEEDS'})."""
    from registrar_armado import _click_step  # motor de clique gated+revalidado

    frame, _ = engine.capture_frame(hwnd=hwnd)
    if frame is None:
        return dict(state="NO_FRAME")
    det = detect_addon_popup(frame)
    if not det["present"]:
        return dict(state="NO_POPUP")
    if max_cost_pp is not None and det.get("cost_pp") and det["cost_pp"] > max_cost_pp:
        return dict(state="COST_EXCEEDS", cost_pp=det["cost_pp"], max_cost_pp=max_cost_pp)

    def locate(fr):
        d = detect_addon_popup(fr)
        return d["confirm_rect"] if d["present"] else None

    def verify(_intent, _now):
        f, _ = engine.capture_frame(hwnd=hwnd)
        return dict(confirmed=(f is not None and not detect_addon_popup(f)["present"]))

    res = _click_step(engine, hwnd, locate_frame_rect=locate,
                      source_key="btn:addon-confirmar", adapter=adapter, control=control,
                      verifier=verify, label="addon", deadline_s=deadline_s)
    # reconciliação: EFFECT_UNCONFIRMED é esperado (OCR lento); modal fechado = sucesso.
    f2, _ = engine.capture_frame(hwnd=hwnd)
    res["modal_closed"] = bool(f2 is not None and not detect_addon_popup(f2)["present"])
    res["cost_pp"] = det.get("cost_pp")
    res["add_chips"] = det.get("add_chips")
    return res


def watch_and_addon(engine, hwnd, *, control, adapter, timeout_s=360.0, poll_s=2.0,
                    max_cost_pp=10, on_log=None) -> dict:
    """Vigia a janela pelo pop-up de add-on (READ-ONLY até aparecer) e, ao surgir,
    faz o add-on simples. `max_cost_pp` protege contra confirmar variante cara.
    Retorna o resultado de confirm_addon, ou {state:'TIMEOUT_NO_POPUP'}."""
    log = on_log or (lambda *_a: None)
    t0 = time.time()
    seen = False
    while time.time() - t0 < timeout_s:
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is not None:
            det = detect_addon_popup(frame)
            if det["present"]:
                log("[addon] pop-up detectado (cost_pp=%s, +%s fichas) -> confirmando"
                    % (det.get("cost_pp"), det.get("add_chips")))
                return confirm_addon(engine, hwnd, control=control, adapter=adapter,
                                     max_cost_pp=max_cost_pp)
            if not seen:
                seen = True
                log("[addon] vigiando a janela pelo pop-up de add-on...")
        time.sleep(poll_s)
    return dict(state="TIMEOUT_NO_POPUP")


def _main(argv=None):
    import argparse
    from bot_control import BotControl
    from cursor_input_win import WindowsCursorInput
    from table_discovery.pppoker import discover_pppoker
    from table_reading.pipeline import configure_ocr
    from window_capture_engine import WindowCaptureEngine

    p = argparse.ArgumentParser(description="Watcher/clicador do add-on de torneio")
    p.add_argument("--hwnd", type=lambda s: int(s, 0), default=None,
                   help="HWND do PPPoker (default: maior janela PPPoker)")
    p.add_argument("--timeout", type=float, default=360.0, help="Segundos vigiando")
    p.add_argument("--poll", type=float, default=2.0, help="Intervalo de verificação (s)")
    p.add_argument("--max-cost-pp", type=int, default=10,
                   help="Custo máx. em Fichas PP (simples=10; barra Duplo/Triplo)")
    p.add_argument("--arm", action="store_true", help="Clica de verdade (senão só detecta)")
    args = p.parse_args(argv)

    configure_ocr()
    engine = WindowCaptureEngine()
    hwnd = args.hwnd
    if hwnd is None:
        wins = discover_pppoker().get("windows", [])
        if not wins:
            print("Sem janela PPPoker."); return 1
        hwnd = max(wins, key=lambda d: d["w"] * d["h"])["hwnd"]
    print("addon_runner | hwnd=%s | arm=%s | timeout=%.0fs" % (hex(hwnd), args.arm, args.timeout))

    if not args.arm:
        # modo detecção: só diz se o pop-up está na tela agora
        frame, _ = engine.capture_frame(hwnd=hwnd)
        det = detect_addon_popup(frame) if frame is not None else {"present": False}
        print("DETECÇÃO:", {k: det.get(k) for k in ("present", "cost_pp", "add_chips", "confirm_rect")})
        return 0

    control = BotControl()
    control.resume()  # RUNNING (auto-arm; play money, ação autorizada)
    adapter = WindowsCursorInput()
    res = watch_and_addon(engine, hwnd, control=control, adapter=adapter,
                          timeout_s=args.timeout, poll_s=args.poll,
                          max_cost_pp=args.max_cost_pp, on_log=print)
    print("[resultado]", {k: res.get(k) for k in ("state", "modal_closed", "cost_pp", "add_chips", "reasons")})
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
