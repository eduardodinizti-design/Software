"""Captura screenshot da janela da SupremaPoker (read-only) p/ mapear os botoes de acao.
Acha a janela pelo executavel, captura os pixels e salva PNG. Nenhuma acao no jogo."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suprema_tela.png")


def main():
    from window_capture_engine import WindowCaptureEngine
    eng = WindowCaptureEngine(title_substring="")      # casa qualquer titulo
    backend = eng._native()
    alvo = None
    for h in backend.handles():
        try:
            st = backend.state(h)
        except Exception:
            continue
        if not st:
            continue
        exe = (st.get("executable") or "").lower()
        if "suprema" in exe and "h2n" not in exe:      # o client, nao o HUD h2n
            w, h2 = st.get("width"), st.get("height")
            print("[win] hwnd=%s pid=%s exe=%s title=%r size=%sx%s" % (
                hex(h), st.get("pid"), st.get("executable"), st.get("title"), w, h2))
            if w and h2 and (alvo is None or w * h2 > alvo[1] * alvo[2]):
                alvo = (h, w, h2)
    if not alvo:
        print("[erro] janela da SupremaPoker nao encontrada (client aberto?).")
        return 1
    hwnd, w, hh = alvo
    frame = backend.pixels(hwnd, w, hh)                # BGR (hh, w, 3)
    try:
        from PIL import Image
        Image.fromarray(frame[:, :, ::-1]).save(OUT)   # BGR->RGB
    except Exception:
        import numpy as np
        try:
            import cv2
            cv2.imwrite(OUT, frame)
        except Exception as e:
            print("[erro] sem PIL/cv2 p/ salvar:", e); return 2
    print("[ok] screenshot salvo:", OUT, "(%dx%d)" % (w, hh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
