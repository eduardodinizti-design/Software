"""DRY-RUN ao vivo da Suprema (RISCO ZERO): na vez do heroi, roda percepcao->cerebro->plano
->calcula a SEQUENCIA de cliques, captura a tela e DESENHA marcadores onde o Henrique CLICARIA —
sem clicar nada, sem mexer o cursor. Valida a cadeia inteira visualmente. Read-only."""
import ctypes
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capturar_na_vez import find_suprema_hwnd, grab

_DIR = os.path.dirname(os.path.abspath(__file__))


def derive_bb(table):
    rr = (table.prompt or {}).get('raise_range') or {}
    presets = rr.get('presets') or {}
    if '2X' in presets and presets['2X']:
        return presets['2X'] / 2.0          # 2X = 2*BB
    return rr.get('min')                     # fallback aproximado


def main():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    import suprema_net
    import suprema_click as C
    import assistir_suprema as AS
    from PIL import Image, ImageDraw

    hwnd = find_suprema_hwnd()
    if not hwnd:
        print("[erro] janela Suprema nao encontrada."); return 1
    advisor = AS.load_advisor()
    print("[dry-run] hwnd=%s; RISCO ZERO (nao clica). Jogue ate a sua vez (150s)." % hex(hwnd), flush=True)
    st = {"n": 0}

    def on_state(table):
        if not table.legal_actions() or st["n"] >= 4:
            return
        bb = derive_bb(table)
        if bb:
            table.bb_chips = bb
        state, advice, plan = AS.decide_and_plan(table, advisor)
        st["n"] += 1
        hero = (table.players.get(table.hero_seat) or {}).get('cards') if table.hero_seat else None
        seq = C.build_sequence(plan)
        # captura + desenha onde CLICARIA (sem clicar)
        shot = os.path.join(_DIR, "dryrun_%d.png" % st["n"])
        try:
            grab(hwnd, shot)
            img = Image.open(shot).convert("RGB"); W, H = img.size
            d = ImageDraw.Draw(img)
            for j, (fx, fy) in enumerate(seq):
                x, y = int(fx * W), int(fy * H)
                d.ellipse([x-18, y-18, x+18, y+18], outline=(255, 0, 255), width=6)
                d.text((x-10, y-42), "%d" % (j+1), fill=(255, 0, 255))
            img.save(shot)
        except Exception as e:
            print("[shot err]", e, flush=True)
        print("[DRY %d] hero=%s pos=%s board=%s bb~%s | CEREBRO=%s -> PLANO=%s %s%s | marcou %d clique(s) -> %s"
              % (st["n"], hero, (state or {}).get('positions', {}).get('hero'),
                 (state or {}).get('board'), bb, advice.get('recommended'), plan.get('action'),
                 plan.get('chips') or '', (' [%s]' % plan.get('preset')) if plan.get('preset') else '',
                 len(seq), os.path.basename(shot)), flush=True)

    suprema_net.run_live(bb_chips=1, on_state=on_state, seconds=150)
    print("[dry-run] fim. decisoes=%d" % st["n"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
