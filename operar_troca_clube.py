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

from club_actions import find_search_lupa, locate_club_in_frame, scroll_grid_once
from club_grid import find_grid_crop, read_club_grid, read_current_club
from club_switcher import same_club
from cursor_controller import CursorController, Intent, make_intervention_check
from lobby_runner import find_lobby_crop
from ocr_locate import locate_word
from screen_coords import frame_to_screen, rect_frame_to_screen


def _read_current_club_live(engine, hwnd, ocr, *, min_badges=3):
    """Clube ATUAL (dentro de um clube) ou None. Só confia quando há uma lista de
    torneios de verdade (>= min_badges badges de buy-in) — senão é a grade/outra
    tela e 'clube atual' não se aplica (não inventa estado)."""
    frame, _ = engine.capture_frame(hwnd=hwnd)
    if frame is None:
        return None
    crop, _box, nb = find_lobby_crop(frame)
    if crop is None or nb < min_badges:
        return None
    return read_current_club(crop, ocr=ocr)


def _click_target_club(engine, hwnd, target, *, adapter, control, ocr, discover_rect,
                       deadline_s=6.0):
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
        cur = _read_current_club_live(engine, hwnd, ocr)
        return dict(confirmed=bool(cur and same_club(cur, target)), current=cur)

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

    cur = _read_current_club_live(engine, hwnd, ocr)
    if cur and same_club(cur, target):
        return dict(ok=True, action='NOOP_JA_NO_CLUBE', current=cur, scrolls=0)

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
    cur = _read_current_club_live(engine, hwnd, ocr)
    if cur and same_club(cur, target):
        return dict(ok=True, action='NOOP_JA_NO_CLUBE', current=cur)
    frame, _ = engine.capture_frame(hwnd=hwnd)
    if frame is None:
        return dict(ok=False, action='SEM_FRAME', reason='captura falhou')
    fw = frame.shape[1]
    region = (1900.0 / fw, 0.45, 2700.0 / fw, 0.62)        # menu no inf-dir do painel
    pt = locate_word(frame, ['Pesquisar'], region=region)   # vista de TILES (texto)
    via = 'texto'
    if pt is None:
        pt = find_search_lupa(frame)                         # vista de CARROSSEL (ícone)
        via = 'lupa'
    if pt is None:
        return dict(ok=False, action='SEM_BUSCA',
                    reason="busca não encontrada ('Pesquisar'/lupa) — está no seletor/carrossel de clubes?")
    if dry_run:
        return dict(ok=True, action='PLANO_BUSCAR', pesquisar_pt=pt, target=target, via=via,
                    reason="clicaria a busca (%s) em %s, digitaria %r e clicaria no resultado"
                           % (via, pt, target))

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
        r = ensure_club_live(args.target, engine=engine, hwnd=args.hwnd, adapter=adapter,
                             control=control, ocr=ocr, discover_rect=_discover_rect,
                             max_scrolls=args.max_scrolls, dry_run=not args.arm)
    print('RESULTADO:', r.get('action'), '| ok=%s' % r.get('ok'),
          '| %s' % (r.get('reason') or ''))
    if r.get('action') == 'PLANO_CLICAR':
        print('  clicaria (frame) em rect=%s [DRY-RUN — nada enviado]' % (r['target_rect_frame'],))
    if r.get('action') == 'PLANO_BUSCAR':
        print("  clicaria 'Pesquisar' em %s, digitaria %r [DRY-RUN — nada enviado]"
              % (r['pesquisar_pt'], r['target']))
    return 0 if r.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
