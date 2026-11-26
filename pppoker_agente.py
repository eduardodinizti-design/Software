"""AGENTE de produção do PPPoker (percepção por DADOS/protobuf, nos moldes do suprema_agente).

Fluxo por mesa: estado da memória (protobuf) -> MESMO cérebro (advise_from_protobuf) -> PLANO
(ação de botão via action_coordinator) -> executa SÓ se ARMADO. DRY por padrão (BotControl começa
PAUSED: execution_allowed()=False), igual à Suprema.

OFFLINE-FIRST / testável: a percepção é um `state_source()` injetável (arquivo estado_mesa.json ao
vivo, OU uma captura no --once) e a execução é um `execute()` injetável. Nada aqui lê tela nem
clica: o CLICKER VIVO (operar_mesa/cursor, que precisa das coords dos botões por OCR) é a camada
viva que se pluga como `execute` ao ARMAR — construída e validada à parte, por ordem do Eduardo.

Anti-thrash (igual suprema): UMA ação por (mesa, mão, rua). A "mão" é a dupla de cartas do hero
(muda a cada mão nova); a "rua" vem do board. Só re-age na mesma mão/rua se enfrentar aposta MAIOR
(to_call subiu > 1bb) — flicker não re-dispara.
"""
from __future__ import annotations

import argparse
import os
import time

from action_coordinator import map_advice_to_action
from pppoker_replay import decide_entry, load_capture, format_line

_REFIRE_EPS_BB = 1.0           # só re-age na mesma mão/rua se to_call subir mais que isto


def street_of(entry):
    """Rua pela contagem do board (protobuf dá o board EXATO): 0=PRE,3=FLOP,4=TURN,5=RIVER."""
    board = ((entry or {}).get('table') or {}).get('board') or []
    n = len(board)
    return {0: 'PRE', 3: 'FLOP', 4: 'TURN', 5: 'RIVER'}.get(n, 'PRE' if n == 0 else 'POS')


def plan_from_decision(d):
    """Traduz a decisão do cérebro (d['recommended']) no PLANO de botão do PPPoker (puro).
    {action: FOLD/CHECK/CALL/BET/RAISE, caveats:[...], size, recommended} ou None se não mapear."""
    action, caveats = map_advice_to_action(d.get('recommended'))
    if action is None:
        return None
    return dict(action=action, caveats=caveats, size=d.get('size'), bucket=d.get('bucket'),
                recommended=d.get('recommended'), to_call_bb=d.get('to_call_bb'))


