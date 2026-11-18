"""Executor da troca de clube — a corrente ARMÁVEL, atrás do gate.

Corrente:
  [idempotência] lê o clube atual; se já é o alvo -> NOOP (não toca em nada).
  [busca] captura -> localiza o alvo na grade (RELÊ a cada passo: a ordem muda) ->
          achou? CLIQUE gated+revalidado (CursorController: min-jerk, revalida na
          chegada, clique único) -> VERIFICA relendo o nome do clube == alvo.
          Não achou? ROLA a grade (drag gated) e repete até achar / FIM / MAX.

Segurança: começa PAUSADO (BotControl); nada é enviado sem Ctrl+Alt+R. DRY-RUN por
padrão (planeja e descreve, não clica). O clique real é AÇÃO EM CONTA REAL — rode
com você no controle do gate (Ctrl+Alt+P pausa na hora). Dependências são injetáveis
(engine/adapter/control/discover_rect/ocr) para teste offline.

Uso ao vivo:
  python operar_troca_clube.py --hwnd 0xae0902 --target "AK Amakha Club"          # DRY-RUN
  python operar_troca_clube.py --hwnd 0xae0902 --target "AK Amakha Club" --arm    # arma (Ctrl+Alt+R)
"""
import argparse
import time

from club_actions import locate_club_in_frame, scroll_grid_once
from club_grid import (find_grid_crop, header_matches, normalize, read_carousel_card,
                       read_club_grid, read_club_header)
from cursor_controller import CursorController, Intent, make_intervention_check
from ocr_locate import locate_word
from screen_coords import frame_to_screen, rect_frame_to_screen


def _read_current_club_live(engine, hwnd, ocr):
    """Nome do clube ATUAL ou None — lido pelo cabeçalho ANCORADO em 'ID do clube'
    (read_club_header), robusto ao tamanho do crop. Vazio/None = não estamos dentro
    de um clube (ex.: no seletor/carrossel, onde não há 'ID do clube')."""
    frame, _ = engine.capture_frame(hwnd=hwnd)
    if frame is None:
        return None
    return read_club_header(frame, ocr=ocr) or None


def _header_matches_live(engine, hwnd, target, ocr):
    """True se o clube ATUAL corresponde a `target` (match robusto por substring)."""
    frame, _ = engine.capture_frame(hwnd=hwnd)
    return frame is not None and header_matches(frame, target, ocr=ocr)


def _click_target_club(engine, hwnd, target, *, adapter, control, ocr, discover_rect,
                       deadline_s=6.0, verify_tries=6, verify_wait_s=0.5):
    """UM clique gated+revalidado no tile do clube-alvo. O validator RELÊ o alvo no
    frame fresco (ordem muda!) e remapeia p/ a tela; o verifier confirma a troca
    relendo o nome do clube. Devolve o dict do CursorController."""
    def validator(intent, now):
        wr = discover_rect(hwnd)
        if wr is None:
            return dict(ok=False, reasons=['WINDOW_GONE'])
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, reasons=['NO_FRAME'])
        fh, fw = frame.shape[:2]
        rect = locate_club_in_frame(frame, target, ocr=ocr)
        if rect is None:
            return dict(ok=False, reasons=['TARGET_NOT_FOUND'])
        return dict(ok=True, identity=target,
                    target_rect=rect_frame_to_screen(rect, window_rect=wr, frame_size=(fw, fh)))

    def verifier(intent, now):
        # Entrar no clube TRANSICIONA de tela: re-tenta por alguns segundos (o verifier
        # do CursorController roda logo após o clique, antes de a tela do clube carregar).
        for i in range(verify_tries):
            frame, _ = engine.capture_frame(hwnd=hwnd)
            if frame is not None and header_matches(frame, target, ocr=ocr):
                return dict(confirmed=True)
            if i < verify_tries - 1:
                time.sleep(verify_wait_s)
        return dict(confirmed=False)

    intent = Intent(id='club-%s-%d' % ((target or '')[:12], int(time.time() * 1000)),
                    action='CLICK', source_key=target, target_rect=(0, 0, 1, 1),
                    deadline=time.monotonic() + deadline_s, expected=dict(club=target))
    ctrl = CursorController(input_adapter=adapter, validator=validator, verifier=verifier,
                            bot_control=control, cancel_check=make_intervention_check(adapter),
                            arrival_tol=12.0)
    return ctrl.execute(intent)


