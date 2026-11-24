"""AGENTE AUTÔNOMO de PRODUÇÃO da Suprema — UM processo, UM hook de rede (SSL_read).

Funde, num só hook (o `run_live` só deixa 1 hook Frida por cliente — por isso o agente de hoje
NÃO salvava mãos: não dava pra rodar um capturador separado junto):
  (1) DECIDE + CLICA pré/pós-flop — cursor SUAVE, anti-thrash por (mão,rua), think-time humano;
  (2) SALVA as mãos em H2N — SupremaHandBuilder → HandAccumulator('SupremaPoker') → HandTextSink
      (.txt Hand2Note). Fecha o gap da auditoria (o operador não gravava hand history);
  (3) opcional (--rebuy): VIGIA rebuy em thread — Recompra SIMPLES se der tempo (política do Eduardo).

Segurança:
  - Default = DRY: observa + SALVA H2N + loga o PLANO, mas NÃO clica. Use --armed p/ jogar.
  - READ-ONLY no protocolo; ação só por clique externo (SendInput), nunca injeção.
  - Anti-thrash: 1 ação por (hand_id, rua) no pós-flop (o to_call pós-flop flicka).
  - Kill-switch: Ctrl+C / matar o processo.

Uso:
  python -I suprema_agente.py                      # DRY: salva H2N + loga o plano (não clica)
  python -I suprema_agente.py --armed              # JOGA sozinho pré+pós e salva H2N
  python -I suprema_agente.py --armed --rebuy      # idem + recompra simples se der tempo
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import random
import signal
import sys
import threading
import time
import _thread
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_TRK = r"C:\Users\tacao\NvtVoz\nvttracker"          # parser estrito do tracker (p/ re-validar saldo)
if os.path.isdir(_TRK) and _TRK not in sys.path:
    sys.path.insert(0, _TRK)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import suprema_act as A            # noqa: E402
import suprema_click as C          # noqa: E402
import suprema_net                 # noqa: E402
from click_arbiter import click_lock, ClickBusy  # noqa: E402  (lock GLOBAL do cursor: multi-plataforma)
from hand_accumulator import HandAccumulator          # noqa: E402
from hand_text_sink import HandTextSink, DEFAULT_BASE  # noqa: E402
from suprema_hand_builder import SupremaHandBuilder    # noqa: E402
from suprema_operar import find_suprema_hwnd           # noqa: E402
from bot_control import BotControl, HotkeyListener, DISABLED  # noqa: E402  (plano de controle: RUNNING/PAUSED/DISABLED)
from status_overlay import StatusOverlay                # noqa: E402  (badge na tela: ARMADO/PAUSADO/DESABILITADO)

try:
    from nvttracker.parser.nlhe_text import parse_hand, ParseError   # noqa: E402
    _HAS_PARSER = True
except Exception:
    _HAS_PARSER = False
    parse_hand = None

    class ParseError(Exception):
        pass


class SaveStats:
    """Conta as mãos salvas e re-valida o saldo (0 = conserva fichas = pronta p/ o banco)."""
    def __init__(self):
        self.ok = self.bad = self.unbalanced = 0

    def on_hand(self, text, hand):
        hid = hand.get("hand_id")
        if not _HAS_PARSER:
            self.ok += 1
            print("  [H2N] mão #%s salva" % hid, flush=True)
            return
        try:
            h = parse_hand(text, check_chips=True)
            bal = h.chip_balance()
            if bal == 0:
                self.ok += 1
            else:
                self.unbalanced += 1
            print("  [H2N] mão #%s | %s" % (hid, "OK" if bal == 0 else "SALDO!=0 (%s)" % bal), flush=True)
        except ParseError as e:
            self.bad += 1
            print("  [H2N] mão #%s | PARSE FALHOU: %s" % (hid, e), flush=True)


def _rebuy_loop(hwnd, armed, seconds, stop):
    """Thread opcional: captura a tela, detecta o modal REBUY e clica Recompra (simples) se armado.
    Cooldown p/ não re-clicar o mesmo modal. Independente do hook de rede."""
    import cv2
    import numpy as np
    from PIL import ImageGrab
    import suprema_rebuy as RB
    t0 = time.time()
    last = 0.0
    while not stop.is_set() and (seconds <= 0 or time.time() - t0 < seconds):
        try:
            left, top, w, h = C.client_rect_screen(hwnd)
            img = ImageGrab.grab(bbox=(left, top, left + w, top + h), all_screens=True)
            r = RB.find_rebuy(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))
        except Exception:
            r = None
        if r and (time.time() - last) > 25:
            fx, fy = r["recompra"]
            x, y = C.frac_to_screen(hwnd, fx, fy)
            print("[REBUY] %s modal detectado -> Recompra (%d,%d)%s"
                  % (time.strftime("%H:%M:%S"), x, y, "" if armed else " [DRY]"), flush=True)
            if armed:
                C._click_sendinput(x, y)
                print("[REBUY] >>> CLIQUE Recompra executado (rebuy simples).", flush=True)
            last = time.time()
        time.sleep(1.5)


def _human_delay(posflop, act, tocall):
    """Delay HUMANIZADO e RANDOMIZADO (LEI Eduardo): varia por mão — às vezes insta, às vezes
    'hmm... foldo', e quanto mais COMPLEXA (3bet/4bet/squeeze) ou PÓS-FLOP, mais pondera. PÓS-FLOP
    NUNCA insta. Outliers ocasionais (tanque) p/ não virar padrão legível."""
    r = random.random()
    tc = tocall if isinstance(tocall, (int, float)) else 0.0
    if posflop:                                            # pós-flop: SEMPRE pensa
        return round(random.uniform(1.8, 3.0) if r < 0.15 else random.uniform(0.7, 1.8), 2)
    if act in (A.RAISE, A.ALL_IN) and tc > 1.0:            # 3bet/4bet/squeeze/resteal: pondera
        return round(random.uniform(2.2, 3.2) if r < 0.12 else random.uniform(1.0, 2.2), 2)
    if act == A.FOLD:                                      # fold: varia (insta / normal / 'hmm')
        if r < 0.35:
            return round(random.uniform(0.0, 0.12), 2)     # insta-fold (lixo)
        if r < 0.80:
            return round(random.uniform(0.3, 1.0), 2)
        return round(random.uniform(1.0, 1.8), 2)          # 'hmm... foldo'
    if r < 0.25:                                           # open/call simples: rápido-médio variado
        return round(random.uniform(0.1, 0.3), 2)
    return round(random.uniform(0.4, 1.3), 2)


def _click_worker(q, stats, stop, *, stale_s=6.0):
    """THREAD ÚNICA de clique (Eduardo 23/11): executa as ações que o auto_emit ENFILEIRA, UMA por vez
    (sem conflito de cursor entre mesas), com o delay humano. Tira o clique da thread do callback do Frida
    -> a percepção NUNCA bloqueia -> sem backlog/"mute"/sit-out (era a causa real do travamento). Pula a
    ação que esperou demais na fila (> stale_s): a janela de ação provavelmente já passou (não clica fora
    de hora). Em regime normal a fila fica ~vazia (a percepção não bloqueia mais), então quase nunca pula."""
    while not stop.is_set():
        try:
            item = q.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            ts, plan, hwnd, ri, nr, posflop, act, tocall, delay, tag = item
            waited = time.time() - ts
            if waited > stale_s:
                print("%s %s ação STALE na fila (%.1fs) -> pulo (não clica fora de hora)"
                      % (tag, time.strftime("%H:%M:%S"), waited), flush=True)
                continue
            think = _human_delay(posflop, act, tocall)         # timing humanizado (LEI Eduardo)
            if think > 0:
                time.sleep(think)
            # ÁRBITRO DE CLIQUE (multi-plataforma): lock GLOBAL do cursor -> NÃO colide com o PPPoker
            # clicando ao mesmo tempo. Se o cursor estiver ocupado pela outra plataforma, PULA (não força).
            try:
                with click_lock():
                    res = C.execute(plan, hwnd, armed=True, step_delay=delay, room_index=ri, n_rooms=nr)
            except ClickBusy:
                print("%s %s cursor ocupado (outra plataforma) -> pulo o clique [%s]"
                      % (tag, time.strftime("%H:%M:%S"), act), flush=True)
                continue
            stats["acoes"] += 1
            print("%s %s CLIQUE[m%s/%s]: %s" % (tag, time.strftime("%H:%M:%S"), ri, nr, res), flush=True)
        except Exception as e:
            print("[AG] clique worker erro: %s" % e, flush=True)
        finally:
            try:
                q.task_done()
            except Exception:
                pass


def make_auto_emit(hwnd, *, armed, delay, stats, room=None, room_index_fn=None, n_rooms_fn=None,
                   control=None, overlay=None, click_q=None):
    """Fábrica do emit (por MESA): decide 1x por spot estável e, se armado, CLICA na COLUNA da
    mesa (room_index/n_rooms -> execute roteia). Cursor volta à posição (restore) p/ multi-mesa.
    Anti-thrash: 1 ação por (sala, hand_id, rua) no pós-flop."""
    acted = {}   # (sala, mão, rua) -> último to_call executado (trava: 1 tentativa, nunca re-clica)
    folded = set()   # (sala, mão) que o hero FOLDOU -> NUNCA mais age nela (bug Q5o: checava pós-flop
                     # uma mão já foldada pré-flop porque as cartas velhas não eram zeradas)
    _tag = ("[AG %s]" % room) if room else "[AG]"

    def auto_emit(state, advice, plan, hero):
        act = (plan or {}).get("action")
        board = (state or {}).get("board") or []
        pos = (state or {}).get("positions", {}).get("hero", "?")
        tocall = (state or {}).get("to_call", {}).get("to_call_bb")
        pot = (state or {}).get("pot", {}).get("pot_bb")
        preset = (plan or {}).get("preset")
        ts = time.strftime("%H:%M:%S")
        posflop = len(board) > 0
        fase = "POS" if posflop else "PRE"
        # TRAVA ABSOLUTA (LEI Eduardo): UMA tentativa por ação, JAMAIS re-clica a mesma. Marcada
        # ANTES de clicar -> se o clique NÃO pegou, ESQUECE e segue o jogo (não retenta). Só age de
        # novo na MESMA mão/rua se enfrentar aposta MAIOR (3bet/4bet real); flicker do to_call NÃO
        # re-dispara (mata o 'raise raise raise' e o mouse indo-e-voltando).
        hkey = (room, (state or {}).get("hand_id"))
        if hkey in folded:         # já FOLDOU esta mão -> nunca age de novo (nem check pós-flop)
            return
        akey = (room, (state or {}).get("hand_id"), (state or {}).get("street"))
        _tc = tocall if isinstance(tocall, (int, float)) else 0.0
        _last = acted.get(akey)
        if _last is not None and _tc <= _last + 1.0:
            print("%s %s %s mão=%s já agiu (to_call %.1f<=%.1f) -> IGNORA (1 tentativa só)"
                  % (_tag, ts, fase, (state or {}).get("hand_id"), _tc, _last), flush=True)
            return
        if act in (A.WAIT, A.ABSTAIN, None):
            print("%s %s %s pos=%s hero=%s board=%s -> %s (não age)" % (_tag, ts, fase, pos, hero, board, act), flush=True)
            return
        acted[akey] = _tc          # MARCA ANTES de clicar -> nunca re-clica a mesma ação
        # COLUNA-na-tela (0-based) da mesa + nº de mesas vivas. Calculado e LOGADO também no DRY:
        # é o que o Eduardo confere na validação multi-tela (sala->coluna vs a tela) ANTES de armar.
        ri = room_index_fn() if room_index_fn else 0
        nr = n_rooms_fn() if n_rooms_fn else 1
        allowed = control.execution_allowed() if control is not None else armed
        _label = "" if allowed else ("  [%s: não clica]" % (control.state if control is not None else "DRY"))
        print("%s %s >>> %s col=m%s/%s pos=%s hero=%s board=%s pot=%sbb to_call=%sbb CÉREBRO=%s PLANO=%s%s%s%s"
              % (_tag, ts, fase, ri, nr, pos, hero, board, pot, tocall, advice.get("recommended"), act,
                 (" %s" % plan.get("chips")) if plan.get("chips") is not None else "",
                 (" [%s]" % preset) if preset else "", _label), flush=True)
        if overlay is not None:                          # BADGE na tela: última ação por mesa
            try:
                overlay.set_table("mesa %s" % (room or "?"), "%s %s %s -> %s%s" % (
                    ts, fase, pos, (advice.get("recommended") or act),
                    (" %s" % plan.get("chips")) if plan.get("chips") is not None else ""))
            except Exception:
                pass
        if not allowed:                                  # PAUSADO/DESABILITADO/DRY: loga+mostra, NÃO clica
            return
        # CLIQUE DESACOPLADO (Eduardo 23/11): NÃO clica aqui — isto roda na THREAD DO CALLBACK do Frida;
        # clicar com sleeps BLOQUEIA a entrega de eventos -> backlog -> "mute"/sit-out (a causa real do
        # travamento). ENFILEIRA a ação p/ o worker de clique (1 por vez, sem conflito de cursor entre
        # mesas). A decisão/anti-thrash/log do CÉREBRO já saíram acima (síncronos, corretos). Sem fila
        # (teste/fallback) mantém o clique síncrono.
        if click_q is not None:
            click_q.put((time.time(), plan, hwnd, ri, nr, posflop, act, tocall, delay, _tag))
        else:
            think = _human_delay(posflop, act, tocall)
            if think > 0:
                time.sleep(think)
            res = C.execute(plan, hwnd, armed=True, step_delay=delay, room_index=ri, n_rooms=nr)
            stats["acoes"] += 1
            print("%s %s CLIQUE[m%s/%s]: %s" % (_tag, time.strftime("%H:%M:%S"), ri, nr, res), flush=True)

    return auto_emit


def _kill_other_agents():
    """ROTINA (LEI Eduardo 22/11): LIMPAR ANTES DE INICIAR. TaskStop/kill do launcher NÃO mata o
    filho python -> órfãos acumulam, TODOS hookados na Suprema, colidindo nos hooks SSL -> sit out.
    Na largada, o próprio agente mata as OUTRAS cópias de suprema_agente.py (nunca a si/pai) antes
    de hookar, garantindo hook ÚNICO. Roda no processo do agente (não no terminal) -> sem bloqueio."""
    try:
        import psutil
        me, pp = os.getpid(), os.getppid()
        killed = []
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if p.info['pid'] in (me, pp):
                    continue
                if (p.info.get('name') or '').lower() != 'python.exe':
                    continue
                if 'suprema_agente.py' in ' '.join(p.info.get('cmdline') or []):
                    p.kill()
                    killed.append(p.info['pid'])
            except Exception:
                pass
        if killed:
            import time as _t
            _t.sleep(1.0)      # deixa os hooks dos órfãos soltarem antes de hookar o novo
            print("[AG] limpeza de rotina: matei cópias órfãs %s (hook único garantido)" % killed, flush=True)
    except Exception:
        pass


def main():
    _kill_other_agents()          # LIMPAR ANTES DE INICIAR (rotina) — hook único
    ap = argparse.ArgumentParser()
    ap.add_argument("--armed", action="store_true", help="CLICA de verdade (sem isso = DRY, só salva H2N + loga)")
    ap.add_argument("--rebuy", action="store_true", help="liga o vigia de rebuy (Recompra simples se der tempo)")
    ap.add_argument("--bb", type=float, default=600.0, help="BB semente (o estado usa o BB exato do game_info)")
    ap.add_argument("--seconds", type=float, default=0.0, help="0 = roda até Ctrl+C")
    ap.add_argument("--mode", default="chip_ev")
    ap.add_argument("--stage", default="mid")
    ap.add_argument("--hunt-bounty", dest="hunt_bounty", action="store_true",
                    help="caça de bounty PKO AUTO: injeta a cabeça (base+acumulado, lida do stream) "
                         "por vilão no call-off (alvo bountiado curto coberto -> menos equity). Só em "
                         "--mode pko/pko_icm. Default off (validar ao vivo).")
    ap.add_argument("--head-fraction", dest="head_fraction", type=float, default=0.5,
                    help="fração do buy-in na cabeça: 0.5 PKO (default), 0.75 super-PKO.")
    ap.add_argument("--starting-stack", dest="starting_stack", type=float, default=None,
                    help="stack inicial em fichas (override; senão detecta no começo pelo avgStack).")
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--base", default=DEFAULT_BASE, help="pasta base dos .txt H2N")
    ap.add_argument("--tournament", default=None)
    ap.add_argument("--process", default="SupremaPoker.exe")
    ap.add_argument("--pid", type=int, default=None,
                    help="PID do cliente Suprema ESPECÍFICO (MULTI-INSTÂNCIA: 2 contas = 2 agentes, um por "
                         "PID). Sem isso, anexa no maior SupremaPoker.exe (1 instância).")
    ap.add_argument("--hwnd", type=int, default=None,
                    help="HWND da janela do cliente (multi-instância: a janela DESTA conta). Sem isso, "
                         "find_suprema_hwnd escolhe a janela da Suprema.")
    ap.add_argument("--hud-dir", dest="hud_dir", default=None,
                    help="pasta _live p/ a HUD overlay: snapshot por assento, 1 arquivo por SALA "
                         "(table_id=sala). Sem isto NÃO alimenta a HUD (usado quando o launcher sobe o agente).")
    ap.add_argument("--dump-raw", dest="dump_raw", default=None,
                    help="espelha TODOS os eventos crus num .jsonl (evidência durável; paridade c/ o capturador).")
    ap.add_argument("--no-guardiao", dest="guardiao", action="store_false",
                    help="NÃO sobe o guardião de quedas. Default: LIGADO (alarme de crash da Suprema, "
                         "a MESMA regra do PPPoker — pedido do Eduardo 23/11).")
    ap.add_argument("--no-overlay", dest="overlay", action="store_false",
                    help="NÃO mostra o badge de estado na tela. Default: LIGADO (padrão do executável — "
                         "ARMADO/PAUSADO/DESABILITADO sempre-no-topo).")
    ap.add_argument("--no-hotkeys", dest="hotkeys", action="store_false",
                    help="NÃO liga os atalhos globais. Default: LIGADO (Ctrl+Alt+R arma / P pausa / D off "
                         "— você assume as mesas a qualquer hora).")
    ap.add_argument("--no-sitout-guard", dest="sitout_guard", action="store_false",
                    help="DESLIGA o anti-sit-out. Default LIGADO: detecta sit-out por OCR do texto do "
                         "botão 'Estou de volta' (NÃO por cor — cor dava falso-positivo nos botões de "
                         "ação verdes, Eduardo 23/11) e clica Voltar só quando RUNNING.")
    ap.add_argument("--no-bust-guard", dest="bust_guard", action="store_false",
                    help="DESLIGA o vigia de bust. Default LIGADO: detecta o pop-up de CLASSIFICAÇÃO "
                         "(caiu do torneio) por OCR do título + cor dos botões, e clica SAIR (fecha a "
                         "mesa) só quando RUNNING — calibrado no print real 23/11.")
    ap.add_argument("--stop-file", dest="stop_file",
                    default=os.path.join(_HERE, "logs", "suprema_stop.flag"),
                    help="arquivo-gatilho de PARADA LIMPA: ao aparecer, o agente faz unload+detach do "
                         "Frida e sai (sem hook pendurado -> pode relançar SEM fechar a Suprema).")
    args = ap.parse_args()
    if not args.tournament:
        args.tournament = "suprema_%s" % datetime.now().strftime("%Y-%m-%d")

    C.set_dpi_aware()

    # Encerramento LIMPO quando o launcher manda CTRL_BREAK (o agente sobe em grupo próprio): vira
    # KeyboardInterrupt -> propaga pelo run_live -> o finally faz unload+detach do Frida (sem hook
    # pendurado = sem sit out). Só Windows (SIGBREAK); Ctrl+C (SIGINT) segue igual.
    def _raise_kbint(*_a):
        raise KeyboardInterrupt
    _brk = getattr(signal, "SIGBREAK", None)
    if _brk is not None:
        try:
            signal.signal(_brk, _raise_kbint)
        except Exception:
            pass

    hwnd = args.hwnd if args.hwnd else find_suprema_hwnd(args.process)   # multi-instância: hwnd DESTA conta
    if not hwnd:
        print("[AG] janela da Suprema não encontrada.", flush=True)
        return 1
    left, top, w, h = C.client_rect_screen(hwnd)
    print("[AG] hwnd=%s client=%dx%d @ (%d,%d) calibrado=%s" % (hwnd, w, h, left, top, C._CALIBRATED), flush=True)

    # PLANO DE CONTROLE + BADGE NA TELA (padrão do executável, idêntico ao operar_mesa do PPPoker):
    # BotControl (RUNNING/PAUSED/DISABLED; default PAUSED=seguro) + StatusOverlay (faixa sempre-no-topo
    # ARMADO/PAUSADO/DESABILITADO) + HotkeyListener (Ctrl+Alt+R arma / P pausa / D off -> você assume as
    # mesas a qualquer hora, o clique é gated por execution_allowed()). --armed começa ARMADO (RUNNING).
    overlay = StatusOverlay(title="NVT Henrique — Suprema").start() if args.overlay else None

    def _clean_stop(reason):
        # PARADA LIMPA: interrompe a main thread -> KeyboardInterrupt -> o finally do run_live faz
        # unload+detach do Frida. SEM hook pendurado -> dá pra RELANÇAR sem fechar a Suprema (resolve
        # o "por que toda vez tem que fechar a Suprema": o restart era remendo de parada suja).
        print("[AG] parada LIMPA (%s) -> unload+detach do Frida." % reason, flush=True)
        if overlay:
            try:
                overlay.note("parando — detach limpo do Frida…")
            except Exception:
                pass
        _thread.interrupt_main()

    def _on_change(s):
        print("\n>>> HENRIQUE %s <<<\n" % s, flush=True)
        if overlay:
            overlay.set_state(s)
        if s == DISABLED:                 # Ctrl+Alt+D = kill-switch LIMPO (detach, nunca hard-kill)
            _clean_stop("Ctrl+Alt+D (DESABILITADO)")
    control = BotControl(on_change=_on_change)
    if overlay:
        overlay.set_state(control.state)
        overlay.note("Ctrl+Alt+R arma   Ctrl+Alt+P pausa   Ctrl+Alt+D desliga")
    if args.armed:
        control.resume()     # PAUSED -> RUNNING: começa ARMADO (regra Eduardo: teste ao vivo é clicando)
    listener = HotkeyListener(control) if args.hotkeys else None
    if listener:
        listener.start()

    # H2N + DECISÃO + CLIQUE por MESA (MULTI-MESA): SupremaRouter roteia por roomID -> 1 estado,
    # 1 cérebro e 1 builder POR SALA; o clique vai na COLUNA certa (room_index/n_rooms). 1 mesa =
    # idêntico ao de antes (n_rooms=1).
    sink = HandTextSink(base=args.base)
    save = SaveStats()
    tour_id = "".join(ch for ch in args.tournament if ch.isdigit()) or datetime.now().strftime("%Y%m%d")
    from assistir_suprema import load_advisor, make_on_state
    import suprema_multi
    advisor = load_advisor()
    stats = {"acoes": 0}
    router = suprema_multi.SupremaRouter(bb_chips=args.bb)
    # Ordem roomID->COLUNA estável (append-only por 1ª aparição) + contagem de mesas VIVAS (poda
    # bustadas por staleness relativa). NÃO re-ordena (o sorted() antigo embaralhava colunas vivas
    # a cada mesa nova) e NÃO infla n_rooms com mesas que já bustaram. Não há sinal de posição no
    # protocolo (varredura do dump) -> ordem de 1ª aparição; L/R real a validar DRY ao vivo.
    order = suprema_multi.RoomOrder()
    import suprema_tile_binder
    # roomID -> COLUNA por VISÃO (OCR do ID no feltro de cada tile): ANCORA na realidade, não no
    # palpite de ordem de 1ª aparição (que clicava na mesa espelhada ao vivo). 1 mesa = atalho sem OCR.
    binder = suprema_tile_binder.TileBinder(hwnd)
    _ctx = {}                         # room -> {builder, on_state, acc, emit_hud}
    _last_evt = [time.time()]         # watchdog de HOOK MUDO: carimba cada evento recebido

    raw_fp = None
    if args.dump_raw:                 # evidência crua durável (paridade c/ o capturador)
        os.makedirs(os.path.dirname(os.path.abspath(args.dump_raw)) or ".", exist_ok=True)
        raw_fp = open(args.dump_raw, "a", encoding="utf-8")

    def _n_rooms():
        return binder.n_cols or order.n_rooms()

    def _room_index(room):
        binder.ensure(order.live_rooms())      # re-liga só se a grade mudou (cacheado; 1 mesa = atalho)
        col = binder.column_of(room)
        if col is not None:
            return col
        print("[AG] binder SEM mapa p/ sala %s (OCR do ID falhou?) -> fallback ordem de aparição"
              % room, flush=True)
        return order.index(room)

    def _ctx_for(room):
        c = _ctx.get(room)
        if c is None:
            acc = HandAccumulator(room="SupremaPoker", tournament_id=tour_id,
                                  table_tag="%s_%s" % (args.tournament, room), max_seats=9,
                                  sink=sink, on_hand=save.on_hand)
            emit = make_auto_emit(hwnd, armed=args.armed, delay=args.delay, stats=stats, room=room,
                                  room_index_fn=(lambda r=room: _room_index(r)), n_rooms_fn=_n_rooms,
                                  control=control, overlay=overlay, click_q=_click_q)
            emit_hud = None
            if args.hud_dir:          # 1 snapshot por SALA (table_id=sala) -> a HUD overlay desenha cada mesa
                try:
                    from suprema_live_emit import SupremaLiveEmitter
                    emit_hud = SupremaLiveEmitter(args.hud_dir, table_id=room)
                except Exception:
                    emit_hud = None
            c = {"acc": acc, "builder": SupremaHandBuilder(acc), "emit_hud": emit_hud,
                 "on_state": make_on_state(advisor, mode=args.mode, stage=args.stage, emit=emit,
                                           hunt_bounty=args.hunt_bounty, head_fraction=args.head_fraction,
                                           starting_stack=args.starting_stack)}
            _ctx[room] = c
        return c

    def on_message(msg):
        _last_evt[0] = time.time()                       # hook VIVO (qualquer evento de jogo recebido)
        room = suprema_multi.room_of(msg)
        if room is None:
            return
        if raw_fp is not None:                           # evidência crua durável (paridade capturador)
            try:
                raw_fp.write(json.dumps({"ts": time.time(), "msg": msg}, ensure_ascii=False) + "\n")
                raw_fp.flush()
            except Exception:
                pass
        order.touch(room, suprema_multi.event_ts(msg))   # ordem estável + liveness (poda bustadas)
        c = _ctx_for(room)
        try:
            c["builder"].feed(msg)
        except Exception:
            pass
        router.feed_json(msg)
        t = router.table(room)
        if t is not None:
            try:
                c["on_state"](t)
            except Exception:
                pass
            if c["emit_hud"] is not None:                # alimenta a HUD overlay (snapshot da sala)
                try:
                    c["emit_hud"](t)
                except Exception:
                    pass

    stop = threading.Event()

    # CLIQUE DESACOPLADO (Eduardo 23/11): fila + 1 thread worker que executa TODOS os cliques (de todas as
    # mesas), UMA ação por vez. Tira o clique da thread do callback do Frida -> a percepção nunca bloqueia
    # -> sem backlog/"mute"/sit-out. O auto_emit (no callback) só decide e ENFILEIRA. Ver _click_worker.
    _click_q = queue.Queue()
    threading.Thread(target=_click_worker, args=(_click_q, stats, stop), daemon=True).start()

    # PARADA LIMPA por ARQUIVO-GATILHO: quem quiser parar o agente só cria `args.stop_file` (ex.: eu,
    # do terminal: `touch logs/suprema_stop.flag`). O watcher remove o arquivo e dispara o _clean_stop
    # (unload+detach). Substitui o hard-kill (TaskStop) que deixava o hook pendurado e exigia reabrir a
    # Suprema. Se o arquivo já existe de uma sessão anterior, limpa na largada p/ não parar na hora.
    try:
        if os.path.exists(args.stop_file):
            os.remove(args.stop_file)
    except Exception:
        pass

    def _stop_file_watcher():
        while not stop.wait(1.0):
            try:
                if os.path.exists(args.stop_file):
                    try:
                        os.remove(args.stop_file)
                    except Exception:
                        pass
                    _clean_stop("stop-file")
                    return
            except Exception:
                pass
    threading.Thread(target=_stop_file_watcher, daemon=True).start()

    if args.guardiao:
        # ALARME DE QUEDA (LEI Eduardo 23/11: a MESMA regra do PPPoker, agora na Suprema). O
        # guardiao.py já vigia SupremaPoker.exe (CLIENTS) — detecta crash/fechamento, registra a
        # assinatura WER e TOCA O ALARME sonoro. Sobe junto, em thread daemon, stand_down=False
        # (só avisa; não desanexa o nosso stack no meio do jogo). Ver [[nvt-guardiao-crashes]].
        try:
            import guardiao
            threading.Thread(target=guardiao.run, kwargs=dict(interval=2.0, stand_down=False),
                             daemon=True).start()
            print("[AG] guardião de quedas ATIVO — alarme de crash (PPPoker+Suprema).", flush=True)
        except Exception as e:
            print("[AG] guardião NÃO subiu (%s) — sigo sem alarme de crash." % e, flush=True)
    if args.rebuy:
        threading.Thread(target=_rebuy_loop, args=(hwnd, args.armed, args.seconds, stop), daemon=True).start()

    # WATCHDOG DE HOOK MUDO: se nenhum evento chega há >15s, o hook pode estar pendurado (religou com
    # a Suprema aberta = o bug recorrente). Em vez de ficar parado em silêncio, AVISA na tela (badge)
    # e no log; some quando os eventos voltam. Mata o mistério "não clica e não sei por quê".
    def _mute_watchdog():
        # 45s: lull normal entre mãos (herói espera) NÃO alarma; hook mudo de verdade = silêncio
        # permanente (passa de 45s). Evita falso-alarme a cada pausa.
        warned = False
        while not stop.wait(3.0):
            silence = time.time() - _last_evt[0]
            if silence > 45:
                # BREAK-AWARE (LEI Eduardo 23/11): silêncio na janela do intervalo (:55->:00, com folga
                # p/ o drift) é ESPERADO, NÃO é hook mudo. No break todas as mesas param juntas. Fora da
                # janela, silêncio longo = provável hook mudo real.
                _mnt = datetime.now().minute
                if _mnt >= 53 or _mnt <= 2:
                    m = "BREAK (intervalo ~:55->:00) — silêncio esperado, não é hook mudo"
                else:
                    m = "SEM DADOS há %ds — hook mudo? feche e reabra a Suprema" % int(silence)
                if overlay:
                    try: overlay.note("⚠ " + m)
                    except Exception: pass
                if not warned:
                    print("[AG] ⚠ %s" % m, flush=True)
                    warned = True
            elif warned:
                if overlay:
                    try: overlay.note("")
                    except Exception: pass
                warned = False
    threading.Thread(target=_mute_watchdog, daemon=True).start()

    # ANTI-SIT-OUT (LEI Eduardo 23/11): vigia a TELA (independente do hook); se o hero fica SIT-OUT,
    # clica "Estou de volta" p/ reentrar. Default LIGADO (--no-sitout-guard desliga). DETECÇÃO POR OCR
    # do TEXTO do botão ('volta' presente = sit-out), NÃO por cor — a 1ª versão por cor dava falso-
    # positivo nos botões de ação verdes (Pagar/Aumentar) e clicava antes da ação chegar. Validado nos
    # pixels reais (sit-out='Estou de volta'; sua vez='Desistir/Pagar...'). Ver suprema_sitout.
    if args.sitout_guard:
        try:
            import suprema_sitout
            threading.Thread(target=suprema_sitout.sitout_watch, args=(hwnd, control, stop),
                             kwargs=dict(seconds=args.seconds), daemon=True).start()
            print("[AG] anti-sit-out ATIVO (--sitout-guard).", flush=True)
        except Exception as e:
            print("[AG] anti-sit-out NÃO subiu (%s)." % e, flush=True)

    # VIGIA DE BUST (Eduardo 23/11): caiu do torneio -> pop-up CLASSIFICAÇÃO -> clica SAIR (fecha a
    # mesa). Independente do hook; calibrado no print real (título por OCR + botões por cor). Só age
    # ARMADO. Default LIGADO (--no-bust-guard desliga). Ver suprema_bust.
    if getattr(args, "bust_guard", True):
        try:
            import suprema_bust
            threading.Thread(target=suprema_bust.bust_watch, args=(hwnd, control, stop),
                             kwargs=dict(seconds=args.seconds), daemon=True).start()
            print("[AG] vigia de BUST ATIVO (--bust-guard).", flush=True)
        except Exception as e:
            print("[AG] vigia de bust NÃO subiu (%s)." % e, flush=True)

    print("[AG] AGENTE no ar MULTI-MESA (estado=%s). Salva H2N em %s %s%s" % (
        control.state, sink.base, "| rebuy ON" if args.rebuy else "", "" if _HAS_PARSER else " | (sem parser)"),
        flush=True)
    try:
        suprema_net.run_live(bb_chips=args.bb, on_message=on_message, on_state=None,
                             seconds=args.seconds, process=args.process, pid=args.pid)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for c in _ctx.values():
            try:
                c["acc"].on_hand_over()
            except Exception:
                pass
        if raw_fp is not None:
            try:
                raw_fp.close()
            except Exception:
                pass
        if listener is not None:
            try: listener.stop()
            except Exception: pass
        if overlay is not None:
            try: overlay.stop()
            except Exception: pass
    print("[AG] fim. ações=%d | salas(vivas)=%s | todas=%s | mãos H2N: %d OK, %d saldo!=0, %d falha | arquivos: %d"
          % (stats["acoes"], order.live_rooms(), order.all_rooms(),
             save.ok, save.unbalanced, save.bad, len(sink.written)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