def make_table_emit(advisor, *, control=None, execute=None, stats=None, log=print,
                    mode='chip_ev', stage='mid', env=None, multi_bind=False, guards=None, recorder=None):
    """Fábrica do emit por mesa: decide 1x por spot (anti-thrash), loga, e CLICA só se ARMADO
    (control.execution_allowed()). `execute(plan, table_key, entry)` é o clicker vivo injetado
    (None = DRY puro). Devolve emit(table_key, entry) -> dict da decisão (com 'plan' e 'fired').

    GUARDA ANTI-CROSS: `env` é um dict compartilhado que o run() atualiza com env['n_tables'] (nº de
    mesas vivas no frame). Com 2+ mesas E sem binding por tile (`multi_bind=False`), o grab single-
    table não sabe QUAL recorte é a mesa decidida -> NÃO clica (abstém), nunca cruza mesa.

    GUARDAS+H2N (opcionais): `guards` (ppp_guards.GuardMonitor) decide bust/sit-out ANTES de agir —
    bust -> PARA a mesa (não decide/clica); sit-out -> sinaliza VOLTAR. `recorder` (ppp_h2n.HandRecorder)
    grava as mãos passivamente. None = desligado (DRY/testes não gravam arquivo)."""
    acted = {}                 # (mesa, mão, rua) -> último to_call_bb executado (trava 1-tentativa)
    stats = stats if stats is not None else {}
    env = env if env is not None else {}

    def emit(table_key, entry):
        if recorder is not None:                 # H2N: grava a mão (passivo, nunca atrapalha)
            try:
                recorder.observe_table(table_key, entry)
            except Exception as e:
                log('[PPP %s] H2N falhou: %s' % (table_key, e))
        if guards is not None:                   # GUARDAS: bust/sit-out ANTES de decidir/clicar
            try:
                gd = guards.update(entry, table_key)
            except Exception as e:
                gd = None
                log('[PPP %s] guarda falhou: %s' % (table_key, e))
            if gd and gd.get('action') == 'STOP':
                log('[PPP %s] GUARDA: bust do hero -> PARA a mesa (%s)' % (table_key, gd.get('reason')))
                stats['bust'] = stats.get('bust', 0) + 1
                return {'status': 'GUARD_STOP', 'reason': gd.get('reason'), 'plan': None, 'fired': False}
            if gd and gd.get('action') == 'SITOUT_RETURN':
                log('[PPP %s] GUARDA: sit-out do hero -> VOLTAR (nunca foldar p/ walk)' % table_key)
                stats['sitout'] = stats.get('sitout', 0) + 1
                # o clique "Voltar" é do agente; locator do botão ainda não plugado -> por ora só sinaliza
                return {'status': 'GUARD_SITOUT', 'plan': None, 'fired': False}
        d = decide_entry(table_key, entry, advisor, mode=mode, stage=stage)
        d['plan'] = None
        d['fired'] = False
        if d.get('status') != 'ADVICE' or not d.get('recommended'):
            log('[PPP %s] %s (não age: %s)' % (table_key, d.get('status'), d.get('reason')))
            return d
        hand_key = tuple(d['hero']) if d.get('hero') else None
        street = street_of(entry)
        akey = (table_key, hand_key, street)
        tc = d.get('to_call_bb') or 0.0
        last = acted.get(akey)
        if last is not None and tc <= last + _REFIRE_EPS_BB:
            log('[PPP %s] mão=%s %s já agiu (to_call %.1f<=%.1f) -> IGNORA (1 tentativa só)'
                % (table_key, hand_key, street, tc, last))
            return d
        plan = plan_from_decision(d)
        d['plan'] = plan
        acted[akey] = tc        # MARCA antes de clicar -> nunca re-clica a mesma ação
        allowed = control.execution_allowed() if control is not None else False
        tag = '' if allowed else '  [DRY: não clica]'
        log('%s  CÉREBRO=%s PLANO=%s%s%s' % (
            format_line(d), d.get('recommended'),
            (plan or {}).get('action'),
            (' %s' % plan['size']) if plan and plan.get('size') is not None else '', tag))
        if allowed and execute is not None and plan and plan.get('action'):
            n_tables = int(env.get('n_tables', 1) or 1)
            if n_tables > 1 and not multi_bind:
                log('[PPP %s] %d mesas vivas e SEM binding por tile -> NÃO clica (anti-cross)'
                    % (table_key, n_tables))
                return d
            try:
                execute(plan, table_key, entry)
                d['fired'] = True
                stats['acoes'] = stats.get('acoes', 0) + 1
            except Exception as e:
                log('[PPP %s] execução falhou: %s' % (table_key, e))
        return d

    return emit


def run_once(entries, emit):
    """Processa um lote de (table_key, entry) UMA vez (offline: uma captura). Devolve as decisões."""
    return [emit(k, e) for k, e in entries]


def file_state_source(path):
    """state_source() que relê o estado_mesa.json a cada tick (o emitter Frida reescreve ao vivo).
    Devolve lista de (table_key, entry); [] se o arquivo sumiu/corrompeu (nunca lança)."""
    def source():
        try:
            return load_capture(path)
        except Exception:
            return []
    return source


def run(state_source, emit, stop, *, interval=1.0, seconds=0.0, env=None):
    """Laço vivo: a cada `interval`s pega o estado atual e roda o emit por mesa. Para quando `stop`
    é setado (ou após `seconds`, se >0). `stop` tem .is_set()/.wait() (threading.Event).
    Atualiza env['n_tables'] (nº de mesas vivas no frame) p/ a guarda anti-cross do emit."""
    t0 = time.time()
    while not stop.is_set() and (seconds <= 0 or time.time() - t0 < seconds):
        entries = state_source()
        if env is not None:
            env['n_tables'] = len(entries)
        for table_key, entry in entries:
            try:
                emit(table_key, entry)
            except Exception:
                pass
        stop.wait(interval)