def ensure_club_live(target, *, engine, hwnd, adapter, control, ocr, discover_rect,
                     max_scrolls=10, dry_run=True, settle_s=0.4):
    """Garante que o lobby está no clube `target`. dry_run=True PLANEJA (não envia).
    Devolve dict(ok, action, ...). Ações: NOOP_JA_NO_CLUBE / PLANO_CLICAR / TROCADO /
    PLANO_ROLAR / TROCA_NAO_CONFIRMADA / SEM_GRADE / SCROLL_FALHOU / NAO_ENCONTRADO /
    SEM_FRAME / ALVO_INVALIDO."""
    if not (isinstance(target, str) and target.strip()):
        return dict(ok=False, action='ALVO_INVALIDO', reason='alvo vazio', scrolls=0)

    if _header_matches_live(engine, hwnd, target, ocr):
        return dict(ok=True, action='NOOP_JA_NO_CLUBE', scrolls=0)

    for step in range(max_scrolls + 1):
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, action='SEM_FRAME', reason='captura falhou', scrolls=step)
        rect = locate_club_in_frame(frame, target, ocr=ocr)
        if rect is not None:
            if dry_run:
                return dict(ok=True, action='PLANO_CLICAR', target_rect_frame=rect, scrolls=step)
            res = _click_target_club(engine, hwnd, target, adapter=adapter, control=control,
                                     ocr=ocr, discover_rect=discover_rect)
            if res.get('state') == 'DONE':
                return dict(ok=True, action='TROCADO', scrolls=step, click=res)
            return dict(ok=False, action='TROCA_NAO_CONFIRMADA', scrolls=step, click=res,
                        reason=','.join(res.get('reasons', [])) or res.get('state'))
        # find_grid_crop só LOCALIZA; a grade é real apenas se houver NOME de clube
        # legível (senão é outra tela com verde — ex.: banner promo dentro de um clube).
        g = find_grid_crop(frame)
        has_clubs = g['ok'] and any(t['name'] for t in read_club_grid(g['crop'], ocr=ocr))
        if not has_clubs:
            return dict(ok=False, action='SEM_GRADE',
                        reason=g['reason'] if not g['ok'] else 'sem nomes de clube legíveis',
                        scrolls=step, hint='abra a lista de clubes para a troca')
        panel = (g['origin'][0], g['origin'][1], g['crop'].shape[1], g['crop'].shape[0])
        if dry_run:
            return dict(ok=False, action='PLANO_ROLAR', scrolls=step, panel_rect=panel,
                        reason='alvo não visível nesta tela; rolaria para procurar')
        if step == max_scrolls:
            return dict(ok=False, action='NAO_ENCONTRADO', reason='MAX_SCROLLS', scrolls=step)
        sc = scroll_grid_once(adapter, control, panel_rect=panel)
        if not sc['sent'] or not sc['ok']:
            return dict(ok=False, action='SCROLL_FALHOU', reason=sc['reason'], scrolls=step)
        time.sleep(settle_s)
    return dict(ok=False, action='NAO_ENCONTRADO', reason='MAX_SCROLLS', scrolls=max_scrolls)


def _gated_click_frame_point(adapter, control, discover_rect, hwnd, frame, pt):
    """Clique GATED num ponto do frame (mapeado p/ a tela). Para alvos ESTÁTICOS
    (item de menu) — sem revalidação de trajetória. Nada sem RUNNING."""
    if control is not None and not control.execution_allowed():
        return dict(ok=False, reason='BOT_NOT_RUNNING')
    wr = discover_rect(hwnd)
    if wr is None:
        return dict(ok=False, reason='WINDOW_GONE')
    fh, fw = frame.shape[:2]
    sx, sy = frame_to_screen(pt, window_rect=wr, frame_size=(fw, fh))
    adapter.move_to(sx, sy)
    rep = adapter.click_once(sx, sy)
    return dict(ok=bool(rep.get('released')), screen=(sx, sy), click=rep)


