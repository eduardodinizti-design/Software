"""Operar a mesa (passo 3) — lê, decide e CLICA Fold/Call/Check, com travas.

DEFAULT = DRY-RUN (não envia clique; só mostra a intenção). Com `--arm` usa o
cursor REAL, mas só clica com o BotControl em RUNNING. Começa PAUSADO: aperte
Ctrl+Alt+R para ARMAR, Ctrl+Alt+P para pausar (você assume), Ctrl+Alt+D desabilita.
Só Fold/Call/Check (clique único); Raise/Bet/all-in ficam de fora (sizing depois).
Uma ação por mão. Revalida na chegada e verifica o efeito.

Uso:
  python operar_mesa.py --hwnd 0x...              # dry-run (seguro)
  python operar_mesa.py --hwnd 0x... --arm        # arma (ainda precisa Ctrl+Alt+R)
"""
import argparse
import sys
import time

import cv2

from table_reading.pipeline import configure_ocr
from table_reading.automatic_table_crops import detect_table_crops
from table_reading.action_buttons import read_action_buttons
from table_reading.hand_tracking import read_hand_id
from table_reading.community_cards import read_board
from table_advisor import advise_table
from preflop_advisor import PreflopAdvisor
from preflop_context import PreflopAggressorTracker
from reader_cache import ReaderCache
from action_executor import ActionExecutor
from action_coordinator import DryRunInput, map_advice_to_action, decision_identity
from position_stabilizer import PositionStabilizer
from screen_coords import rect_frame_to_screen
from raise_panel import target_multiplier, map_multiplier_to_preset, read_raise_panel
from raise_sequencer import RaiseSequencer
from cursor_input_win import WindowsCursorInput
from bot_control import BotControl, HotkeyListener, DISABLED, PAUSED, RUNNING
from window_capture_engine import WindowCaptureEngine
from table_discovery.pppoker import discover_pppoker
from status_overlay import StatusOverlay
from grade_reader import find_buyin_badges
from table_reading.tournament_end import detect_tournament_end
from tournament_metrics import record_tournament_end
from latency_metrics import LatencyMetrics
from shadow_mode import ShadowMonitor
from operator_robustness import BoundedKeySet, CaptureWatch, raise_outcome, reconcile_targets
from anticipation import AnticipationStore, available_actions, TurnEpochTracker
from hero_card_memory import HeroCardMemory

DEFAULT_RANGES = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEFAULT_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _discover_rect(hwnd):
    """Geometria lógica ATUAL da janela (None se sumiu) — p/ continuidade entre etapas."""
    ws = [w for w in discover_pppoker().get('windows', []) if w['hwnd'] == hwnd]
    return (ws[0]['x'], ws[0]['y'], ws[0]['w'], ws[0]['h']) if ws else None


def _table_key(x, y):
    """Chave estável de mesa pela origem do crop (robusta a jitter de poucos px).
    NÃO é índice do recorte (que pode reordenar)."""
    return '%dx%d' % (x // 100, y // 100)


def _close_tournament_table(frame, crop_box, te, hwnd, adapter, engine, armed):
    """ROTINA ao cair do torneio: fecha a mesa clicando 'Sair'. Move+clica (o 1º
    clique só FOCA a janela; por isso move_to antes). Confirma relendo a MESMA
    região do crop. Em dry-run não clica (só mira). Devolve True se o fechamento
    foi confirmado (a tela de fim sumiu)."""
    box = te.get('sair_box')
    if not box:
        return False
    x, y, cbw, cbh = crop_box
    fh, fw = frame.shape[:2]
    bx, by, bw, bh = x + box[0], y + box[1], box[2], box[3]
    rect = rect_frame_to_screen((bx, by, bw, bh), window_rect=_discover_rect(hwnd),
                                frame_size=(fw, fh))
    if rect is None:
        return False
    cx, cy = int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2)
    if not armed:
        return False                                   # dry-run: só detecta/registra
    try:
        adapter.move_to(cx, cy)
        time.sleep(0.15)
        adapter.click_once(cx, cy)
        time.sleep(0.9)
    except Exception as exc:                           # noqa: BLE001
        print('   (falha ao clicar Sair: %s)' % str(exc)[:80], flush=True)
        return False
    f2, _ = engine.capture_frame(hwnd=hwnd)
    if f2 is None:
        return True
    return detect_tournament_end(f2[y:y + cbh, x:x + cbw]).get('status') != 'TOURNAMENT_END'


_RANKS = '23456789TJQKA'


def _board_sig(board):
    """Assinatura barata da RUA/board p/ a impressão digital da antecipação. Uma
    decisão pré-flop (preparada sem board) NÃO pode ser reusada depois do flop:
    mesma mão/época mas rua nova muda esta assinatura -> invalida o payload. Usa
    rua + nº de cartas do board (robusto a leitura parcial)."""
    board = board or {}
    return (board.get('street'), len(board.get('cards') or []))


def _is_premium(cards):
    """Mão PREMIUM pré-flop (NUNCA foldar no fallback): par TT+ ou AK/AQ. Foldar um
    monstro (KK/AA) por falta de nó é o pior erro possível — este guarda evita isso."""
    if not cards or len(cards) != 2:
        return False
    try:
        a, b = (_RANKS.index(cards[0][0]), _RANKS.index(cards[1][0]))
    except (ValueError, IndexError):
        return False
    hi, lo = max(a, b), min(a, b)
    if a == b and a >= _RANKS.index('T'):          # par TT, JJ, QQ, KK, AA
        return True
    if hi == _RANKS.index('A') and lo >= _RANKS.index('Q'):   # AK, AQ
        return True
    return False


