"""Localiza uma PALAVRA de UI na tela e devolve o ponto de clique (coords do frame).

Usa pytesseract.image_to_data (caixas por palavra) — âncora robusta para itens de
menu/botões com rótulo de texto (ex.: "Pesquisar", "Trocar exibição"), em vez de
coordenadas fixas que mudam com a posição da janela. Requer configure_ocr() antes.
"""


def locate_word(frame, targets, *, region=None, psm=6, min_conf=30):
    """Centro (x, y) no FRAME da 1ª palavra de `targets` encontrada (case-insensitive,
    acento/pontuação ignorados nas pontas), ou None. `region=(x0,y0,x1,y1)` em FRAÇÕES
    do frame limita a busca (e acelera). `targets`: str ou lista de str."""
    import cv2
    import pytesseract
    if isinstance(targets, str):
        targets = [targets]
    tset = {t.strip().lower() for t in targets if t.strip()}
    if not tset:
        return None
    h, w = frame.shape[:2]
    if region:
        fx0, fy0, fx1, fy1 = region
        x0, y0 = max(0, int(fx0 * w)), max(0, int(fy0 * h))
        x1, y1 = min(w, int(fx1 * w)), min(h, int(fy1 * h))
    else:
        x0, y0, x1, y1 = 0, 0, w, h
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    g = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    d = pytesseract.image_to_data(g, config='--psm %d' % psm,
                                  output_type=pytesseract.Output.DICT)
    for i, raw in enumerate(d['text']):
        word = raw.strip().strip('.:,;').lower()
        if not word:
            continue
        try:
            conf = float(d['conf'][i])
        except (TypeError, ValueError):
            conf = -1.0
        if word in tset and conf >= min_conf:
            return (x0 + d['left'][i] + d['width'][i] // 2,
                    y0 + d['top'][i] + d['height'][i] // 2)
    return None
