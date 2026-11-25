"""LAUNCHER de 2+ CONTAS da Suprema (Eduardo 24/11): acha TODAS as instâncias do cliente (2 contas = 2
SupremaPoker.exe = 2 janelas) e sobe UM agente POR CONTA, cada um mirando seu --pid/--hwnd específicos.
O ÁRBITRO DE CLIQUE (click_arbiter) serializa o cursor físico entre os agentes -> não brigam pelo mouse.
Cada conta grava H2N/dump SEPARADO (base/c0, base/c1...). Só o 1º agente escuta hotkeys/overlay (os
extras sobem --no-hotkeys --no-overlay p/ não duplicar atalho global nem empilhar badges).

    python iniciar_suprema_duo.py [--mode icm --stage bubble]
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = 0x08000000


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default=None, choices=(None, 'chip_ev', 'icm', 'pko', 'pko_icm'))
    ap.add_argument('--stage', default=None, choices=(None, 'pre_itm', 'bubble', 'ft', 'mid'))
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    from suprema_operar import find_suprema_instances
    insts = find_suprema_instances()
    print('[DUO] instâncias Suprema: %d -> %s' % (len(insts), insts), flush=True)
    if not insts:
        print('[DUO] nenhuma Suprema aberta. Abra as contas (1 janela por conta) e rode de novo.', flush=True)
        return

    py = sys.executable
    frozen = getattr(sys, 'frozen', False)
    liveroot = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'NvtTracker', 'live')
    rawdir = os.path.join(REPO, 'logs', 'suprema_raw')
    logdir = os.path.join(REPO, 'logs')
    os.makedirs(rawdir, exist_ok=True)
    os.makedirs(logdir, exist_ok=True)
    d = datetime.now().strftime('%Y-%m-%d')
    procs = []

    for i, (pid, hwnd) in enumerate(insts):
        base = os.path.join(liveroot, 'c%d' % i)
        hud = os.path.join(base, '_live_suprema')
        os.makedirs(hud, exist_ok=True)
        head = [py, 'suprema-agente'] if frozen else [py, '-I', '-u', 'suprema_agente.py']
        cmd = head + ['--pid', str(pid), '--hwnd', str(hwnd), '--base', base, '--hud-dir', hud,
                      '--tournament', 'suprema_c%d_%s' % (i, d),
                      '--dump-raw', os.path.join(rawdir, 'suprema_c%d_%s.jsonl' % (i, d)),
                      '--stop-file', os.path.join(logdir, 'suprema_stop_c%d.flag' % i), '--armed']
        if i > 0:                                   # extras: sem hotkeys/overlay (evita atalho duplo + badges)
            cmd += ['--no-hotkeys', '--no-overlay']
        if args.mode:
            cmd += ['--mode', args.mode]
        if args.stage:
            cmd += ['--stage', args.stage]
        lf = open(os.path.join(logdir, 'suprema_c%d.log' % i), 'a', encoding='utf-8', errors='replace')
        p = subprocess.Popen(cmd, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT, creationflags=NO_WINDOW,
                             env=dict(os.environ, NVT_PARENT_PID=str(os.getpid())))
        procs.append(('c%d(pid %s)' % (i, pid), p))
        print('[DUO] subiu conta %d: pid=%s hwnd=%s -> logs/suprema_c%d.log' % (i, pid, hwnd, i), flush=True)

    print('[DUO] ÁRBITRO DE CLIQUE serializa o cursor entre as %d conta(s). Ctrl+C encerra todas.'
          % len(procs), flush=True)
    try:
        while any(p.poll() is None for _, p in procs):
            time.sleep(2)
    except KeyboardInterrupt:
        print('[DUO] Ctrl+C -> encerrando...', flush=True)
    finally:
        for name, p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        print('[DUO] encerrado.', flush=True)


if __name__ == '__main__':
    main()