def _first_button_row(frame, max_tables):
    """(crop_origin, buttons_result) do 1º crop que é vez do hero, ou (None,None)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    for prop in detect_table_crops(rgb, max_tables=max_tables):
        x, y, bw, bh = map(int, prop.box)
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
            return (x, y), br
    return None, None


def _find_table_by_key(frame, max_tables, want_key):
    """Acha o crop cuja chave bate com `want_key` (a MESMA mesa), ou None. Não usa
    a 1ª linha de botões qualquer — não valida uma mesa com os botões de outra."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    for prop in detect_table_crops(rgb, max_tables=max_tables):
        x, y, bw, bh = map(int, prop.box)
        if _table_key(x, y) == want_key:
            return (x, y, bw, bh)
    return None


def make_validator(engine, hwnd, max_tables):
    """Revalidação ligada à INTENÇÃO: mesma janela (geometria FRESCA), MESMA mesa
    (por chave), vez do hero, o botão da ação e o VALOR esperado. Devolve
    `target_rect` (coord de tela com a geometria atual) e `identity` (assinatura da
    decisão) — o CursorController cancela em TARGET_MOVED/IDENTITY_CHANGED, inclusive
    quando o valor do Call muda com o botão na mesma coordenada."""
    def validator(intent, now):
        exp = intent.expected or {}
        want_key = exp.get('table_key')
        wins = [w for w in discover_pppoker().get('windows', []) if w['hwnd'] == hwnd]
        if not wins:
            return dict(ok=False, reasons=['JANELA_SUMIU'])         # geometria velha não vale
        w = wins[0]
        win_rect = (w['x'], w['y'], w['w'], w['h'])
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(ok=False, reasons=['RECAPTURE_FAILED'])
        fh, fw = frame.shape[:2]
        box = _find_table_by_key(frame, max_tables, want_key)
        if box is None:
            return dict(ok=False, reasons=['MESA_ALVO_NAO_ENCONTRADA'])
        x, y, bw, bh = box
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        if br['status'] != 'EXPERIMENTAL_BUTTON_ROW':
            return dict(ok=False, reasons=['NAO_E_VEZ_DO_HERO'])
        btn = next((b for b in br['buttons'] if b.get('action') == intent.action), None)
        if btn is None:
            return dict(ok=False, reasons=['BOTAO_SUMIU'])
        tx, ty, tw, th = btn['box']
        rect = rect_frame_to_screen((x + tx, y + ty, tw, th), window_rect=win_rect,
                                    frame_size=(fw, fh))
        # RELÊ a mão na chegada (não ecoa a esperada): se a mão mudou, a identidade
        # diverge do source_key e o controlador cancela (IDENTITY_CHANGED) — não clica
        # numa mão nova. Mão ilegível vira identidade != esperada -> também cancela.
        cur = read_hand_id(frame[y:y + bh, x:x + bw])
        cur_hand = cur.get('hand_id') or cur.get('hand_number')
        identity = decision_identity(want_key, cur_hand, intent.action,
                                     btn.get('amount'), btn.get('unit'))
        return dict(ok=True, target_rect=rect, identity=identity)
    return validator


# Leituras que PROVAM positivamente que a linha de ação sumiu numa mesa legível
# (não é a vez do hero). Erros de leitura (INVALID_CROP/CROP_TOO_SMALL) e a linha
# ainda presente NÃO contam — ausência por OCR/cobertura != ação executada.
_ROW_GONE_STATUSES = ('NO_BUTTON_ROW', 'PRESELECTION_ROW')