def ensure_club_via_search(target, *, engine, hwnd, adapter, keyboard, control, ocr,
                           discover_rect, dry_run=True, settle_s=0.7):
    """Troca para `target` pela BUSCA (rota robusta, ignora ordem/scroll): no SELETOR,
    clica 'Pesquisar' -> DIGITA o nome -> a grade filtra -> clica o tile do resultado
    (relê/localiza, gated+revalidado) -> VERIFICA. dry_run PLANEJA (não envia).
    Requer o adaptador de teclado (keyboard)."""
    if not (isinstance(target, str) and target.strip()):
        return dict(ok=False, action='ALVO_INVALIDO', reason='alvo vazio')
    if _header_matches_live(engine, hwnd, target, ocr):
        return dict(ok=True, action='NOOP_JA_NO_CLUBE')
    frame, _ = engine.capture_frame(hwnd=hwnd)
    if frame is None:
        return dict(ok=False, action='SEM_FRAME', reason='captura falhou')
    fw = frame.shape[1]
    region = (1900.0 / fw, 0.45, 2700.0 / fw, 0.62)        # menu no inf-dir do painel
    # SÓ a vista de TILES tem BUSCA POR NOME (menu 'Pesquisar'). A lupa do CARROSSEL
    # NÃO é busca: abre 'Entrar em um clube' por ID (descoberto ao vivo 17/11) — por
    # isso não é usada aqui.
    pt = locate_word(frame, ['Pesquisar'], region=region)
    if pt is None:
        return dict(ok=False, action='SEM_BUSCA',
                    reason="'Pesquisar' não encontrado — vá para a GRADE DE TILES (Trocar exibição)")
    if dry_run:
        return dict(ok=True, action='PLANO_BUSCAR', pesquisar_pt=pt, target=target,
                    reason="clicaria 'Pesquisar' em %s, digitaria %r e clicaria no resultado"
                           % (pt, target))

    if control is not None and not control.execution_allowed():
        return dict(ok=False, action='GATE_FECHADO', reason='bot não está RUNNING')
    c1 = _gated_click_frame_point(adapter, control, discover_rect, hwnd, frame, pt)
    if not c1['ok']:
        return dict(ok=False, action='CLICK_PESQUISAR_FALHOU', reason=c1.get('reason'))
    time.sleep(0.4)
    keyboard.clear_field(40)                                # campo limpo
    keyboard.type_text(target.strip())                     # filtra a grade
    time.sleep(settle_s)
    res = _click_target_club(engine, hwnd, target, adapter=adapter, control=control,
                             ocr=ocr, discover_rect=discover_rect)
    if res.get('state') == 'DONE':
        return dict(ok=True, action='TROCADO', via='busca', click=res)
    return dict(ok=False, action='TROCA_NAO_CONFIRMADA', via='busca', click=res,
                reason=','.join(res.get('reasons', [])) or res.get('state'))


def _gated_drag_frame(adapter, control, discover_rect, hwnd, frame, p0, p1, *, settle_s=0.05):
    """Drag GATED entre dois pontos do frame (mapeados p/ a tela). Para o SWIPE do
    carrossel. Nada sem RUNNING."""
    if control is not None and not control.execution_allowed():
        return dict(ok=False, reason='BOT_NOT_RUNNING')
    wr = discover_rect(hwnd)
    if wr is None:
        return dict(ok=False, reason='WINDOW_GONE')
    fh, fw = frame.shape[:2]
    s0 = frame_to_screen(p0, window_rect=wr, frame_size=(fw, fh))
    s1 = frame_to_screen(p1, window_rect=wr, frame_size=(fw, fh))
    rep = adapter.drag(s0[0], s0[1], s1[0], s1[1], settle_s=settle_s)
    return dict(ok=bool(rep.get('released')), drag=rep)


