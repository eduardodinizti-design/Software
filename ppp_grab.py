"""Captura + crop da mesa PPPoker p/ o clicker (item 1 do agente de produção por dados).

grab_frame(table_key, hwnd) -> VIEW da mesa (ou None). O VIEW leva TUDO que o ppp_execute precisa
p/ ler os botões e mapear o clique pra TELA corretamente:
  {crop: sub-imagem da mesa, origin:(ox,oy) do crop na janela, window_rect:(x,y,w,h) da janela na
   tela, full_size:(fw,fh) do frame cheio, box:(ox,oy,cw,ch)}
O offset `origin` é somado às coords do botão (que vêm relativas ao CROP) antes do to_screen — igual
ao operar_mesa (rect_frame_to_screen((x+tx, y+ty, ...))). Sem isso o clique cairia no lugar errado.

PPPoker (Unity/IL2CPP) desenha TODAS as mesas numa janela ÚNICA; detect_table_crops acha os recortes.
SINGLE-table (1 recorte) é direto. MULTI-table exige o binding roomid->recorte (tiles/StickyBinder);
enquanto não plugado, MULTI ABSTÉM (devolve None) — NUNCA devolve o crop errado, logo nunca clica a
mesa errada [[nvt-pppoker-sticky-bind]] [[nvt-multitable-tiled-bug]]. READ-ONLY (só captura de tela).

Reusa WindowCaptureEngine + detect_table_crops + _discover_rect (validados). Tudo injetável p/ teste
offline (capture/detect/discover)."""
from __future__ import annotations

_COMPLETE = 'COMPLETE_CANDIDATE'     # único status confiável de "mesa inteira" (detect_table_crops)


def imagegrab_capture(rect):
    """Captura a REGIÃO da janela no desktop COMPOSTO via ImageGrab (RGB ndarray). Diferente do
    BitBlt/PrintWindow do WindowCaptureEngine, isto ENXERGA janelas Unity/GPU (que dão PRETO no
    BitBlt — visto ao vivo no PPPoker do Eduardo). Mesma técnica da Suprema. None se falhar.
    `rect` = (x,y,w,h) lógico da janela na tela (pode ter x negativo em multi-monitor)."""
    try:
        import numpy as np
        from PIL import ImageGrab
        x, y, w, h = rect
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        return np.array(img)[:, :, :3]
    except Exception:
        return None


def imagegrab_capture_bgr(rect):
    """Captura em BGR (ImageGrab dá RGB). Os EXECUTORES de aposta (read_raise_panel/read_bet_panel)
    esperam BGR — confirmado ao vivo: read_raise_panel só acha os presets 2×/2.5×/3×/4× em BGR.
    (A detecção de MESA/crop, ao contrário, quer RGB — por isso a captura do grab segue RGB.)"""
    try:
        import cv2
        f = imagegrab_capture(rect)
        return cv2.cvtColor(f, cv2.COLOR_RGB2BGR) if f is not None else None
    except Exception:
        return None


def is_pppoker_felt(crop, *, min_blue=0.10, max_green_body=0.08):
    """Rede anti-OCLUSÃO: True se o recorte parece FELTRO AZUL do PPPoker, SEM feltro verde de Suprema
    por cima. Protege contra clicar numa janela sobreposta (o screenshot/clique pega o TOPO).
    Discriminador: VERDE só é esperado na FAIXA DE BOTÕES de baixo (F/C/Passar/Raise) — então mede o
    verde apenas no CORPO (topo ~82%, feltro) e reprova se houver verde demais lá (Suprema sobreposta,
    visto ~0.25) SEM confundir com os botões verdes do PPP (excluídos). Reprova também se o AZUL é fraco
    (popup cobrindo). crop em RGB. Falha-ABERTO (True) se não avalia — é rede EXTRA, não a trava
    principal (binding por roomid)."""
    try:
        import cv2
        if crop is None or getattr(crop, 'ndim', 0) != 3 or crop.shape[0] < 20 or crop.shape[1] < 20:
            return True
        hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        sat = (s > 40) & (v > 30)
        blue = float((((h >= 95) & (h <= 135)) & sat).mean())           # azul no recorte todo
        body = int(crop.shape[0] * 0.82)                                # corpo = topo 82% (sem botões)
        # verde = hue 45-88 (verde PURO da Suprema ~60-80). EXCLUI amarelo/dourado 35-45 (fichas, texto
        # "BB", botão dealer do PRÓPRIO PPPoker) que falso-positivava mesa limpa (clean~0.03, Suprema~0.25).
        gb = ((h[:body] >= 45) & (h[:body] < 88)) & sat[:body]
        green_body = float(gb.mean())                                   # verde no CORPO (feltro)
        return blue >= min_blue and green_body <= max_green_body
    except Exception:
        return True