def build_live_execute(hwnd, *, control=None, grab_frame=None, adapter=None, on_sizing=None,
                       enable_sizing=False, log=print):
    """Monta o CLICKER VIVO (ppp_execute.make_execute) com as peças reais e VALIDADAS:
      - grab_frame = ppp_grab.make_grab(hwnd) (captura+crop da mesa; single-table ok, multi abstém);
      - adapter = WindowsCursorInput() (cursor FÍSICO, SendInput);
      - on_sizing = ppp_sizing.make_on_sizing(hwnd) (RAISE/BET: RaiseSequencer pré + postflop_bet
        pós, captura ImageGrab) — montado quando `control` é dado; sem ele, RAISE/BET não clica.
    Só use isto com o Henrique ARMADO, por ordem do Eduardo [[nvt-regra-master-sem-autonomia]]."""
    import ppp_execute
    if grab_frame is None:
        import ppp_grab
        # multi-mesa SEGURO por PROJEÇÃO: roomid -> rect de tela Unity (readTilesScreen) -> recorta
        # DIRETO (robusto a clutter/sobreposição) + rede anti-oclusão. Sem tiles.json (produtor
        # parado) a grab abstém -> nunca cruza.
        # MONITOR PRINCIPAL (VALIDADO 25/11 - cursor caiu EXATO no Fold): coords da imagem == coords de
        # tela (origem 0,0, 100%), sem offset de janela/projeção/DPI multi-monitor. AUTO escolhe mesa
        # única (maior blob de feltro) ou multi-mesa (binding por ordem via tiles.json do emitter).
        grab_frame = ppp_grab.make_grab_primary_auto(
            tiles_source=ppp_grab.make_tiles_screen_source(), log=log)
    if adapter is None:
        # CURSOR EM CURVA (LEI do Eduardo: ver o mouse se movendo, nunca teleporte). SmoothCursor
        # envolve o WindowsCursorInput físico com min-jerk+Bézier (mesmo padrão da Suprema).
        from smooth_cursor import SmoothCursor
        adapter = SmoothCursor()
        # ÁRBITRO DE CURSOR GLOBAL: serializa TODO move/click/drag com a Suprema (mutex nomeado +
        # fila in-process) -> sem BRIGA DE CURSOR quando as duas plataformas jogam juntas pelo launcher.
        # Solo, o mutex é descontendido (sem custo). Em cursor ocupado, o adapter PULA o clique (não força).
        try:
            from cursor_arbiter import make_arbitrated_adapter
            adapter = make_arbitrated_adapter(adapter, plataforma='PPPOKER')
        except Exception as e:
            log('[PPP] árbitro de cursor off (%s) -> cursor direto' % e)
    # SEGURANÇA: o sizing (raise/bet) só é plugado com enable_sizing=True. Por padrão NÃO — o painel
    # de aposta ainda não foi calibrado ao vivo; sem on_sizing, raise/bet NÃO clica (loga e pula).
    if on_sizing is None and enable_sizing and control is not None:
        import ppp_sizing
        on_sizing = ppp_sizing.make_on_sizing(hwnd, adapter=adapter, control=control, log=log)
    return ppp_execute.make_execute(hwnd, adapter, grab_frame=grab_frame, on_sizing=on_sizing, log=log)


def _load_advisor():
    from assistir_suprema import load_advisor
    return load_advisor()


DEFAULT_CAPTURE = os.path.join('research', 'ppp_il2cpp', 'estado_mesa_multitable_20261120.json')
DEFAULT_LIVE = os.path.join('logs', 'estado_mesa.json')


