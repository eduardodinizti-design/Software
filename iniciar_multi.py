"""LAUNCHER ÚNICO MULTI-PLATAFORMA (Eduardo 24/11): sobe Suprema E PPPoker AO MESMO TEMPO, cada um no seu
pipeline, sobre o CÉREBRO COMUM. O ÁRBITRO DE CLIQUE (click_arbiter — lock GLOBAL do cursor) já está
plugado nos dois executores (suprema_agente._click_worker e action_executor), então os cliques das duas
plataformas se SERIALIZAM: só uma clica por vez, a outra espera (ou pula) -> não brigam pelo cursor físico.

Detecta quais salas estão ABERTAS e sobe só essas (clicou-abriu). Hooks em processos DIFERENTES
(SupremaPoker.exe x PPPoker) -> sem conflito de Frida.

    python iniciar_multi.py                         # auto-detecta e sobe as salas abertas (ARMADO)
    python iniciar_multi.py --mode icm --stage bubble   # mesmo, com ICM na bolha

Suprema -> suprema_agente.py (1 hook SSL_read: decide+clica+salva H2N).
PPPoker -> iniciar_bot.py   (protobuf + operador + emissor + captura).
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = 0x08000000


def _suprema_open():
    try:
        import suprema_operar
        return bool(suprema_operar.find_suprema_hwnd())
    except Exception:
        return False


def _pppoker_open():
    try:
        import iniciar_bot
        return bool(iniciar_bot.discover_hwnd())
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default=None, choices=(None, 'chip_ev', 'icm', 'pko', 'pko_icm'))
    ap.add_argument('--stage', default=None, choices=(None, 'pre_itm', 'bubble', 'ft', 'mid'))
    ap.add_argument('--only', choices=('suprema', 'pppoker'), default=None,
                    help='sobe só uma plataforma (default: as duas que estiverem abertas)')
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    py = sys.executable
    frozen = getattr(sys, 'frozen', False)   # .exe (PyInstaller) -> re-invoca por SUBCOMANDO; fonte -> .py
    logdir = os.path.join(REPO, 'logs')
    os.makedirs(logdir, exist_ok=True)
    procs = []

    def spawn(name, cmd):
        lf = open(os.path.join(logdir, 'multi_%s.log' % name), 'a', encoding='utf-8', errors='replace')
        p = subprocess.Popen(cmd, cwd=REPO, stdout=lf, stderr=subprocess.STDOUT, creationflags=NO_WINDOW,
                             env=dict(os.environ, NVT_PARENT_PID=str(os.getpid())))
        procs.append((name, p))
        print('[MULTI] subiu %s (pid %s) -> logs/multi_%s.log' % (name, p.pid, name), flush=True)

    sup = args.only in (None, 'suprema') and _suprema_open()
    ppp = args.only in (None, 'pppoker') and _pppoker_open()
    print('[MULTI] detecção: Suprema=%s  PPPoker=%s' % (
        'ABERTA' if sup else 'não', 'ABERTO' if ppp else 'não'), flush=True)
    if not (sup or ppp):
        print('[MULTI] nenhuma sala aberta. Abra a Suprema e/ou o PPPoker (com a mesa) e rode de novo.',
              flush=True)
        return

    if sup:
        base = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'NvtTracker', 'live')
        os.makedirs(os.path.join(base, '_live_suprema'), exist_ok=True)
        raw = os.path.join(REPO, 'logs', 'suprema_raw')
        os.makedirs(raw, exist_ok=True)
        d = datetime.now().strftime('%Y-%m-%d')
        head = [py, 'suprema-agente'] if frozen else [py, '-I', '-u', 'suprema_agente.py']
        cmd = head + ['--base', base, '--hud-dir', os.path.join(base, '_live_suprema'),
                      '--tournament', 'suprema_%s' % d,
                      '--dump-raw', os.path.join(raw, 'suprema_%s.jsonl' % d), '--armed']
        if args.mode:
            cmd += ['--mode', args.mode]
        if args.stage:
            cmd += ['--stage', args.stage]
        spawn('suprema', cmd)

    if ppp:
        head = [py, 'iniciar'] if frozen else [py, '-u', 'iniciar_bot.py']
        cmd = head + ['--no-painel']
        if args.mode:
            cmd += ['--mode', args.mode]
        if args.stage:
            cmd += ['--stage', args.stage]
        spawn('pppoker', cmd)

    print('[MULTI] ÁRBITRO DE CLIQUE ativo: o cursor é SERIALIZADO entre Suprema e PPPoker.', flush=True)
    print('[MULTI] rodando. Ctrl+C aqui encerra os dois.', flush=True)
    try:
        while any(p.poll() is None for _, p in procs):
            time.sleep(2)
    except KeyboardInterrupt:
        print('[MULTI] Ctrl+C -> encerrando as plataformas...', flush=True)
    finally:
        for name, p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        print('[MULTI] encerrado.', flush=True)


if __name__ == '__main__':
    main()