def build_view(full_rgb, box, window_rect):
    """Monta o VIEW a partir do frame cheio + o box (x,y,w,h) do recorte da mesa + o rect da janela."""
    ox, oy, cw, ch = (int(v) for v in box)
    crop = full_rgb[oy:oy + ch, ox:ox + cw]
    fh, fw = full_rgb.shape[0], full_rgb.shape[1]
    return {'crop': crop, 'origin': (ox, oy), 'window_rect': window_rect,
            'full_size': (fw, fh), 'box': (ox, oy, cw, ch)}


def load_tiles_screen(path):
    """Lê o tiles.json de PROJEÇÃO: {"render":[rw,rh], "tiles":{roomid:[ux0,uy0,ux1,uy1]}} (rect de
    TELA Unity, px físico, Y de baixo). Devolve (render, {roomid: urect}). (None,{}) se falhar."""
    import json
    import os
    if not path or not os.path.exists(path):
        return (None, {})
    try:
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        render = d.get('render')
        if not (isinstance(render, list) and len(render) == 2 and render[0] and render[1]):
            return (None, {})
        tiles = {str(k): [float(x) for x in v] for k, v in (d.get('tiles') or {}).items()
                 if isinstance(v, list) and len(v) == 4}
        return ([float(render[0]), float(render[1])], tiles)
    except Exception:
        return (None, {})


def unity_rect_to_frame(urect, render, frame_size):
    """Rect de TELA Unity (px físico, Y de baixo) -> box no frame LÓGICO (x,y,w,h, Y de cima). Janela
    borderless (client==window, offset 0): fx=ux×(fw/rw); fy=(rh-uy_topo)×(fh/rh). PURA."""
    ux0, uy0, ux1, uy1 = urect
    rw, rh = render
    fw, fh = frame_size
    sx, sy = fw / rw, fh / rh
    fx = ux0 * sx
    fy = (rh - uy1) * sy             # uy1 = topo (Unity Y de baixo) -> topo no frame
    return (int(fx), int(fy), int((ux1 - ux0) * sx), int((uy1 - uy0) * sy))


def make_tiles_screen_source(path='logs/tiles.json'):
    """tiles_source() p/ o make_grab_proj: relê o tiles.json de projeção a cada chamada."""
    def source():
        return load_tiles_screen(path)
    return source


def make_grab_proj(hwnd, *, tiles_source, capture=None, discover_rect=None,
                   felt_check=is_pppoker_felt, log=print):
    """grab_frame(table_key, hwnd) por PROJEÇÃO (robusto a clutter/sobreposição): roomid -> rect de
    tela Unity (do readTilesScreen) -> converte p/ frame -> recorta DIRETO (sem detect_table_crops,
    sem contar recortes). Rede anti-oclusão (felt_check) abstém se a mesa estiver coberta. Abstém se
    não há tile p/ o roomid, sem render, ou o rect cai fora do frame. capture/discover injetáveis."""
    if discover_rect is None:
        from operar_mesa import _discover_rect as discover_rect
    if capture is None:
        capture = imagegrab_capture

    def grab_frame(table_key, hwnd_=hwnd):
        wr = discover_rect(hwnd_)
        if wr is None:
            log('[grab %s] sem rect da janela' % table_key)
            return None
        try:
            render, tiles = tiles_source()
        except Exception as e:
            log('[grab %s] tiles_source falhou: %s' % (table_key, e))
            return None
        urect = tiles.get(str(table_key)) or tiles.get(table_key)
        if not urect or not render:
            log('[grab %s] sem tile/render p/ este roomid -> abstém' % table_key)
            return None
        frame = capture(wr)
        if frame is None:
            log('[grab %s] sem frame' % table_key)
            return None
        fh, fwid = frame.shape[0], frame.shape[1]
        fx, fy, fcw, fch = unity_rect_to_frame(urect, render, (fwid, fh))
        if fx < 0 or fy < 0 or fx + fcw > fwid or fy + fch > fh or fcw <= 0 or fch <= 0:
            log('[grab %s] tile fora do frame -> abstém' % table_key)
            return None
        v = build_view(frame, (fx, fy, fcw, fch), wr)
        if felt_check and not felt_check(v['crop']):     # rede anti-oclusão
            log('[grab %s] recorte não é feltro PPPoker (oclusão?) -> abstém' % table_key)
            return None
        return v

    return grab_frame