def make_verifier(engine, hwnd, max_tables):
    """Efeito na MESMA mesa: a linha de ação sumiu, com evidência POSITIVA. Ausência
    de botões por OCR/cobertura/troca de tela NÃO confirma (confirmed=False) — só um
    read limpo sem linha de ação (NO_BUTTON_ROW/PRESELECTION_ROW) confirma. O
    controlador trata não-confirmado como UNKNOWN_RESULT e não repete."""
    def verifier(intent, now):
        time.sleep(0.3)
        exp = intent.expected or {}
        frame, _ = engine.capture_frame(hwnd=hwnd)
        if frame is None:
            return dict(confirmed=False)
        box = _find_table_by_key(frame, max_tables, exp.get('table_key'))
        if box is None:
            return dict(confirmed=False)                 # não achei a mesa -> não confirmo
        x, y, bw, bh = box
        br = read_action_buttons(frame[y:y + bh, x:x + bw])
        return dict(confirmed=br.get('status') in _ROW_GONE_STATUSES)
    return verifier


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--hwnd', type=lambda s: int(s, 0), nargs='+', required=True,
                   help='Um ou mais HWND de janelas de mesa (2 mesas = 2 HWND).')
    p.add_argument('--ranges', default=DEFAULT_RANGES)
    p.add_argument('--deep', default=None)
    p.add_argument('--frames', type=int, default=0, help='0 = até Ctrl+C/Disable')
    p.add_argument('--intervalo', type=float, default=1.0)
    p.add_argument('--max-tables', type=int, default=6)
    p.add_argument('--rediscover', action='store_true',
                   help='D1: re-descobre janelas periodicamente (pega mesas novas de '
                        'balanceamento MTT e dropa as fechadas). Off por padrao.')
    p.add_argument('--rediscover-every', type=int, default=200,
                   help='ciclos entre re-descobertas (com --rediscover)')
    p.add_argument('--bounty-bb', type=float, default=None,
                   help='PKO: valor do bounty em BB p/ o overlay de call-off (so engata em torneio PKO e cobrindo o shove)')
    p.add_argument('--mode', choices=('chip_ev', 'icm', 'pko', 'pko_icm'), default=None,
                   help='Forca o modo do torneio (sobrepoe a deteccao por nome; ex. PKO quando o skin nao mostra no nome)')
    p.add_argument('--stage', choices=('pre_itm', 'bubble', 'ft', 'mid'), default=None,
                   help='Forca a fase do torneio (sobrepoe a deteccao)')
    p.add_argument('--hud', action='store_true',
                   help='Le o HUD VIP (8 stats por vilao) p/ exploit no pos-flop')
    p.add_argument('--arm', action='store_true', help='Usa o cursor REAL (ainda gated)')
    p.add_argument('--overlay', action='store_true',
                   help='Faixa de status SEMPRE-NO-TOPO (feedback visível: ARMADO/PAUSADO + ações)')
    p.add_argument('--auto-arm', action='store_true',
                   help='Comeca JA ARMADO (RUNNING), sem precisar do Ctrl+Alt+R. '
                        'Ctrl+Alt+P ainda pausa e Ctrl+Alt+D desabilita a qualquer momento.')
    p.add_argument('--no-hotkeys', dest='hotkeys', action='store_false')
    p.add_argument('--antecipar', action='store_true',
                   help='A1: reaproveita a decisao SEGURA (fold/check) ja computada entre '
                        'frames da MESMA vez do hero, pulando o cerebro (~330ms) em revisitas. '
                        'Nunca antecipa call/raise. Default off.')
    args = p.parse_args(argv)

    import os
    configure_ocr()
    deep = args.deep or (DEFAULT_DEEP if os.path.exists(DEFAULT_DEEP) else None)
    advisor = (PreflopAdvisor.from_files(args.ranges, deep) if deep
               else PreflopAdvisor.from_file(args.ranges))
    # B01/B02: proveniência auditável no startup — quais pack(s) por sha256 alimentam
    # o cérebro, cobertura de nós e colisões de chave resolvidas SEM sombra silenciosa.
    _mani = advisor.manifest()
    print('[CEREBRO] fontes: ' + ', '.join(
        '%s(%s.. %dn/%dval)' % (os.path.basename(s['path']), s['sha256'][:8], s['nodes'], s['validated'])
        for s in _mani['sources']) +
        ' | chaves=%d nos=%d colisoes=%d (0 sombra silenciosa)' % (
            _mani['index_keys'], _mani['total_nodes'], len(_mani['collisions'])), flush=True)
    engine = WindowCaptureEngine()
    overlay = StatusOverlay().start() if args.overlay else None

    def _on_change(s):
        print('\n>>> BOT %s <<<\n' % s, flush=True)
        if overlay:
            overlay.set_state(s)
    control = BotControl(on_change=_on_change)
    if overlay:
        overlay.set_state(control.state)
        overlay.note('DRY-RUN (sem clique)' if not args.arm else 'ARMADO: Ctrl+Alt+R para liberar o clique')
    listener = HotkeyListener(control) if args.hotkeys else None
    if listener:
        listener.start()
    if args.auto_arm and args.arm:
        control.resume()   # PAUSED -> RUNNING: comeca ARMADO (sem depender do Ctrl+Alt+R)
        print('>>> AUTO-ARM: iniciando ARMADO (RUNNING). Ctrl+Alt+P pausa; Ctrl+Alt+D desabilita.', flush=True)
    adapter = WindowsCursorInput() if args.arm else DryRunInput()
    # Uma entrada por janela (HWND): geometria + executor + validator/verifier próprios.
    per = {}

    def _build_entry(hwnd, w):
        wr = (w['x'], w['y'], w['w'], w['h'])
        return dict(executor=ActionExecutor(window_rect=wr, bot_control=control, armed=args.arm),
                    validator=make_validator(engine, hwnd, args.max_tables),
                    verifier=make_verifier(engine, hwnd, args.max_tables))

    wins_all = discover_pppoker().get('windows', [])
    for hwnd in args.hwnd:
        w = next((x for x in wins_all if x['hwnd'] == hwnd), None)
        if w is None:
            print('Janela %#x nao encontrada; ignorada.' % hwnd, flush=True)
            continue
        per[hwnd] = _build_entry(hwnd, w)
    if not per:
        print('Nenhuma janela valida.'); return 1
    targets = list(per)
    raise_done = BoundedKeySet(2048)   # (mesa_global, mao): LRU p/ não vazar em horas (D3)
    raise_attempts = {}                # D4: tentativas de raise por (mesa,mao) p/ cap de re-try
    hero_mem = HeroCardMemory()   # memória temporal por-slot das cartas do hero (anti HERO_CARDS_UNKNOWN)
    stabilizer = PositionStabilizer()   # suaviza posições (anti-flicker HJ<->UTG+2)
    aggr_tracker = PreflopAggressorTracker()   # agressor pré-flop por mesa (p/ equity pós-flop)
    read_cache = ReaderCache()                 # cache de HUD/bounty (latência: relê a cada N frames)

    print('OPERAR MESA | modo=%s | %s' % (
        'ARMADO (cursor REAL)' if args.arm else 'DRY-RUN (sem clique)',
        'comeca PAUSADO: Ctrl+Alt+R arma, P pausa, D desabilita' if args.hotkeys
        else 'sem hotkeys'), flush=True)
    print('Travas: so Fold/Call/Check; 1 acao por mao; revalida na chegada; verifica efeito.',
          flush=True)
    print('Janelas monitoradas: %d (round-robin, 1 por ciclo). Com 2 mesas use --intervalo menor.'
          % len(per), flush=True)

    n = 0
    tourneys_closed = BoundedKeySet(512)   # (hwnd, table_key): LRU p/ não vazar em horas (D3)
    capture_watch = CaptureWatch()  # D2: vigia janela morta (captura None consecutiva) sem silêncio
    advise_watch = CaptureWatch(alert_after=3, repeat=20)  # D7: circuit-breaker de exceção do advise_table
    latency = LatencyMetrics()      # A0: instrumentação de latência real (p50/p95/p99)
    # A1 (antecipação, só com --antecipar): reaproveita a decisão SEGURA entre frames
    # da MESMA vez do hero. Época = cada vez que a ação (re)chega à mesa; dentro de uma
    # época o adversário NÃO pode agir (é a vez do hero), então a decisão fica congelada
    # e reusá-la é seguro. O store trava fold/check; call/raise sempre recomputam.
    anticip = AnticipationStore()
    anticip_turns = TurnEpochTracker()   # A2: debounce da vez (pisca da linha de botões)
    anticip_payload = {}            # (tkey, hkey, época) -> (result, adv) p/ pular advise_table
    # Shadow Mode / Monitoring: compara bot x GTO em tempo real e avisa quando o
    # cérebro sai dos trilhos na sessão (grava logs/shadow/decisoes.jsonl).
    def _shadow_sink(rec):
        if rec['verdict'] == 'fora_dos_trilhos':
            print('[SHADOW] FORA DOS TRILHOS: %s %s %s | GTO=%s acao=%s autoridade=%s'
                  % (rec.get('hero_cards'), rec.get('position'), rec.get('spot'),
                     rec.get('gto_recommended'), rec.get('bot_action'), rec.get('authority')),
                  flush=True)
    shadow = ShadowMonitor(sink=_shadow_sink)

    def _emit_shadow(result, adv, action, out=None):
        ts = result.get('table_state') or {}
        _, health = shadow.observe(
            frame=n, table=tkey_local, hero_cards=result.get('hero_cards'),
            position=(ts.get('positions') or {}).get('hero'),
            stack_bb=adv.get('stack_bb'), to_call_bb=ts.get('to_call_bb'),
            spot=adv.get('spot'), node_id=adv.get('node_id'), validated=adv.get('validated'),
            gto_status=adv.get('status'), gto_recommended=adv.get('recommended'),
            bot_action=action, authority=(out or {}).get('authority'),
            result_state=(out or {}).get('state'))
        if health['status'] == 'off_rails':
            print('[SHADOW] *** CEREBRO FORA DOS TRILHOS *** %d/%d das ultimas decisoes comprometeram ficha contra o GTO'
                  % (health['off_rails'], health['window']), flush=True)
    try:
        while args.frames == 0 or n < args.frames:
            n += 1
            t0 = time.monotonic()
            if control.state == DISABLED:
                print('Desabilitado. Encerrando. Nenhum clique a mais.', flush=True)
                break
            # D1: re-descoberta periódica (opt-in). Pega mesas NOVAS (balanceamento MTT
            # abre HWND novo) e dropa as fechadas, sem o humano re-alimentar a lista.
            if (args.rediscover and args.rediscover_every > 0
                    and n > 1 and n % args.rediscover_every == 1):
                try:
                    _disc = discover_pppoker().get('windows', [])
                except Exception as _e:               # noqa: BLE001
                    _disc = None
                    print('[%03d] [AVISO] re-descoberta falhou: %s' % (n, str(_e)[:80]), flush=True)
                if _disc is not None:
                    _add, _drop, _by = reconcile_targets(targets, _disc, max_targets=max(4, args.max_tables * 2))
                    for _h in _add:
                        per[_h] = _build_entry(_h, _by[_h])
                        targets.append(_h)
                        print('[%03d] mesa NOVA 0x%x -> entra no round-robin (balanceamento?)' % (n, _h), flush=True)
                    for _h in _drop:
                        per.pop(_h, None)
                        if _h in targets:
                            targets.remove(_h)
                        capture_watch.ok(_h)
                        print('[%03d] mesa 0x%x sumiu -> removida do round-robin' % (n, _h), flush=True)
                    if not targets:
                        print('[%03d] Nenhuma mesa restante apos re-descoberta. Encerrando.' % n, flush=True)
                        break
            hwnd = targets[(n - 1) % len(targets)]     # round-robin: 1 janela por ciclo
            ph = per[hwnd]
            executor, validator, verifier = ph['executor'], ph['validator'], ph['verifier']
            _tcap = time.monotonic()
            frame, meta = engine.capture_frame(hwnd=hwnd)
            latency.record('captura', (time.monotonic() - _tcap) * 1000)
            cap_ts = time.monotonic()            # A0: referência p/ idade do snapshot
            if frame is None:
                # D2: não fica em silêncio indefinido — conta falhas consecutivas por
                # janela e avisa quando parece MORTA (minimizada/fechada/coberta/GDI).
                fails, alert = capture_watch.fail(hwnd)
                if alert:
                    print('[%03d] [AVISO] janela 0x%x sem captura ha %d ciclos (morta/'
                          'minimizada/coberta?) meta=%s' % (n, hwnd, fails, (meta or {}).get('status')),
                          flush=True)
                time.sleep(max(0.1, args.intervalo - (time.monotonic() - t0)))
                continue
            capture_watch.ok(hwnd)   # captura voltou -> zera o contador da janela
            fh, fw = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            crops = list(detect_table_crops(rgb, max_tables=args.max_tables))
            # FILTRA O LOBBY (falso-positivo de "mesa"): o painel do lobby tem BADGES de
            # buy-in (cartões de torneio) e o detector o conta como mesa (mesas=2 quando
            # só há 1). Mesa de jogo não tem badge. Remove o lobby p/ contagem/log corretos.
            _real = []
            for p in crops:
                _x, _y, _bw, _bh = map(int, p.box)
                if len(find_buyin_badges(frame[_y:_y + _bh, _x:_x + _bw])) == 0:
                    _real.append(p)
                else:
                    print('[%03d] LOBBY ignorado (crop x=%d, tem badges de buy-in)' % (n, _x), flush=True)
            crops = _real
            hero_turn_seen = False
            for prop in crops:
                x, y, bw, bh = map(int, prop.box)
                crop = frame[y:y + bh, x:x + bw]
                tkey_local = _table_key(x, y)
                tkey = '%x:%s' % (hwnd, tkey_local)    # chave GLOBAL (isola entre janelas)
                # ROTINA: FIM DE TORNEIO (eliminação). A tela Ranking+Ficar/Sair NÃO é
                # linha de ação, então o fast-path a pularia p/ sempre (o agente ficava
                # ocioso numa mesa morta). Detecta ANTES: ao cair, FECHA a mesa (clica
                # 'Sair') e REGISTRA a métrica de desempenho (ranking/posição/campo).
                te = detect_tournament_end(crop)
                if te['status'] == 'TOURNAMENT_END':
                    tk = tkey_local
                    anticip.invalidate(tkey)           # mesa morta: esquece preparações
                    anticip_turns.close(tkey)
                    hero_mem.invalidate(tkey)
                    if (hwnd, tk) in tourneys_closed:
                        continue
                    # Autorização de input AO VIVO: só fecha (clica 'Sair') se ARMADO
                    # E o controle permitir agora. PAUSADO/DESABILITADO -> dry-run, mesmo
                    # com --arm (o fechamento é input e respeita a pausa como o clique).
                    close_armed = args.arm and control.execution_allowed()
                    closed = _close_tournament_table(frame, (x, y, bw, bh), te, hwnd,
                                                     adapter, engine, close_armed)
                    record_tournament_end(
                        ranking=te.get('ranking'), result='busted', mode=args.mode,
                        action='closed_via_sair' if close_armed else 'detected_dry_run',
                        closed=closed, table_key=tk)
                    tourneys_closed.add((hwnd, tk))
                    print('[%03d] >>> TORNEIO ENCERRADO (ranking %s) -> %s | metrica registrada'
                          % (n, te.get('ranking'),
                             ('SAIR clicado, fechado=%s' % closed) if args.arm else 'DRY-RUN (so detecta)'),
                          flush=True)
                    continue
                # D9/D17: mesa VIVA num slot (hwnd+tkey) que estava marcado como FECHADO
                # = re-entry / novo torneio no HWND reusado. Limpa o marcador (senão o fim
                # do NOVO torneio seria ignorado) e INVALIDA a memória da mesa antiga
                # (cartas/agressor/antecipação não vazam p/ o torneio novo).
                if (hwnd, tkey_local) in tourneys_closed:
                    tourneys_closed.discard((hwnd, tkey_local))
                    hero_mem.invalidate(tkey)
                    anticip.invalidate(tkey)
                    anticip_turns.close(tkey)
                    print('[%03d] mesa reaberta no slot %s (hwnd 0x%x) -> novo torneio: '
                          'marcador/limpo, memoria invalidada' % (n, tkey_local, hwnd), flush=True)
                # FAST-PATH (agilidade): read_action_buttons custa ~1ms; advise_table
                # ~330ms. Como o operador só AGE na vez do hero, pulamos a leitura
                # pesada quando NÃO é a vez — ciclo ocioso cai de ~900ms p/ ~250ms.
                # (Trade-off: sem advise_table fora da vez, não se rastreia o agressor
                #  pré-flop entre frames; a decisão na vez relê as apostas do frame atual.)
                br0 = read_action_buttons(crop)
                if br0['status'] != 'EXPERIMENTAL_BUTTON_ROW':
                    anticip_turns.on_nonturn(tkey)     # A2: pisca isolado NÃO fecha a época
                    continue
                hero_turn_seen = True
                # Memória de cartas do hero por mão (imutáveis): fallback quando um
                # frame não lê, evitando HERO_CARDS_UNKNOWN por falha pontual.
                hk = read_hand_id(crop)
                hkey = hk.get('hand_id') or hk.get('hand_number')
                # A1/A2 (época de decisão): a vez está presente. O tracker incrementa a
                # época só quando a vez (re)abre de verdade (após `debounce` visitas fora)
                # ou a mão muda — um pisca isolado mantém a época -> reusa em vez de
                # recomputar. Dentro da época o vilão não pode agir: decisão congelada.
                epoch = anticip_turns.on_turn(tkey, hkey)
                override = hero_mem.pair(tkey, hkey) if hkey else None
                # A1: REUSO. Se já há decisão SEGURA (fold/check) preparada p/ esta mesma
                # vez (mesma época), pula o cérebro (~330ms). O store revalida: cartas
                # batendo + ação ainda oferecida AGORA. call/raise/pós-flop nunca entram
                # no store -> recomputam. Só com --antecipar.
                reuse = None
                if args.antecipar and hkey is not None and (tkey, hkey, epoch) in anticip_payload:
                    # Lê o board (barato) só aqui: um flop novo na MESMA época invalida a
                    # decisão pré-flop preparada — a impressão digital inclui a rua.
                    _bsig = _board_sig(read_board(crop, hero_cards=override or [None, None]))
                    reuse = anticip.take(tkey, (hkey, epoch), (epoch, _bsig),
                                         available_actions(br0.get('buttons')), override)
                if reuse is not None:
                    result, _ = anticip_payload[(tkey, hkey, epoch)]
                    latency.incr('antecipado')
                    print('[%03d] A1 ANTECIPADO: reusa %s (mesa %s epoca %d) sem repagar o cerebro'
                          % (n, reuse['action'].upper(), tkey_local, epoch), flush=True)
                else:
                    try:
                        with latency.span('percepcao_cerebro'):
                            result = advise_table(crop, advisor, stabilizer=stabilizer,
                                                  table_key=tkey, hero_override=override,
                                                  tracker=aggr_tracker, bounty_bb=args.bounty_bb,
                                                  mode=args.mode, stage=args.stage, enable_hud=args.hud,
                                                  read_cache=read_cache)
                        advise_watch.ok(tkey)   # D7: leitura/cérebro voltou nesta mesa
                    except Exception as e:                 # noqa: BLE001
                        # NUNCA silencioso (regra do Eduardo: logar TUDO): registra o erro
                        # da leitura/cérebro e PULA p/ a próxima mão/mesa — o fluxo não quebra.
                        # D7: circuit-breaker — se a MESMA mesa falha sempre (layout novo/
                        # skin), escala o aviso em vez de perder a mão em silêncio a cada vez.
                        fails, alert = advise_watch.fail(tkey)
                        tag = ' [*** MESA TRAVADA: %d falhas seguidas ***]' % fails if alert else ''
                        print('[%03d] ERRO advise_table mesa(%d,%d): %s -> pula p/ proxima%s'
                              % (n, x, y, str(e)[:90], tag), flush=True)
                        continue
                    # A1: guarda a decisão SEGURA desta vez p/ reusar em revisitas da mesma
                    # época. prepare() só aceita fold/check pré-flop ADVICE (nunca fold de
                    # premium); o payload guarda o result inteiro p/ o downstream intacto.
                    if args.antecipar and result.get('is_table') and hkey is not None:
                        _adv = result.get('advice') or {}
                        if anticip.prepare(tkey, (hkey, epoch), _adv,
                                           (epoch, _board_sig(result.get('board'))),
                                           result.get('hero_cards'), is_premium=_is_premium):
                            anticip_payload[(tkey, hkey, epoch)] = (result, _adv)
                            while len(anticip_payload) > 256:
                                anticip_payload.pop(next(iter(anticip_payload)))
                if not result.get('is_table'):
                    continue
                # Memória temporal por-slot: alimenta com os candidatos deste frame (só
                # quando o cérebro rodou de verdade; no reuso A1 o result é cacheado e
                # recontaria o mesmo frame). Recupera o par quando um slot pisca AMBÍGUO
                # num frame e lê no outro -> override na próxima vez, sem inventar carta.
                if hkey and reuse is None:
                    hero_mem.observe(tkey, hkey, result.get('hero_slots') or [None, None])
                # O rastreador do agressor pré-flop e o recálculo do pós-flop em contexto
                # (pot_type/iniciativa/range do vilão) agora ficam DENTRO de advise_table
                # (tracker=aggr_tracker), compartilhados com os observadores contínuos.
                br = read_action_buttons(crop)
                if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    hero_turn_seen = True
                hid = hkey
                adv = result.get('advice') or {}
                if adv.get('phase') == 'postflop':
                    # Pós-flop NÃO executa a ESTRATÉGIA (não-validada): sem bet/call/raise.
                    # D6 — ANTI-FREEZE: se há CHECK (GRÁTIS, não compromete ficha), clica
                    # CHECK p/ não perder a mão no relógio (ver turn/river de graça).
                    # Enfrentando aposta (sem CHECK) NÃO age: nunca comita NEM folda cego
                    # pós-flop. CHECK = piso SAFETY_NONCOMMIT (autorizado por legalidade).
                    has_check = br['status'] == 'EXPERIMENTAL_BUTTON_ROW' and any(
                        b.get('action') == 'CHECK' for b in br.get('buttons', []))
                    if br['status'] == 'EXPERIMENTAL_BUTTON_ROW' and adv.get('status') == 'ADVICE':
                        eqtxt = ''
                        if adv.get('equity') is not None:
                            eqtxt = ' | eq=%.0f%% vs pot_odds=%.0f%%' % (
                                adv['equity'] * 100, (adv.get('pot_odds') or 0) * 100)
                        print('[%03d] vez do hero PÓS-FLOP (%s): %s %s%s | estrategia nao executa%s'
                              % (n, adv.get('street'), str(adv.get('recommended')).upper(),
                                 adv.get('made') or '', eqtxt,
                                 ' (CHECK gratis anti-freeze)' if has_check else ''), flush=True)
                    elif br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                        print('[%03d] vez do hero PÓS-FLOP (%s): ABSTEM %s | mao=%s%s'
                              % (n, adv.get('street'), adv.get('reason'), adv.get('made'),
                                 ' | CHECK gratis anti-freeze' if has_check else ' | sem execucao'), flush=True)
                    if has_check:
                        check_adv = dict(status='ADVICE', recommended='check', validated=False,
                                         phase='postflop', anti_freeze=True)
                        out = executor.execute(dict(result, advice=check_adv), br, origin=(x, y),
                                               frame_size=(fw, fh), input_adapter=adapter,
                                               validator=validator, verifier=verifier,
                                               hand_id=hid, table_key=tkey_local)
                        if out.get('acted'):
                            print('[%03d] >>> POS-FLOP anti-freeze: CHECK %s'
                                  % (n, 'DRY-RUN' if out['dry_run'] else 'REAL'), flush=True)
                            _emit_shadow(result, adv, 'check', out)
                    continue
                # LOG DO CÉREBRO (toda vez do hero, pré-flop): grava POR QUE a decisão
                # saiu — hero, posição, to_call, apostas, spot, nó, validated, equity/req.
                # Sem isto não dá pra auditar erros graves (ex.: cold-call de Q6o) no fim
                # da sessão. É a base pra achar/consertar o erro com FATO.
                if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    _ts = result.get('table_state') or {}
                    _p = _ts.get('positions') or {}
                    _bets = [(_p.get(b.get('seat')), b.get('bet_bb')) for b in (_ts.get('bets') or [])]
                    print('[%03d] CEREBRO m%s hero=%s pos=%s to_call=%s bets=%s | spot=%s node=%s val=%s eq=%s req=%s -> %s %s' % (
                        n, tkey_local, result.get('hero_cards'), _p.get('hero'),
                        _ts.get('to_call_bb'), _bets, adv.get('spot'), adv.get('node_id'),
                        adv.get('validated'), adv.get('equity'),
                        adv.get('required_equity_icm') or adv.get('required_equity'),
                        adv.get('status'), adv.get('recommended') or adv.get('reason') or ''), flush=True)
                # GUARDA DEEP NÃO-VALIDADA (erro grave): a base HRC é validada só p/
                # short (bucket <=25). Em bucket 40/100 (deep) o cérebro usa RANGES DE
                # REFERÊNCIA NÃO-validados (val=False), largos → cold-call de lixo (Q6o).
                # Regra: nó deep não-validado NUNCA compromete fichas — só joga o SEGURO
                # (CHECK grátis senão FOLD). Folds de lixo deep seguem iguais.
                if br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    _nid = (adv.get('node_id') or '').split('|')
                    _bkt = int(_nid[2]) if len(_nid) > 2 and _nid[2].isdigit() else None
                    if (adv.get('validated') is False and _bkt is not None and _bkt > 25
                            and adv.get('recommended') not in ('fold', 'check', None)):
                        _hc = any(b.get('action') == 'CHECK' for b in br.get('buttons', []))
                        _safe = 'check' if _hc else 'fold'
                        print('[%03d] GUARDA DEEP(bucket %s nao-validado): %s -> SEGURO %s'
                              % (n, _bkt, adv.get('recommended'), _safe), flush=True)
                        # B04: NÃO fabrica validated=True. O seguro (check/fold) é piso
                        # de não-commit -> o contrato autoriza por SAFETY_NONCOMMIT, sem
                        # mentir que o cérebro validou. Mantém validated=False + flag.
                        adv = dict(adv, recommended=_safe, status='ADVICE',
                                   validated=False, phase='preflop', deep_guard=True)
                        result = dict(result, advice=adv)
                _, caveats = map_advice_to_action(adv.get('recommended'))
                is_raise = 'REQUIRES_SIZING_MULTISTEP' in caveats
                # RAISE = fluxo multi-etapa (sequenciador). Só executa ARMADO (em
                # dry-run os cliques não abrem o painel de verdade).
                if (br['status'] == 'EXPERIMENTAL_BUTTON_ROW' and adv.get('status') == 'ADVICE'
                        and is_raise and (tkey, hid) not in raise_done):
                    tmult = target_multiplier(adv, result.get('table_state'))
                    if tmult is None:
                        print('[%03d] vez do hero: RAISE sem target de size -> abstem' % n, flush=True)
                    elif not args.arm:
                        pr = map_multiplier_to_preset(tmult, read_raise_panel(crop).get('presets') or [])
                        print('[%03d] vez do hero: RAISE alvo %.2fx (preset %s) | DRY-RUN: sequencia so executa armada'
                              % (n, tmult, (pr and pr['label']) or '?'), flush=True)
                    elif not control.execution_allowed():
                        print('[%03d] RAISE mas BOT PAUSADO' % n, flush=True)
                    elif not adv.get('validated'):
                        # Autorização única também no RAISE: nó não validado
                        # (referência/deep) não dispara a sequência armada (só estuda).
                        print('[%03d] RAISE de no NAO VALIDADO -> nao executa (so estuda)' % n, flush=True)
                    else:
                        seq = RaiseSequencer(capture=lambda h=hwnd: engine.capture_frame(hwnd=h),
                                             window_rect=lambda h=hwnd: _discover_rect(h),
                                             input_adapter=adapter, target_mult=tmult,
                                             bot_control=control, table_key=tkey_local, hand=hid,
                                             max_tables=args.max_tables)
                        res = seq.run()
                        key = (tkey, hid)
                        # D4: ok=True = aposta submetida -> feito, NUNCA re-tenta. ok=False
                        # = nada submetido (o passo 0 do seq revalida a vez) -> re-tenta no
                        # próximo ciclo, com CAP p/ não travar. Nunca duplica raise.
                        decision, raise_attempts[key] = raise_outcome(res, raise_attempts.get(key, 0))
                        if decision != 'retry':
                            raise_done.add(key)
                            raise_attempts.pop(key, None)
                        if decision == 'done':
                            print('[%03d] >>> RAISE sequencia: preset %sx confirmado=%s' % (
                                n, res.get('preset'), res.get('confirmed')), flush=True)
                        elif decision == 'giveup':
                            print('[%03d] [*** RAISE sem efeito apos cap: %s -> desiste (mao pode '
                                  'precisar de atencao) ***]' % (n, res.get('reason')), flush=True)
                        else:
                            print('[%03d] RAISE sem efeito (%s) -> re-tenta no proximo ciclo '
                                  '(seq revalida a vez)' % (n, res.get('reason')), flush=True)
                        _emit_shadow(result, adv, adv.get('recommended') or 'raise',
                                     {'authority': 'VALIDATED', 'state': res.get('reason')
                                      or ('confirmado=%s' % res.get('confirmed'))})
                    continue
                out = executor.execute(result, br, origin=(x, y), frame_size=(fw, fh),
                                       input_adapter=adapter, validator=validator,
                                       verifier=verifier, hand_id=hid, table_key=tkey_local)
                # FALLBACK ANTI-FREEZE (crítico): se o advisor ABSTEVE (sem nó validado
                # p/ a rota), o operador NUNCA pode congelar na vez do hero — ele morreria
                # no relógio e perderia a mão. Joga o SEGURO: CHECK se há (grátis), senão
                # FOLD. Garante que o hero SEMPRE age. Só pré-flop (pós-flop e raise saem
                # antes), só armado, e só quando a razão foi abstenção (não 'já agiu'/pausa).
                # NUNCA FOLDAR ÀS CEGAS: o fallback só age se as CARTAS do hero foram
                # LIDAS. Sem leitura (hero_cards None), ABSTÉM e tenta de novo no próximo
                # frame (a leitura quase sempre volta; a hero_mem reaproveita a mão).
                # Foldar sem ver as cartas largava PREMIUM (ex.: KK) — erro gravíssimo.
                if (not out.get('acted')
                        and str(out.get('reason', '')).startswith('SEM_ACAO_RECOMENDADA')
                        and br['status'] == 'EXPERIMENTAL_BUTTON_ROW'
                        and result.get('hero_cards')):
                    has_check = any(b.get('action') == 'CHECK' for b in br.get('buttons', []))
                    fb = 'check' if has_check else 'fold'
                    # BLINDAGEM DE PREMIUM: NUNCA foldar um monstro (KK/AA/AK...) por falta
                    # de nó. Se o fallback foldaria e a mão é premium, PAGA (call) em vez
                    # de largar — ex.: 3bet KK, tomou 4bet shove, sem nó -> CALL, não fold.
                    premium_commit = False
                    if fb == 'fold' and _is_premium(result.get('hero_cards')):
                        fb = 'call'
                        premium_commit = True
                        print('[%03d] BLINDAGEM PREMIUM: %s sem no -> CALL (NUNCA folda monstro)'
                              % (n, result.get('hero_cards')), flush=True)
                    # B04: o fallback NÃO fabrica validated=True. check/fold = piso de
                    # não-commit (contrato autoriza por SAFETY_NONCOMMIT). O CALL premium
                    # é autoridade SEPARADA e NÃO-validada (safety_premium, Opção A do
                    # usuário): paga o monstro, mas sem mentir validade -> marca lacuna
                    # de cobertura p/ resolver no P1.
                    fb_adv = dict(status='ADVICE', recommended=fb, validated=False,
                                  phase='preflop', fallback=True)
                    if premium_commit:
                        fb_adv['safety_premium'] = True
                    fb_result = dict(result, advice=fb_adv)
                    out = executor.execute(fb_result, br, origin=(x, y), frame_size=(fw, fh),
                                           input_adapter=adapter, validator=validator,
                                           verifier=verifier, hand_id=hid, table_key=tkey_local)
                    if out.get('acted'):
                        print('[%03d] >>> FALLBACK anti-freeze: %s | autoridade=%s%s'
                              % (n, fb.upper(), out.get('authority'),
                                 ' (LACUNA DE COBERTURA premium -> P1)' if premium_commit else ''),
                              flush=True)
                        if overlay:
                            overlay.set_table('mesa %s' % tkey_local, '>>> FALLBACK %s' % fb.upper())
                if out.get('acted'):
                    latency.note('idade_snapshot', (time.monotonic() - cap_ts) * 1000)
                    pl = out['plan']
                    print('[%03d] >>> AGIU: %s em %s | autoridade=%s estado=%s %s %s' % (
                        n, pl['action'],
                        tuple(round(c) for c in pl.get('screen_center', pl['center'])),
                        out.get('authority'),
                        out['state'], 'DRY-RUN' if out['dry_run'] else 'REAL',
                        out['reasons'] or ''), flush=True)
                    if overlay:
                        overlay.set_table('mesa %s' % tkey_local, '>>> %s %s (%s)' % (
                            pl['action'], result.get('hero_cards') or '',
                            'DRY' if out['dry_run'] else 'REAL'))
                    _emit_shadow(result, adv, pl['action'].lower(), out)
                elif br['status'] == 'EXPERIMENTAL_BUTTON_ROW':
                    # Vez do hero mas NÃO agiu (raise multi-etapa / abstenção / já agiu):
                    # mostra a decisão para a demo.
                    adv = result.get('advice') or {}
                    _emit_shadow(result, adv, None, out)
                    pos = (result.get('table_state', {}).get('positions') or {}).get('hero')
                    print('[%03d] vez do hero: %s %s | conselho=%s %s | executor: %s' % (
                        n, result.get('hero_cards'), pos, adv.get('status'),
                        adv.get('recommended') or adv.get('reason') or '',
                        out.get('reason')), flush=True)
                    if overlay:
                        overlay.set_table('mesa %s' % tkey_local, '%s %s -> %s %s' % (
                            result.get('hero_cards') or '?', pos or '',
                            adv.get('status'), adv.get('recommended') or adv.get('reason') or ''))
            # heartbeat: a cada ~8 frames sem vez-do-hero, mostra que está vivo
            if not hero_turn_seen and n % 8 == 0:
                print('[%03d] . vivo | mesas=%d | sua vez: nao | estado=%s'
                      % (n, len(crops), control.state), flush=True)
            latency.record('ciclo', (time.monotonic() - t0) * 1000)
            if n % 50 == 0:                      # A0: resumo periódico de latência
                print(latency.format_report('LATENCIA (A0) @ciclo %d' % n), flush=True)
            time.sleep(max(0.1, args.intervalo - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        print('Encerrado pelo usuario.', flush=True)
    finally:
        if listener:
            listener.stop()
        if overlay:
            overlay.stop()
        print(latency.format_report('LATENCIA (A0) — resumo final'), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