def _verify_entered_live(engine, hwnd, target, ocr, *, tries=6, wait_s=0.5):
    """Confirma a ENTRADA no clube relendo o cabeçalho, re-tentando enquanto a tela
    transiciona. True se confirmou."""
    for i in range(tries):
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is not None and header_matches(frame, target, ocr=ocr):
            return True
        if i < tries - 1:
            time.sleep(wait_s)
    return False


def ensure_club_via_carousel(target, *, engine, hwnd, adapter, control, ocr, discover_rect,
                             dry_run=True, max_swipes=12, settle_s=0.6):
    """Troca para `target` pela vista de CARROSSEL (uma carta por vez, 'N/M'): lê o card
    atual; se CONTÉM o alvo, clica o card (entra) e VERIFICA; senão DESLIZA ao próximo e
    repete, até achar ou dar a volta. dry_run PLANEJA. Match por substring (tolera ruído
    do ícone no nome do card)."""
    if not (isinstance(target, str) and target.strip()):
        return dict(ok=False, action='ALVO_INVALIDO', reason='alvo vazio')
    if _header_matches_live(engine, hwnd, target, ocr):
        return dict(ok=True, action='NOOP_JA_NO_CLUBE')
    tgt_ns = normalize(target).replace(' ', '')
    for step in range(max_swipes + 1):
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, action='SEM_FRAME', reason='captura falhou')
        card = read_carousel_card(frame, ocr=ocr)
        if card is None:
            return dict(ok=False, action='SEM_CARROSSEL',
                        reason='não é a vista de carrossel de clube')
        if tgt_ns and tgt_ns in card['name'].casefold().replace(' ', ''):
            if dry_run:
                return dict(ok=True, action='PLANO_CLICAR_CARD', card_click=card['card_click'],
                            card=card['name'], idx=card['idx'])
            c = _gated_click_frame_point(adapter, control, discover_rect, hwnd, frame, card['card_click'])
            if not c['ok']:
                return dict(ok=False, action='CLICK_CARD_FALHOU', reason=c.get('reason'))
            if _verify_entered_live(engine, hwnd, target, ocr):
                return dict(ok=True, action='TROCADO', via='carrossel')
            return dict(ok=False, action='TROCA_NAO_CONFIRMADA', via='carrossel')
        # card atual não é o alvo -> deslizar ao próximo
        if dry_run:
            return dict(ok=False, action='PLANO_SWIPE', card=card['name'],
                        idx=card['idx'], total=card['total'], swipe=card['swipe'])
        if step >= card['total']:                 # deu a volta sem achar
            return dict(ok=False, action='NAO_ENCONTRADO', reason='rodou os cards', total=card['total'])
        p0, p1 = card['swipe']
        sw = _gated_drag_frame(adapter, control, discover_rect, hwnd, frame, p0, p1)
        if not sw['ok']:
            return dict(ok=False, action='SWIPE_FALHOU', reason=sw.get('reason'))
        time.sleep(settle_s)
    return dict(ok=False, action='NAO_ENCONTRADO', reason='max_swipes')


def ensure_club_any_view(target, *, engine, hwnd, adapter, control, ocr, discover_rect,
                         max_scrolls=10, dry_run=True):
    """Troca para `target` AUTO-DETECTANDO a vista: tenta a GRADE DE TILES; se não for
    (SEM_GRADE), tenta o CARROSSEL. Idempotência e verificação já embutidas em cada um."""
    r = ensure_club_live(target, engine=engine, hwnd=hwnd, adapter=adapter, control=control,
                         ocr=ocr, discover_rect=discover_rect, max_scrolls=max_scrolls,
                         dry_run=dry_run)
    if r.get('action') == 'SEM_GRADE':
        rc = ensure_club_via_carousel(target, engine=engine, hwnd=hwnd, adapter=adapter,
                                      control=control, ocr=ocr, discover_rect=discover_rect,
                                      dry_run=dry_run)
        if rc.get('action') != 'SEM_CARROSSEL':      # era carrossel -> usa esse resultado
            return rc
    return r


