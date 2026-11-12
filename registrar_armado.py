"""Registrador ARMADO — inscreve no torneio do lobby PPPoker, com TRAVAS (Fase 3B+).

Espelha o `operar_mesa`: o fluxo de decisão (`registration_flow`) é LÓGICA PURA e
NUNCA clica (invariante `execution_allowed=False`); o clique mora AQUI, no
orquestrador, atrás do MESMO gate (`BotControl` RUNNING via hotkey) e do mesmo
`CursorController` (trajetória min-jerk + revalidação NA CHEGADA + verificação de
efeito). Cada etapa do registro é um clique revalidado:

    1) clica no CARTÃO do alvo  -> verifica que a tela de detalhes abriu
    2) clica em "Registrar"     -> verifica "Registro concluído" / botão "Entrar"

Travas:
- DEFAULT = DRY-RUN: percorre política + fluxo até AGUARDANDO CONFIRMAÇÃO e PARA
  (não clica). Com `--arm` usa o cursor REAL, mas só clica com o BotControl em
  RUNNING. Começa PAUSADO: Ctrl+Alt+R arma, Ctrl+Alt+P pausa (você assume),
  Ctrl+Alt+D desabilita.
- UM alvo, UMA tentativa por rodada. Autorização explícita por torneio+custo
  (`--target` + `--authorized-cost`); não se transfere para outro evento/custo.
- Política de banca/orçamento/teto (SessionConfig) barra antes de qualquer clique.
- A lista do lobby é DINÂMICA: o validator relê o lobby na chegada; se o cartão
  moveu/sumiu, o CursorController CANCELA (não clica no cartão errado).
- Reconciliação no ledger: reserva -> CONFIRMED só com evidência observável.

Uso:
  # dry-run (seguro): decide e para, sem clicar
  python registrar_armado.py --hwnd 0x1800CC --currency FICHA \
      --max-entry 100 --budget 500 --bankroll 2000 \
      --target "MINI FREEZE" --authorized-cost 10

  # armado (ainda precisa Ctrl+Alt+R para clicar)
  python registrar_armado.py --hwnd 0x1800CC --currency FICHA \
      --max-entry 100 --budget 500 --bankroll 2000 \
      --target "MINI FREEZE" --authorized-cost 10 --arm
"""
import argparse
import sys
import time

import cv2
import numpy as np

from bot_control import BotControl, HotkeyListener
from cursor_controller import CursorController, Intent, make_intervention_check
from cursor_input_win import WindowsCursorInput
from lobby_runner import details_from_card, read_lobby
from registration_flow import RegistrationRound
from registration_ledger import RegistrationLedger
from screen_coords import frame_to_screen, rect_frame_to_screen
from session_config import SessionConfig
from table_discovery.pppoker import discover_pppoker
from table_reading.ocr_runtime import image_to_string
from table_reading.pipeline import configure_ocr
from window_capture_engine import WindowCaptureEngine


# --------------------------------------------------------------------------- #
# Geometria da janela (lógica) — fresca a cada uso (continuidade entre etapas). #
# --------------------------------------------------------------------------- #
def _discover_rect(hwnd, *, tries=4, delay=0.15):
    """Geometria lógica ATUAL da janela (None se sumiu). Retry curto: a janela
    some do discover por instantes durante transições de tela (modal de detalhes),
    então tentamos algumas vezes antes de desistir."""
    for i in range(max(1, tries)):
        ws = [w for w in discover_pppoker().get('windows', []) if w['hwnd'] == hwnd]
        if ws:
            return (ws[0]['x'], ws[0]['y'], ws[0]['w'], ws[0]['h'])
        if i < tries - 1:
            time.sleep(delay)
    return None


def _ocr_line(gray):
    return ' '.join(image_to_string(gray, config='--psm 7').split())


