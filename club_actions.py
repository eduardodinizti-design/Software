"""Primitivas de AÇÃO da troca de clube: localizar o tile-alvo (p/ revalidação do
clique) e rolar a grade. Puras/injetáveis — a execução real é gated pelo BotControl.

- `locate_club_in_frame(frame, target, ocr)`: devolve o RECT do NOME do clube-alvo
  no frame (coords do frame), ou None se não visível/ambíguo. É o `locate_frame_rect`
  que o CursorController chama a CADA validação (inicial + na chegada), então a
  ordem da grade mudar ou o tile mover NÃO causa clique no clube errado — relê sempre.
- `scroll_grid_once(adapter, control, panel_rect, ...)`: rola a grade UMA vez via
  drag (click-and-hold). GATED: só arrasta se `control.execution_allowed()`. A
  grade rola e a ordem muda, então o chamador relê após cada rolagem.
"""
from club_grid import find_grid_crop, read_club_grid, match_club


def locate_club_in_frame(frame, target, *, ocr):
    """(x, y, w, h) do nome do clube-alvo no frame, ou None. Ambíguo -> None (não
    clica entre clubes parecidos; a decisão é a verificação ou busca exata)."""
    g = find_grid_crop(frame)
    if not g['ok']:
        return None
    ox, oy = g['origin']
    tiles = read_club_grid(g['crop'], ocr=ocr)
    m = match_club(target, [t['name'] for t in tiles])
    if m['ambiguous'] or m['index'] is None:
        return None
    x0, y0, x1, y1 = tiles[m['index']]['name_rect']
    return (ox + x0, oy + y0, x1 - x0, y1 - y0)


def scroll_grid_once(adapter, control, *, panel_rect, drag_frac=0.5, reveal='below',
                     settle_s=0.05):
    """Rola a grade UMA vez. GATED: nada é enviado sem RUNNING. reveal='below'
    arrasta o conteúdo p/ CIMA (revela clubes mais abaixo); 'above' o contrário.
    O drag solta o botão garantido (try/finally do adaptador). Devolve
    dict(ok, sent, reason, drag). A direção certa é confirmada ao vivo."""
    px, py, pw, ph = panel_rect
    cx = px + pw // 2
    span = max(1, int(ph * drag_frac) // 2)
    mid = py + ph // 2
    y0, y1 = (mid + span, mid - span) if reveal == 'below' else (mid - span, mid + span)
    if control is not None and not control.execution_allowed():
        return dict(ok=False, sent=False, reason='BOT_NOT_RUNNING', drag=None)
    rep = adapter.drag(cx, y0, cx, y1, settle_s=settle_s)
    return dict(ok=bool(rep.get('released')), sent=True,
                reason=None if rep.get('released') else 'RELEASE_UNCONFIRMED', drag=rep)