def main(argv=None):
    ap = argparse.ArgumentParser(description='Agente PPPoker por dados (protobuf). DRY por padrão.')
    ap.add_argument('--once', metavar='CAPTURA', nargs='?', const=DEFAULT_CAPTURE,
                    help='processa UMA captura estado_mesa*.json e sai (offline, DRY). '
                         'Sem valor usa a captura de exemplo do repo.')
    ap.add_argument('--live', metavar='ARQUIVO', default=DEFAULT_LIVE,
                    help='estado_mesa.json escrito pelo emitter Frida (laço vivo).')
    ap.add_argument('--interval', type=float, default=1.0)
    ap.add_argument('--seconds', type=float, default=0.0)
    ap.add_argument('--armar', action='store_true',
                    help='ARMA: monta o CLICKER FÍSICO (WindowsCursorInput) e control=RUNNING -> '
                         'CLICA de verdade na mesa. Por padrão SÓ single-click (fold/check/call).')
    ap.add_argument('--sizing', action='store_true',
                    help='(com --armar) também clica RAISE/BET (painel multi-etapa). OFF por padrão: '
                         'o painel de aposta ainda não foi calibrado ao vivo.')
    ap.add_argument('--hwnd', type=int, default=0,
                    help='(com --armar) FIXA a janela-alvo (multi-instância). 0 = primeira achada.')
    ap.add_argument('--no-guards', action='store_true', help='desliga as guardas de bust/sit-out.')
    ap.add_argument('--no-h2n', action='store_true', help='desliga o tracker de mãos (H2N).')
    args = ap.parse_args(argv)

    from bot_control import BotControl
    control = BotControl()       # default PAUSED = DRY
    execute = None
    if args.armar:
        control.resume()         # PAUSED -> RUNNING (execution_allowed True)
        try:
            import operar_mesa
            wins = operar_mesa.discover_pppoker().get('windows', [])
            if not wins:
                print('[PPP] --armar: nenhuma janela PPPoker -> não arma.')
                return 1
            if args.hwnd:
                if args.hwnd not in [w['hwnd'] for w in wins]:
                    print('[PPP] --hwnd %s não está entre as janelas abertas -> não arma.' % args.hwnd)
                    return 1
                hwnd = args.hwnd
            else:
                hwnd = wins[0]['hwnd']
            execute = build_live_execute(hwnd, control=control, enable_sizing=args.sizing)
            print('[PPP] ARMADO: clicker FÍSICO no hwnd %s | sizing=%s | single-table. '
                  'O cursor vai CLICAR. Mexa o mouse p/ assumir.'
                  % (hwnd, 'ON' if args.sizing else 'OFF (raise/bet não clica)'))
        except Exception as e:
            print('[PPP] --armar falhou ao montar o clicker: %s -> segue DRY' % e)
            execute = None

    advisor = _load_advisor()
    env = {'n_tables': 1}        # run() atualiza; emit usa p/ a guarda anti-cross
    # GUARDAS (bust/sit-out) + H2N (tracker de mãos). Passivos e seguros; grava o histórico mesmo em DRY.
    guards = recorder = None
    if not args.no_guards:
        try:
            import ppp_guards
            guards = ppp_guards.GuardMonitor(need=3)
        except Exception as e:
            print('[PPP] guardas off (%s)' % e)
    if not args.no_h2n:
        try:
            import ppp_h2n
            recorder = ppp_h2n.HandRecorder()
        except Exception as e:
            print('[PPP] H2N off (%s)' % e)
    # com o clicker vivo montado, a grab casa a mesa por tiles.json -> multi-mesa é seguro (multi_bind).
    emit = make_table_emit(advisor, control=control, execute=execute, env=env,
                           multi_bind=bool(execute), guards=guards, recorder=recorder)

    if args.once is not None:
        path = args.once
        if not os.path.exists(path):
            print('(captura ausente: %s)' % path)
            return 1
        print('== --once %s ==' % path)
        run_once(load_capture(path), emit)
        if recorder is not None:
            recorder.flush()
        return 0

    import threading
    stop = threading.Event()
    print('== PPPoker agente VIVO (DRY=%s) lendo %s a cada %.1fs ==  (Ctrl+C para sair)'
          % (not control.execution_allowed(), args.live, args.interval))
    try:
        run(file_state_source(args.live), emit, stop, interval=args.interval, seconds=args.seconds, env=env)
    except KeyboardInterrupt:
        stop.set()
    finally:
        if recorder is not None:
            try:
                recorder.flush()        # fecha/grava as mãos abertas ao encerrar a sessão
            except Exception:
                pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