# --------------------------------------------------------------------------- #
# Detectores (validados ao vivo): cartão do alvo e botão verde "Registrar".     #
# --------------------------------------------------------------------------- #
def find_card_frame_point(frame, target_name):
    """(fx, fy) no FRAME físico do corpo do cartão `target_name`, ou None.

    Âncora no badge de buy-in (grade_reader via read_lobby) e aponta um pouco à
    direita do badge (sobre o nome/infos) — o clique abre o torneio.
    """
    out = read_lobby(frame)
    if not out.get('ok'):
        return None
    bx, by = out['box'][0], out['box'][1]
    tgt = (target_name or '').strip().upper()
    for c in out['cards']:
        if (c.get('name') or '').strip().upper() == tgt:
            gx, gy, gw, gh = c['badge']
            return (bx + gx + gw + int(0.6 * gw), by + gy + gh // 2)
    return None


def find_register_button_frame_rect(frame):
    """(x, y, w, h) no FRAME físico do botão verde cujo texto é 'Registrar', ou
    None. Máscara de verde (G dominante) + forma larga na metade inferior + OCR."""
    fh, fw = frame.shape[:2]
    b = frame[:, :, 0].astype(int)
    g = frame[:, :, 1].astype(int)
    r = frame[:, :, 2].astype(int)
    green = ((g > 110) & (g > r + 30) & (g > b + 10) & (r < 150)).astype(np.uint8) * 255
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(green, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w > 0.05 * fw and h > 0.015 * fh and w > 3 * h and y > 0.5 * fh:
            txt = _ocr_line(cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY))
            if 'egistr' in txt.lower():           # "Registrar" (tolerante a OCR)
                if best is None or area > best[4]:
                    best = (int(x), int(y), int(w), int(h), int(area))
    return best[:4] if best else None


def detail_screen_signal(frame):
    """Lê sinais da tela de detalhes do torneio. Retorna dict com:
    `detail_open` (título 'Informações do jogo' OU botão Registrar presente),
    `registrar` (botão 'Registrar' presente), `entrar` (botão 'Entrar' presente),
    `concluido` ('Registro concluído' no topo)."""
    fh, fw = frame.shape[:2]
    # topo central: título e a linha "Registro concluído/encerra"
    top = frame[int(0.03 * fh):int(0.17 * fh), int(0.0 * fw):int(0.5 * fw)]
    top_txt = _ocr_line(cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)).lower()
    reg_rect = find_register_button_frame_rect(frame)
    # botão "Entrar" é verde também; reusa a varredura, mas conferindo o texto
    entrar = _green_button_text_present(frame, 'entrar')
    return dict(
        detail_open=('informa' in top_txt) or (reg_rect is not None) or entrar,
        registrar=reg_rect is not None,
        entrar=entrar,
        concluido=('conclu' in top_txt),
        top_txt=top_txt)


def _green_button_text_present(frame, needle):
    fh, fw = frame.shape[:2]
    b = frame[:, :, 0].astype(int)
    g = frame[:, :, 1].astype(int)
    r = frame[:, :, 2].astype(int)
    green = ((g > 110) & (g > r + 30) & (g > b + 10) & (r < 150)).astype(np.uint8) * 255
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(green, 8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w > 0.05 * fw and h > 0.015 * fh and w > 3 * h and y > 0.5 * fh:
            txt = _ocr_line(cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY))
            if needle in txt.lower():
                return True
    return False


# --------------------------------------------------------------------------- #
# Clique revalidado via CursorController (mesmo motor do operar_mesa).          #
# --------------------------------------------------------------------------- #
def _click_step(engine, hwnd, *, locate_frame_rect, source_key, adapter, control,
                verifier, label, deadline_s=6.0):
    """Executa UM clique gated+revalidado. `locate_frame_rect(frame)->rect|None`
    localiza o alvo no frame físico FRESCO; o validator remapeia para a tela
    lógica a cada chamada (inicial + chegada), então um alvo que moveu CANCELA.
    Retorna o dict do CursorController ({state, reasons, ...})."""
    def validator(intent, now):
        wr = _discover_rect(hwnd)
        if wr is None:
            return dict(ok=False, reasons=['WINDOW_GONE'])
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, reasons=['NO_FRAME'])
        fh, fw = frame.shape[:2]
        rect = locate_frame_rect(frame)
        if rect is None:
            return dict(ok=False, reasons=['TARGET_NOT_FOUND'])
        screen_rect = rect_frame_to_screen(rect, window_rect=wr, frame_size=(fw, fh))
        return dict(ok=True, target_rect=screen_rect, identity=source_key)

    intent = Intent(id='reg-%s-%s' % (label, int(time.time() * 1000)),
                    action='CLICK', source_key=source_key,
                    target_rect=(0, 0, 1, 1),         # placeholder; validator preenche
                    deadline=time.monotonic() + deadline_s,
                    expected=dict(step=label))
    ctrl = CursorController(input_adapter=adapter, validator=validator,
                            verifier=verifier, bot_control=control,
                            cancel_check=make_intervention_check(adapter),
                            arrival_tol=12.0)
    return ctrl.execute(intent)


def _target_rect_from_point(point, pad=28):
    """Transforma um ponto (fx,fy) num retângulo pequeno centrado (o clique mira o
    centro). `pad` é meia-aresta em px físicos do frame."""
    fx, fy = point
    return (fx - pad, fy - pad, 2 * pad, 2 * pad)