def _overlap_frac(a, b):
    """Fração do retângulo `a` (x,y,w,h) que cai DENTRO de `b`."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return (ix * iy) / max(1, aw * ah)


def best_overlap_crop(proj_box, crops, *, min_overlap=0.5):
    """Entre os recortes COMPLETE, acha o que mais SOBREPÕE a caixa projetada (identidade do roomid).
    Devolve (crop, frac) se a sobreposição >= min_overlap; senão (None, frac) -> abstém."""
    best, bestf = None, 0.0
    for c in crops:
        f = _overlap_frac(proj_box, c.box)
        if f > bestf:
            best, bestf = c, f
    return (best, bestf) if bestf >= min_overlap else (None, bestf)


def expand_box(box, frame_size, *, pad_x=0.18, pad_top=0.08, pad_bottom=0.38):
    """Expande a caixa da projeção (que é o _rectTransform INTERNO, sem a linha de botões) p/ cobrir
    a mesa inteira — sobretudo PRA BAIXO (pad_bottom), onde ficam Fold/Check/Call/Aumentar. Clampa ao
    frame. PURA."""
    x, y, w, h = box
    fw, fh = frame_size
    nx = max(0, int(x - w * pad_x))
    ny = max(0, int(y - h * pad_top))
    nx2 = min(fw, int(x + w + w * pad_x))
    ny2 = min(fh, int(y + h + h * pad_bottom))
    return (nx, ny, max(1, nx2 - nx), max(1, ny2 - ny))


def make_grab_hybrid(hwnd, *, tiles_source, capture=None, detect=None, discover_rect=None,
                     max_tables=6, felt_check=is_pppoker_felt, log=print):
    """grab_frame por HÍBRIDO (robusto): projeção (readTilesScreen) dá a IDENTIDADE (rect por roomid).
    Quando detect_table_crops acha um recorte COMPLETE que SOBREPÕE a projeção, usa esse (mesa inteira,
    exato). Quando o detect falha/oscila (0 COMPLETE ou nenhum casa), usa a projeção EXPANDIDA (cobre
    os botões). Sempre ancorado no roomid; felt_check (anti-oclusão) abstém se coberta. Injetável."""
    if discover_rect is None:
        from operar_mesa import _discover_rect as discover_rect
    if capture is None:
        capture = imagegrab_capture
    if detect is None:
        from table_reading.automatic_table_crops import detect_table_crops as detect

    def grab_frame(table_key, hwnd_=hwnd):
        wr = discover_rect(hwnd_)
        if wr is None:
            log('[grab %s] sem rect da janela' % table_key)
            return None
        try:
            render, tiles = tiles_source()
        except Exception as e:
            log('[grab %s] tiles_source falhou: %s' % (table_key, e))
            return None
        urect = tiles.get(str(table_key)) or tiles.get(table_key)
        if not urect or not render:
            log('[grab %s] sem tile/render p/ este roomid -> abstém' % table_key)
            return None
        frame = capture(wr)
        if frame is None:
            log('[grab %s] sem frame' % table_key)
            return None
        fh, fwid = frame.shape[0], frame.shape[1]
        proj = unity_rect_to_frame(urect, render, (fwid, fh))
        try:
            crops = [c for c in detect(frame, max_tables=max_tables)
                     if getattr(c, 'status', None) == _COMPLETE]
        except Exception:
            crops = []
        crop, frac = best_overlap_crop(proj, crops) if crops else (None, 0.0)
        box = crop.box if crop is not None else expand_box(proj, (fwid, fh))   # detect OU projeção expandida
        v = build_view(frame, box, wr)
        if felt_check and not felt_check(v['crop']):
            log('[grab %s] recorte não é feltro PPPoker (oclusão?) -> abstém' % table_key)
            return None
        return v

    return grab_frame


def primary_monitor_rect():
    """(0, 0, w, h) do monitor PRINCIPAL em coords LÓGICAS (SM_CXSCREEN/CYSCREEN)."""
    import ctypes
    u = ctypes.windll.user32
    return (0, 0, int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1)))


def locate_tables_by_felt(frame_rgb, *, min_area_frac=0.015, pad_bottom_frac=0.22, pad_x_frac=0.03,
                          max_tables=6):
    """Acha TODAS as mesas pelos BLOBS DE FELTRO AZUL (robusto — detect_table_crops oscila). Cada blob
    azul >= min_area_frac vira uma caixa (x,y,w,h) ESTENDIDA pra baixo (barra de botões) + respiro
    lateral. Devolve a lista ORDENADA por x (esquerda->direita). [] se nada. PURA."""
    try:
        import cv2
        import numpy as np
        if frame_rgb is None or getattr(frame_rgb, 'ndim', 0) != 3:
            return []
        fh, fw = frame_rgb.shape[0], frame_rgb.shape[1]
        hsv = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        mask = np.uint8(((h >= 95) & (h <= 135) & (s > 40) & (v > 30))) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in cnts:
            if cv2.contourArea(c) < min_area_frac * fw * fh:
                continue
            x, y, w, h0 = cv2.boundingRect(c)
            px = int(w * pad_x_frac)
            nx = max(0, x - px)
            nx2 = min(fw, x + w + px)
            ny2 = min(fh, int(y + h0 + h0 * pad_bottom_frac))
            boxes.append((nx, y, nx2 - nx, ny2 - y))
        boxes.sort(key=lambda b: b[0])                           # esquerda -> direita
        return boxes[:max_tables]
    except Exception:
        return []


def locate_table_by_felt(frame_rgb, *, min_area_frac=0.03, pad_bottom_frac=0.22, pad_x_frac=0.03):
    """A MAIOR mesa pelo blob de feltro (p/ mesa única). None se não houver azul suficiente. PURA."""
    boxes = locate_tables_by_felt(frame_rgb, min_area_frac=min_area_frac,
                                  pad_bottom_frac=pad_bottom_frac, pad_x_frac=pad_x_frac)
    if not boxes:
        return None
    return max(boxes, key=lambda b: b[2] * b[3])


def make_grab_primary(*, capture=None, detect=None, felt_check=is_pppoker_felt, max_tables=6,
                      rect=None, log=print):
    """grab DIRETO do MONITOR PRINCIPAL. VALIDADO 25/11 (cursor caiu EXATO no Fold): capturando só o
    monitor principal (origem 0,0, 100% de escala), as coords da IMAGEM == coords de TELA — sem o
    offset da janela (-1280), sem projeção, SEM o mismatch de DPI do grab multi-monitor (a janela do
    PPPoker atravessa monitores com DPI diferente -> captura e clique desalinhavam). detect_table_crops
    acha a mesa no monitor; o view sai com window_rect=(0,0,w,h) e full_size=(w,h) -> rect_frame_to_screen
    é IDENTIDADE, o clique cai no botão. Pra MESA ÚNICA no monitor principal (ignora table_key -> pega a
    maior mesa COMPLETE que passa no felt-check). felt_check mantém a rede anti-oclusão."""
    if capture is None:
        capture = imagegrab_capture
    if detect is None:
        from table_reading.automatic_table_crops import detect_table_crops as detect

    def grab_frame(table_key=None, hwnd=None):
        pr = rect or primary_monitor_rect()
        frame = capture(pr)
        if frame is None:
            log('[grabP] sem frame do monitor principal')
            return None
        pw, ph = frame.shape[1], frame.shape[0]
        boxes = []
        felt_box = locate_table_by_felt(frame)          # ROBUSTO (blob de feltro) — método principal
        if felt_box is not None:
            boxes.append(felt_box)
        try:                                            # detect como reforço (quando acha, é preciso)
            boxes += [c.box for c in detect(frame, max_tables=max_tables)
                      if getattr(c, 'status', None) == _COMPLETE]
        except Exception:
            pass
        boxes.sort(key=lambda b: b[2] * b[3], reverse=True)   # maior primeiro (a mesa domina a tela)
        for x, y, w, h in boxes:
            if w < 150 or h < 250:
                continue
            crop = frame[y:y + h, x:x + w]
            if felt_check and not felt_check(crop):
                continue
            return build_view(frame, (x, y, w, h), (0, 0, pw, ph))   # origem 0,0 -> to_screen identidade
        log('[grabP] nenhuma mesa (feltro/detect) no monitor principal -> abstém')
        return None

    return grab_frame


def make_grab_primary_multi(*, tiles_source, capture=None, felt_check=is_pppoker_felt, rect=None,
                            max_tables=6, log=print):
    """MULTI-MESA no MONITOR PRINCIPAL. Acha N blobs de feltro (ordenados por x, esquerda->direita) e
    N roomids do tiles.json (ordenados pela x da PROJEÇÃO) e BINDA por ORDEM — robusto ao offset/DPI,
    pois a ORDEM relativa se preserva mesmo quando a coord absoluta não. Devolve o view da mesa pedida
    (table_key=roomid), coords de tela == coords da imagem (origem 0,0). ABSTÉM se nº de blobs != nº de
    roomids (binding incerto -> nunca clica a mesa errada [[nvt-pppoker-sticky-bind]])."""
    if capture is None:
        capture = imagegrab_capture

    def grab(table_key, hwnd=None):
        pr = rect or primary_monitor_rect()
        frame = capture(pr)
        if frame is None:
            log('[grapP*] sem frame do monitor principal'); return None
        pw, ph = frame.shape[1], frame.shape[0]
        blobs = locate_tables_by_felt(frame, max_tables=max_tables)       # ordenados por x
        if not blobs:
            log('[grabP*] nenhum feltro -> abstém'); return None
        try:
            render, tiles = tiles_source()
        except Exception as e:
            log('[grabP* %s] tiles_source falhou: %s' % (table_key, e)); return None
        if not tiles or not render:
            log('[grabP* %s] sem tiles/render -> abstém' % table_key); return None
        roomids = sorted(tiles.keys(), key=lambda rid: unity_rect_to_frame(tiles[rid], render, (pw, ph))[0])
        if len(roomids) != len(blobs):
            log('[grabP* %s] %d roomids x %d mesas na tela -> binding incerto, abstém'
                % (table_key, len(roomids), len(blobs)))
            return None
        key = str(table_key)
        if key not in roomids:
            log('[grabP* %s] roomid fora do tiles -> abstém' % table_key); return None
        box = blobs[roomids.index(key)]                                  # binding por ORDEM
        v = build_view(frame, box, (0, 0, pw, ph))
        if felt_check and not felt_check(v['crop']):
            log('[grabP* %s] recorte não é feltro (oclusão?) -> abstém' % table_key); return None
        return v

    return grab


def make_grab_primary_auto(*, tiles_source=None, capture=None, felt_check=is_pppoker_felt, rect=None,
                           max_tables=6, log=print):
    """Grab do MONITOR PRINCIPAL que ESCOLHE sozinho: >1 roomid no tiles.json -> multi (binding por
    ordem); senão -> single (a maior mesa). Assim o agente serve mesa única E multi-mesa com o mesmo
    grab. tiles_source opcional (sem ele, sempre single)."""
    single = make_grab_primary(capture=capture, felt_check=felt_check, rect=rect,
                               max_tables=max_tables, log=log)
    multi = (make_grab_primary_multi(tiles_source=tiles_source, capture=capture, felt_check=felt_check,
                                     rect=rect, max_tables=max_tables, log=log)
             if tiles_source is not None else None)

    def grab(table_key=None, hwnd=None):
        if multi is not None:
            try:
                _, tiles = tiles_source()
            except Exception:
                tiles = {}
            if tiles and len(tiles) > 1:
                return multi(table_key, hwnd)        # multi-mesa: binding por ordem
        return single(table_key, hwnd)               # mesa única: maior blob de feltro

    return grab


def load_tiles_world(path):
    """Lê logs/tiles.json {roomid: [wx0,wy0,wx1,wy1]} (cantos de MUNDO, do emitir_tiles.py). {} se falhar."""
    import json
    import os
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
        return {str(k): [float(x) for x in v] for k, v in d.items()
                if isinstance(v, list) and len(v) == 4}
    except Exception:
        return {}


def tiles_order_resolver(tiles_world):
    """resolve_crop_index (make_grab) DATA-DRIVEN por ORDEM world-x — sem projeção de tela (as coords
    do readTiles2 vêm em MUNDO Unity, mas a ORDEM esquerda->direita basta p/ casar roomid<->recorte).
    Ordena os roomids por world-x e devolve o índice (rank) do recorte da mesa `table_key`. Abstém
    (None) se o nº de recortes != nº de mesas conhecidas (painel aberto/parcial), ou roomid ausente —
    NUNCA cruza mesa [[nvt-pppoker-sticky-bind]]."""
    ordered = [r for r, _ in sorted(tiles_world.items(), key=lambda kv: kv[1][0])]  # esq->dir (world-x)

    def resolve(table_key, crops):
        if not ordered or len(crops) != len(ordered):
            return None
        tk = str(table_key)
        return ordered.index(tk) if tk in ordered else None

    return resolve


def make_tiles_resolver(tiles_path='logs/tiles.json'):
    """resolve_crop_index que RELÊ o tiles.json a cada chamada (o produtor reescreve ao vivo)."""
    def resolve(table_key, crops):
        return tiles_order_resolver(load_tiles_world(tiles_path))(table_key, crops)
    return resolve


def sticky_crop_resolver(binder, fresh_roomids):
    """resolve_crop_index p/ o make_grab, baseado no StickyBinder (posição->roomid grudento).
    Assume que o índice do recorte (crops ordenados cima->baixo/esq->dir) == a POSIÇÃO do tile.
    Devolve o índice cujo roomid grudado == table_key, ou None (abstém) se o bind não é confiável.
    O binder é alimentado ao vivo (binder.observe) com os binds confiantes (nameplate/carta); aqui
    só CONSULTAMOS — a seleção é offline-testável, a fonte do bind é a camada viva."""
    def resolve(table_key, crops):
        for i in range(len(crops)):
            rid = binder.roomid_for(i, fresh_roomids=fresh_roomids)
            if rid is not None and str(rid) == str(table_key):
                return i
        return None
    return resolve


def load_tiles(path):
    """Lê o sidecar de tiles {roomid: [x,y,w,h] na TELA} (escrito pelo emitter via ler_tiles.js:
    TableUIPanel._roomId + cantos do RectTransform — DATA-driven, sem vision). Tolerante: aceita
    {roomid:[x,y,w,h]} ou {'tiles':{...}} / lista [{roomid,rect:[x0,y0,x1,y1]}]. {} se falhar."""
    import json
    import os
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as fh:
            d = json.load(fh)
    except Exception:
        return {}
    if isinstance(d, dict) and 'tiles' in d and isinstance(d['tiles'], (list, dict)):
        d = d['tiles']
    out = {}
    items = d.items() if isinstance(d, dict) else enumerate(d)
    for k, v in items:
        rid = str(v.get('roomid')) if isinstance(v, dict) else str(k)
        rect = v.get('rect') if isinstance(v, dict) else v
        if not rect or len(rect) != 4:
            continue
        x0, y0, a, b = (float(t) for t in rect)
        # aceita [x,y,w,h] (a=w,b=h) OU [x0,y0,x1,y1] (a>x0 e b>y0 => cantos)
        if a > x0 and b > y0 and (a - x0) < 10000 and (a > x0 + 1):
            w, h = a - x0, b - y0            # cantos -> largura/altura
        else:
            w, h = a, b
        out[rid] = (int(x0), int(y0), int(w), int(h))
    return out


def make_grab_tiles(hwnd, *, tiles_source, capture=None, discover_rect=None, felt_check=is_pppoker_felt, log=print):
    """grab_frame(table_key, hwnd) DATA-DRIVEN: roomid -> retângulo do tile (do IL2CPP) -> crop.
    Dispensa detect_table_crops E vision: o emitter dá o rect exato de cada mesa por roomid. Multi-
    mesa robusto (nunca cruza). Abstém se não há tile p/ o roomid ou se o tile cai fora do frame.
      tiles_source() -> {roomid: (x,y,w,h) na TELA}   (ex.: lambda: load_tiles('logs/tiles.json'))
    capture/discover_rect injetáveis p/ teste."""
    if discover_rect is None:
        from operar_mesa import _discover_rect as discover_rect
    if capture is None:
        capture = imagegrab_capture

    def grab_frame(table_key, hwnd_=hwnd):
        wr = discover_rect(hwnd_)
        if wr is None:
            log('[grab %s] sem rect da janela' % table_key)
            return None
        try:
            tiles = tiles_source() or {}
        except Exception as e:
            log('[grab %s] tiles_source falhou: %s' % (table_key, e))
            return None
        rect = tiles.get(str(table_key)) or tiles.get(table_key)
        if not rect:
            log('[grab %s] sem tile p/ este roomid -> abstém' % table_key)
            return None
        frame = capture(wr)
        if frame is None:
            log('[grab %s] sem frame' % table_key)
            return None
        wx, wy = wr[0], wr[1]
        sx, sy, sw, sh = rect
        fx, fy = int(sx - wx), int(sy - wy)       # tela -> coord do frame (frame(0,0)=canto da janela)
        fh, fwid = frame.shape[0], frame.shape[1]
        if fx < 0 or fy < 0 or fx + sw > fwid or fy + sh > fh or sw <= 0 or sh <= 0:
            log('[grab %s] tile fora do frame -> abstém' % table_key)
            return None
        v = build_view(frame, (fx, fy, int(sw), int(sh)), wr)
        if felt_check and not felt_check(v['crop']):
            log('[grab %s] recorte não é feltro PPPoker (oclusão?) -> abstém' % table_key)
            return None
        return v

    return grab_frame


def make_grab(hwnd, *, capture=None, detect=None, discover_rect=None, max_tables=6,
              resolve_crop_index=None, felt_check=is_pppoker_felt, log=print):
    """Fábrica do grab_frame(table_key, hwnd) (camada VIVA; capture/detect/discover injetáveis).
      discover_rect(hwnd) -> (x,y,w,h) | None       (default: operar_mesa._discover_rect)
      capture(rect) -> frame_rgb | None             (default: imagegrab_capture — desktop composto)
      detect(rgb, max_tables=...) -> [TableCrop]    (default: table_reading detect_table_crops)
      resolve_crop_index(table_key, crops) -> int | None  (MULTI-mesa: qual recorte é a mesa
         `table_key`; crops já ordenados esquerda->direita/cima->baixo. None = não sabe -> abstém)
    Só considera recortes status=COMPLETE_CANDIDATE (ignora UNCERTAIN/parcial = ruído de UI).
    1 mesa completa -> VIEW dela. 0 -> None. >1 -> usa resolve_crop_index; sem ele (ou index None/
    fora do range) ABSTÉM — NUNCA clica a mesa errada [[nvt-pppoker-sticky-bind]]. Nunca lança."""
    if discover_rect is None:
        from operar_mesa import _discover_rect as discover_rect
    if capture is None:
        capture = imagegrab_capture
    if detect is None:
        from table_reading.automatic_table_crops import detect_table_crops as detect

    def grab_frame(table_key, hwnd_=hwnd):
        wr = discover_rect(hwnd_)
        if wr is None:
            log('[grab %s] sem rect da janela' % table_key)
            return None
        try:
            frame = capture(wr)
        except Exception as e:
            log('[grab %s] captura falhou: %s' % (table_key, e))
            return None
        if frame is None:
            log('[grab %s] sem frame' % table_key)
            return None
        try:
            crops = [c for c in detect(frame, max_tables=max_tables)
                     if getattr(c, 'status', None) == _COMPLETE]
        except Exception as e:
            log('[grab %s] detect_table_crops falhou: %s' % (table_key, e))
            return None
        if not crops:
            log('[grab %s] nenhuma mesa COMPLETE no frame' % table_key)
            return None
        # Com resolvedor (binding por tiles), ele é AUTORITATIVO p/ qualquer nº de recortes: casa
        # roomid<->recorte e ABSTÉM se a contagem de recortes != nº de mesas (ex.: 1 COMPLETE mas 2
        # mesas vivas -> NUNCA devolve o recorte da outra mesa). Sem resolvedor, só single-table.
        if resolve_crop_index is not None:
            try:
                idx = resolve_crop_index(table_key, crops)
            except Exception as e:
                log('[grab %s] resolvedor de binding falhou: %s' % (table_key, e))
                return None
            if not isinstance(idx, int) or not (0 <= idx < len(crops)):
                log('[grab %s] binding incerto p/ a mesa -> abstém (nunca clica a errada)' % table_key)
                return None
            box = crops[idx].box
        elif len(crops) == 1:
            box = crops[0].box
        else:
            log('[grab %s] multi-mesa (%d completas) sem resolvedor -> abstém' % (table_key, len(crops)))
            return None
        v = build_view(frame, box, wr)
        if felt_check and not felt_check(v['crop']):     # rede anti-oclusão (Suprema/popup por cima)
            log('[grab %s] recorte não é feltro PPPoker (oclusão?) -> abstém' % table_key)
            return None
        return v

    return grab_frame
