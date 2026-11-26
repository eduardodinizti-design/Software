"""VIGIA DE BUST da Suprema: detecta que o hero CAIU do torneio e clica SAIR — na hora, INDEPENDENTE
do hook (igual ao anti-sit-out).

TELA REAL (calibrada 23/11 em print ao vivo): ao bustar, a Suprema abre um pop-up "CLASSIFICAÇÃO" com
a POSIÇÃO final (ex. "Posição 138"), prêmios/KO/bounty, e DOIS botões no rodapé:
    [ Sair ] (VERMELHO, à ESQUERDA)      [ Observar ] (laranja, à direita)
Eduardo quer SAIR (deixa o torneio e fecha a mesa) — NÃO "Observar" (que fica assistindo). Isso NÃO é a
tela de "Ficar/Sair" verde do PPPoker (detect_tournament_end não serve aqui: botões vermelho/laranja).

Detecção SEGURA (anti-clique-errado, espírito da trava anti-Pagar 15/11): localiza a palavra "Sair" por
OCR (image_to_data = caixa da palavra) na metade inferior do tile, E SÓ age se o pop-up for CONFIRMADO
(tem "Observar" e sinais de classificação: "Posi..."/"Classi..."/"Bounty"). Sem isso, NÃO clica nada.

Camadas:
  - PURA/testável: find_sair(tile) -> (cx, cy) do botão Sair no CROP do tile, ou None.
  - IO/loop: bust_watch (thread) varre cada coluna; se achar, clica Sair. Gated por execution_allowed().
"""
from __future__ import annotations

_TESS = (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
         r"C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")


def _is_classificacao(im):
    """CONFIRMA o pop-up de CLASSIFICAÇÃO (bust) pelo TÍTULO/posição — OCR da faixa superior do tile
    (texto do título lê confiável, ao contrário do texto dos botões). Exige o título E a marca do MTT:
    ('classifica'|'posi') E ('mtt'|'suprema'|'bounty'). PURA."""
    try:
        import os
        import pytesseract
        from PIL import Image
        for c in _TESS:
            if os.path.exists(c):
                pytesseract.pytesseract.tesseract_cmd = c
                break
        h, w = im.shape[:2]
        top = Image.fromarray(im[int(0.05 * h):int(0.52 * h), int(0.15 * w):int(0.85 * w)])
        txt = " ".join(pytesseract.image_to_string(top, config="--psm 6").split()).lower()
    except Exception:
        return False
    return (('classifica' in txt or 'posi' in txt)
            and ('mtt' in txt or 'suprema' in txt or 'bounty' in txt))


def find_sair(tile_rgb):
    """Localiza o botão 'Sair' do pop-up de CLASSIFICAÇÃO (bust) e devolve (cx, cy) no CROP do tile,
    ou None. Estratégia calibrada 23/11 no print real: (1) CONFIRMA o pop-up pelo TÍTULO (OCR), (2) acha
    os DOIS botões QUENTES na faixa inferior (Sair vermelho esq / Observar laranja dir) por COR e clica
    o da ESQUERDA (= Sair), exigindo que ele seja o MAIS VERMELHO (G menor). O texto do botão NÃO é OCRável
    (branco em botão colorido), por isso cor+geometria. PURA/testável (recebe a imagem do tile)."""
    import numpy as np
    im = np.asarray(tile_rgb)
    if im.ndim != 3 or im.shape[2] < 3:
        return None
    im = np.ascontiguousarray(im[..., :3])
    H, W = im.shape[:2]
    if H < 200 or W < 150:
        return None
    if not _is_classificacao(im):
        return None                                   # não é a tela de bust -> não clica
    import cv2
    by0 = int(0.68 * H)
    band = im[by0:int(0.82 * H), :, :]
    R, G, Bl = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    warm = ((R > 150) & (R > G + 25) & (R > Bl + 25)).astype('uint8') * 255
    n, _, st, _ = cv2.connectedComponentsWithStats(warm, 8)
    bh, bw = band.shape[:2]
    blobs = [(int(st[i, 0]), int(st[i, 1]), int(st[i, 2]), int(st[i, 3]))
             for i in range(1, n)
             if st[i, 4] > 0.004 * bh * bw and st[i, 2] > 0.12 * W
             and 1.8 < st[i, 2] / max(st[i, 3], 1) < 7]
    blobs.sort(key=lambda b: b[0])                    # esquerda -> direita
    if len(blobs) < 2:
        return None                                   # precisa do PAR Sair/Observar

    def _meanG(b):
        s = band[b[1]:b[1] + b[3], b[0]:b[0] + b[2]]
        return float(s[:, :, 1].mean())
    sair = blobs[0]                                   # ESQUERDA = Sair (vermelho)
    if _meanG(sair) >= _meanG(blobs[-1]):
        return None                                   # esquerdo não é o mais vermelho -> aborta (seguro)
    return (sair[0] + sair[2] // 2, by0 + sair[1] + sair[3] // 2)


def bust_watch(hwnd, control, stop, *, seconds=0.0, period=4.0, cooldown=25.0, click=None,
               detect=None, on_bust=None):
    """THREAD de bust: a cada `period`s varre cada COLUNA; se achar o pop-up de CLASSIFICAÇÃO (bust),
    clica o botão SAIR (coords -> tela). Gated por control.execution_allowed() (só ARMADO). Cooldown
    longo por coluna (a tela some após o clique). Independente do hook. `click`/`detect` injetáveis.

    `on_bust(column, tile)` (opcional): chamado 1× por bust detectado (ANTES do cooldown re-barrar),
    p/ REGISTRAR o resultado do torneio (suprema_results). Best-effort: exceção nele NUNCA derruba o
    vigia nem impede o clique de Sair."""
    import time
    import suprema_click as C
    from PIL import ImageGrab
    if click is None:
        click = C._click_sendinput
    if detect is None:
        detect = find_sair
    last = {}
    t0 = time.time()
    while not stop.is_set() and (seconds <= 0 or time.time() - t0 < seconds):
        try:
            n = max(1, C.columns_from_window(hwnd))
            for i in range(n):
                tx, ty, tw, th = C.table_rect_for_room(hwnd, i, n)
                tile = ImageGrab.grab(bbox=(tx, ty, tx + tw, ty + th), all_screens=True)
                pos = detect(tile)
                if not pos:
                    continue
                if (time.time() - last.get(i, 0.0)) < cooldown:
                    continue
                last[i] = time.time()                     # 1 evento por bust (armado OU dry)
                if on_bust is not None:                   # REGISTRA o resultado (vale em DRY também:
                    try:                                  # o bust aconteceu independente de clicarmos)
                        on_bust(column=i, tile=tile)
                    except Exception:
                        pass
                if control is not None and not control.execution_allowed():
                    continue                              # DRY/pausado: registrou, mas NÃO clica Sair
                sx, sy = tx + int(pos[0]), ty + int(pos[1])
                print("[AG] BUSTOU do torneio (coluna %d/%d) -> clico SAIR em (%d,%d)"
                      % (i, n, sx, sy), flush=True)
                click(sx, sy)
        except Exception:
            pass
        stop.wait(period)