def _discover_rect(hwnd, *, tries=4, delay=0.15):
    from table_discovery.pppoker import discover_pppoker
    for i in range(max(1, tries)):
        ws = [w for w in discover_pppoker().get('windows', []) if w['hwnd'] == hwnd]
        if ws:
            return (ws[0]['x'], ws[0]['y'], ws[0]['w'], ws[0]['h'])
        if i < tries - 1:
            time.sleep(delay)
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True)
    p.add_argument('--target', required=True, help='Clube-alvo (nome como no lobby)')
    p.add_argument('--arm', action='store_true', help='Usa o cursor REAL (começa PAUSADO)')
    p.add_argument('--search', action='store_true',
                   help='Rota de BUSCA (lupa Pesquisar -> digitar nome -> resultado), '
                        'em vez de rolar os tiles. Precisa estar no seletor de clubes.')
    p.add_argument('--max-scrolls', type=int, default=10)
    p.add_argument('--no-hotkeys', action='store_true')
    p.add_argument('--arm-timeout', type=float, default=60.0,
                   help='Segundos esperando Ctrl+Alt+R antes de desistir (com --arm)')
    args = p.parse_args(argv)

    from bot_control import BotControl, HotkeyListener
    from cursor_input_win import WindowsCursorInput
    from keyboard_input_win import WindowsKeyboardInput
    from table_reading.ocr_runtime import image_to_string
    from table_reading.pipeline import configure_ocr
    from window_capture_engine import WindowCaptureEngine

    st = configure_ocr()
    ocr = lambda g: image_to_string(g, config='--psm 7')
    engine = WindowCaptureEngine()
    control = BotControl()
    adapter = WindowsCursorInput() if args.arm else None
    keyboard = WindowsKeyboardInput() if args.arm else None
    listener = HotkeyListener(control) if (args.arm and not args.no_hotkeys) else None
    if listener:
        listener.start()

    print('=' * 70)
    print('TROCA DE CLUBE | modo=%s | alvo=%r' % ('ARMADO' if args.arm else 'DRY-RUN', args.target))
    print('OCR:', st.get('status'), '| começa PAUSADO — Ctrl+Alt+R arma, Ctrl+Alt+P pausa')
    print('=' * 70)

    if args.arm:
        print('>>> Aperte Ctrl+Alt+R para ARMAR (esperando até %.0fs)...' % args.arm_timeout)
        t0 = time.monotonic()
        while not control.execution_allowed() and time.monotonic() - t0 < args.arm_timeout:
            time.sleep(0.1)
        if not control.execution_allowed():
            print('Não armado a tempo — nada enviado.'); return 1

    if args.search:
        r = ensure_club_via_search(args.target, engine=engine, hwnd=args.hwnd,
                                   adapter=adapter, keyboard=keyboard, control=control,
                                   ocr=ocr, discover_rect=_discover_rect, dry_run=not args.arm)
    else:
        r = ensure_club_any_view(args.target, engine=engine, hwnd=args.hwnd, adapter=adapter,
                                 control=control, ocr=ocr, discover_rect=_discover_rect,
                                 max_scrolls=args.max_scrolls, dry_run=not args.arm)
    print('RESULTADO:', r.get('action'), '| ok=%s' % r.get('ok'),
          '| %s' % (r.get('reason') or ''))
    if r.get('action') == 'PLANO_CLICAR':
        print('  clicaria (frame) em rect=%s [DRY-RUN — nada enviado]' % (r['target_rect_frame'],))
    if r.get('action') == 'PLANO_CLICAR_CARD':
        print('  clicaria o card %r em %s [DRY-RUN — nada enviado]' % (r.get('card'), r.get('card_click')))
    if r.get('action') == 'PLANO_BUSCAR':
        print("  clicaria 'Pesquisar' em %s, digitaria %r [DRY-RUN — nada enviado]"
              % (r['pesquisar_pt'], r['target']))
    return 0 if r.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