# --------------------------------------------------------------------------- #
# Orquestração                                                                  #
# --------------------------------------------------------------------------- #
def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--hwnd', type=lambda s: int(s, 0), required=True,
                   help='HWND da janela PPPoker (lobby na aba do torneio)')
    p.add_argument('--club', default='Karekas')
    p.add_argument('--currency', required=True, help='Moeda explícita (nunca inventada)')
    p.add_argument('--max-entry', type=float, required=True, help='Teto por inscrição')
    p.add_argument('--budget', type=float, required=True, help='Orçamento da sessão')
    p.add_argument('--bankroll', type=float, required=True, help='Banca em buy-ins')
    p.add_argument('--max-simultaneous', type=int, default=4)
    p.add_argument('--target', required=True, help='Nome do torneio autorizado')
    p.add_argument('--authorized-cost', type=float, required=True,
                   help='Custo da oferta autorizada p/ o alvo (§5)')
    p.add_argument('--frames', type=int, default=5, help='Frames p/ ler o lobby')
    p.add_argument('--db', default=':memory:', help='SQLite do ledger (persiste)')
    p.add_argument('--arm', action='store_true', help='Usa o cursor REAL (ainda gated)')
    p.add_argument('--no-hotkeys', action='store_true')
    args = p.parse_args(argv)

    configure_ocr()
    engine = WindowCaptureEngine()
    wr = _discover_rect(args.hwnd)
    if wr is None:
        print('Janela %#x não encontrada.' % args.hwnd); return 1

    # --- leitura do lobby (merge de N frames) -------------------------------
    from lobby_runner import read_lobby_multi
    lob = read_lobby_multi(lambda: engine.capture_frame(hwnd=args.hwnd)[0],
                           frames=args.frames)
    if not lob.get('ok'):
        print('Sem lobby:', lob.get('reason')); return 1
    card = next((c for c in lob['cards']
                 if (c.get('name') or '').strip().upper() == args.target.strip().upper()), None)
    if card is None:
        print('Alvo %r não encontrado. Lidos: %s'
              % (args.target, [c['name'] for c in lob['cards']])); return 1

    config = SessionConfig(
        enabled=True, clubs_authorized=(args.club,),
        allowed_modalities=('freezeout', 'mko', 'pko'), currency=args.currency,
        max_entry_buyin=args.max_entry, daily_budget=args.budget,
        bankroll_bi=args.bankroll, max_simultaneous=args.max_simultaneous)
    ledger = RegistrationLedger(args.db)

    control = BotControl()
    listener = None
    if not args.no_hotkeys:
        listener = HotkeyListener(control)
        listener.start()
    # O gate do FLUXO (reserve/authorize) exige RUNNING. Em dry-run liberamos o
    # fluxo (só lógica, não clica); o clique real continua barrado por --arm.
    if not args.arm:
        control.resume()                 # PAUSED->RUNNING (fluxo lógico só)

    mode = 'real_supervised' if args.arm else 'observation'
    rnd = RegistrationRound(
        round_id='armado-1', operator='eduardo', target_name=args.target,
        authorized_cost=args.authorized_cost, currency=args.currency, config=config,
        ledger=ledger, mode=mode, bot_control=control)

    details = details_from_card(card, club=args.club, currency=args.currency)

    print('=' * 70)
    print('REGISTRAR ARMADO | modo=%s | %s' % (
        'ARMADO (cursor REAL)' if args.arm else 'DRY-RUN (sem clique)',
        'começa PAUSADO: Ctrl+Alt+R arma' if (args.arm and not args.no_hotkeys)
        else ('sem hotkeys' if args.no_hotkeys else 'fluxo lógico liberado')))
    print('Alvo: %r | custo autorizado: %s %s' % (args.target, args.authorized_cost, args.currency))
    print('=' * 70)

    # --- fluxo supervisionado: observe -> details -> reserve ----------------
    for step, res in [('observe', rnd.observe(card, club=args.club)),
                      ('check_details', rnd.check_details(details))]:
        print('[%s] -> %s %s' % (step, res['flow_state'], res.get('reasons') or ''))
        if rnd.flow_state == 'BLOCKED':
            print('BLOQUEADO. Nada reservado.'); ledger.close(); return 1

    # reserve exige RUNNING; no armado isso significa Ctrl+Alt+R ANTES de reservar.
    if args.arm and not control.execution_allowed():
        print('\n>>> ARME para prosseguir: aperte Ctrl+Alt+R (ou Ctrl+Alt+D p/ sair).')
        while not control.execution_allowed():
            if control.state == 'DISABLED':
                print('Desabilitado. Saindo.'); ledger.close()
                if listener: listener.stop()
                return 0
            time.sleep(0.1)

    res = rnd.reserve()
    print('[reserve] -> %s %s' % (res['flow_state'], res.get('reasons') or ''))
    if rnd.flow_state == 'BLOCKED':
        print('BLOQUEADO na reserva.'); ledger.close()
        if listener: listener.stop()
        return 1

    s = rnd.summary()
    print('\n--- RESUMO (AGUARDANDO CONFIRMAÇÃO) ---')
    print('  Torneio ......: %s / %s' % (s['tournament'], s['club']))
    print('  Custo ........: %s %s' % (s['total_cost'], s['currency']))
    print('  Orç. após ....: %s' % s['budget_remaining_after_reserve'])

    # autorização explícita por torneio+custo (confirm=True vem do operador que
    # passou --target/--authorized-cost E armou). Em observação, para sem enviar.
    ares = rnd.authorize(confirm=True)
    print('[authorize] -> %s %s' % (rnd.flow_state, ares.get('note') or ''))

    if not args.arm:
        print('\n>>> DRY-RUN: decisão pronta e autorizada; o clique NÃO é enviado.')
        print('    Para inscrever de verdade: rode de novo com --arm e aperte Ctrl+Alt+R.')
        ledger.close()
        if listener: listener.stop()
        return 0

    # ----------------------------------------------------------------------- #
    # ARMADO: executa os cliques gated+revalidados.                            #
    # ----------------------------------------------------------------------- #
    adapter = WindowsCursorInput()

    # Passo 1: clicar no cartão -> verifica que a tela de detalhes abriu.
    def card_locator(frame):
        pt = find_card_frame_point(frame, args.target)
        return _target_rect_from_point(pt) if pt else None

    def verify_detail(_intent, _now):
        frame, _ = engine.capture_frame(hwnd=args.hwnd)
        if frame is None:
            return dict(confirmed=False)
        sig = detail_screen_signal(frame)
        return dict(confirmed=bool(sig['detail_open']), signal=sig)

    print('\n[passo 1/2] clicando no CARTÃO do alvo...')
    r1 = _click_step(engine, args.hwnd, locate_frame_rect=card_locator,
                     source_key='card:%s' % args.target.upper(), adapter=adapter,
                     control=control, verifier=verify_detail, label='card')
    print('   -> %s %s' % (r1['state'], r1.get('reasons') or ''))
    if r1['state'] not in ('DONE', 'UNKNOWN_RESULT'):
        print('   cartão não abriu detalhes (cancelado). Nada enviado ao Registrar.')
        ledger.close()
        if listener: listener.stop()
        return 1
    time.sleep(0.8)   # deixa a tela de detalhes assentar

    # Passo 2: clicar em "Registrar" -> verifica "Registro concluído"/"Entrar".
    def verify_registered(_intent, _now):
        frame, _ = engine.capture_frame(hwnd=args.hwnd)
        if frame is None:
            return dict(confirmed=False)
        sig = detail_screen_signal(frame)
        ok = bool(sig['concluido'] or sig['entrar'])
        return dict(confirmed=ok, signal=sig)

    print('[passo 2/2] clicando em "Registrar"...')
    r2 = _click_step(engine, args.hwnd,
                     locate_frame_rect=find_register_button_frame_rect,
                     source_key='btn:registrar', adapter=adapter, control=control,
                     verifier=verify_registered, label='registrar')
    print('   -> %s %s' % (r2['state'], r2.get('reasons') or ''))

    # ---- conciliação -------------------------------------------------------
    frame, _ = engine.capture_frame(hwnd=args.hwnd)
    sig = detail_screen_signal(frame) if frame is not None else {}
    registered = bool(sig.get('concluido') or sig.get('entrar'))
    rnd.record_user_action()      # "ação" = nosso clique gated (CONFIRMATION_SENT)
    receipt = dict(identity=rnd.identity, cost=args.authorized_cost,
                   currency=args.currency, confirmed=registered,
                   evidence_ref='ocr:%s' % ('concluido' if sig.get('concluido')
                                            else 'entrar' if sig.get('entrar') else 'none'))
    rrec = rnd.reconcile(receipt)
    print('\n[reconcile] -> %s %s' % (rnd.flow_state, rrec.get('note') or rrec.get('reasons') or ''))
    if registered:
        print('\n*** INSCRITO: "Registro concluído" / botão "Entrar" detectado. ***')
    else:
        print('\n*** RESULTADO DESCONHECIDO: não confirmei a inscrição na tela. '
              'Reserva mantida; confira no cliente. ***')
    ledger.close()
    if listener:
        listener.stop()
    return 0 if registered else 2


if __name__ == '__main__':
    sys.exit(main())
