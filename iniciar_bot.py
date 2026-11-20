"""LAUNCHER UNICO do bot NVT — "clicou, rodou". Acha o PPPoker e sobe ABSOLUTAMENTE
TUDO que o sistema oferece, cada um na SUA janela (lei do Eduardo 19/11: nada pode
ficar de fora do launcher — "tudo que o sistema oferece tem que estar plugado").

Sobe 5 componentes:
  1) OPERADOR armado (auto-arm) com TODAS as capacidades ligadas: percepcao PROTOBUF
     (pre-flop exato), exploit do field (--hud), POS-FLOP (joga tudo: bet/raise/call
     com size no nosso slider + Plano Geometrico), fecha mesa bustada, faixa de status
     (--overlay), antecipacao de latencia (--antecipar), re-descoberta de mesas
     (--rediscover). PKO: passa o --bounty-bb (informado ao subir ou via arg).
  2) CAPTURADOR de maos (read-only, padrao Hand2Note p/ a DB).
  3) EMISSOR de assentos (seat->uid+nick via protobuf -> exploit da nossa DB).
  4) ALARME SONORO (MESA FINAL + BOLHA + DEAL) na propria janela (ENTER silencia).
  5) PAINEL de KPIs (central de gestao / desempenho) na propria janela.

Feche esta janela (ou Ctrl+C) para PARAR TUDO.

Mode/stage sao AUTO-detectados (chip_ev/icm/pko/pko_icm + fase); da p/ FORCAR com
--mode/--stage se quiser num teste. O bounty (PKO) e AUTO-LIDO pelo operador (emissor
-> logs/mtt_bounty.json); --bounty-bb N e so OVERRIDE manual.
"""
import argparse
import os
import sys
import time
import subprocess

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)


def _cleanup_stale():
    """LIMPA processos de bot ÓRFÃOS (emissor/operador/captura/alarme/painel de launches
    anteriores) ANTES de subir — evita EMISSOR DUPLICADO (Eduardo 19/11: "quando o bot cair
    de todas as mesas tem que limpar o emissor pra não duplicar"). Só os NOSSOS scripts;
    nunca o PPPoker nem este processo. Idempotente: todo launch começa limpo."""
    me = os.getpid()
    scripts = ('emitir_seats', 'operar_mesa', 'capturar_maos', 'alerta_ft', 'painel.py')
    killed = []
    try:
        import psutil
    except Exception:                            # noqa: BLE001
        psutil = None
    if psutil is not None:
        import signal
        brk = getattr(signal, "CTRL_BREAK_EVENT", None)
        frida_scripts = ('emitir_seats', 'capturar_maos')   # hosts Frida: desanexar LIMPO
        for p in list(psutil.process_iter(['pid', 'cmdline'])):
            try:
                if p.info['pid'] == me:
                    continue
                cmd = ' '.join(p.info.get('cmdline') or [])
                if not (cmd and any(s in cmd for s in scripts)):
                    continue
                if any(s in cmd for s in frida_scripts) and brk is not None:
                    # órfão Frida: pede desanexar limpo (evita fatal error se já há PPPoker)
                    try:
                        os.kill(p.info['pid'], brk)
                    except Exception:            # noqa: BLE001
                        p.terminate()
                else:
                    p.terminate()
                killed.append(p.info['pid'])
            except Exception:                    # noqa: BLE001
                continue
        if killed:
            time.sleep(2.0)                      # tempo p/ unload()+detach() dos hosts Frida
            for pid in killed:
                try:
                    psutil.Process(pid).kill()   # sobreviventes: força
                except Exception:                # noqa: BLE001
                    pass
    else:
        # Fallback Windows sem psutil: wmic acha PIDs por linha de comando e taskkill mata.
        for s in scripts:
            try:
                out = subprocess.check_output(
                    'wmic process where "commandline like \'%%%s%%\'" get processid' % s,
                    shell=True, stderr=subprocess.DEVNULL).decode('latin-1', 'replace')
                for tok in out.split():
                    if tok.strip().isdigit() and int(tok) != me:
                        subprocess.call('taskkill /PID %s /F' % tok, shell=True,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed.append(int(tok))
            except Exception:                    # noqa: BLE001
                continue
    if killed:
        print("[limpeza] %d processo(s) de bot orfaos encerrados (sem duplicar emissor): %s"
              % (len(killed), killed))
    else:
        print("[limpeza] nenhum processo de bot anterior (inicio limpo).")
    return killed


def discover_hwnd():
    try:
        from table_discovery.pppoker import pppoker_table_hwnds
        hs = pppoker_table_hwnds()
        return hs[0] if hs else None
    except Exception as e:                       # noqa: BLE001
        print("  (erro ao procurar o PPPoker: %s)" % e)
        return None


def _parse_args(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--bounty-bb', type=float, default=None,
                   help='PKO/KO: bounty medio em BB (calibra os call-offs). Sem isso, pergunta ao subir.')
    p.add_argument('--mode', choices=('chip_ev', 'icm', 'pko', 'pko_icm'), default=None,
                   help='FORCA o modo (default: auto-detecta pelo torneio).')
    p.add_argument('--stage', choices=('pre_itm', 'bubble', 'ft', 'mid'), default=None,
                   help='FORCA a fase (default: auto-detecta).')
    p.add_argument('--no-painel', dest='painel', action='store_false',
                   help='Nao sobe o painel de KPIs.')
    args, _ = p.parse_known_args(argv)
    return args


def _shutdown(procs):
    """Encerra TUDO sem derrubar o PPPoker (Eduardo 19/11: "fechar o bot dá fatal error").
    Hosts FRIDA (SEATS/CAPTURA) primeiro recebem CTRL_BREAK -> fazem script.unload()+detach()
    LIMPO; esperamos eles saírem; só então o resto (operador/alarme/painel) e quem não saiu
    levam terminate. Hard-kill de host Frida vivo = crash do PPPoker, então isso é evitado."""
    import signal
    brk = getattr(signal, "CTRL_BREAK_EVENT", None)
    frida_hosts = [(n, p) for n, p in procs if n in ("SEATS", "CAPTURA")]
    for n, p in frida_hosts:
        try:
            if p.poll() is None and brk is not None:
                p.send_signal(brk)          # -> SIGBREAK no filho -> unload+detach limpo
        except Exception:                    # noqa: BLE001
            try: p.terminate()
            except Exception: pass           # noqa: BLE001
    # espera os hosts Frida desanexarem sozinhos (até ~8s no total)
    deadline = time.time() + 8
    for n, p in frida_hosts:
        try:
            p.wait(timeout=max(0.2, deadline - time.time()))
        except Exception:                    # noqa: BLE001
            pass
    for n, p in frida_hosts:                  # não saiu no tempo: aí sim força (raro)
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:                    # noqa: BLE001
            pass
    for n, p in procs:                        # resto: encerra normal
        if (n, p) in frida_hosts:
            continue
        try:
            p.terminate()
        except Exception:                    # noqa: BLE001
            pass


def main(argv=None):
    opts = _parse_args(argv if argv is not None else sys.argv[1:])
    print("=" * 62)
    print("   NVT BOT  —  launcher COMPLETO (tudo plugado)")
    print("=" * 62)
    # LIMPEZA PRÉVIA (Eduardo 19/11): mata emissor/operador ÓRFÃOS antes de subir, pra
    # NUNCA duplicar o emissor (inclusive quando religa p/ um novo torneio provisionado).
    # Mata SÓ processos do bot; NUNCA o PPPoker.
    _cleanup_stale()
    hwnd = discover_hwnd()
    if not hwnd:
        print("\n[X] PPPoker nao encontrado. ABRA o PPPoker (com a mesa) e rode de novo.")
        try:
            input("\nEnter para sair...")
        except Exception:                        # noqa: BLE001
            pass
        return
    print("[ok] PPPoker encontrado (hwnd %s)." % hwnd)

    # Bounty (PKO): AUTO-LIDO pelo operador (emissor -> logs/mtt_bounty.json). O
    # --bounty-bb aqui é só OVERRIDE manual; sem ele, o bot coleta sozinho.
    bounty = opts.bounty_bb
    if bounty is not None:
        print("[ok] Bounty OVERRIDE manual = %.2f BB." % bounty)
    else:
        print("[ok] Bounty PKO: AUTO (operador le de logs/mtt_bounty.json, escrito pelo emissor).")

    new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    procs = []
    frozen = getattr(sys, "frozen", False)   # .exe (PyInstaller) vs fonte
    research = os.path.join(REPO, "research", "ppp_il2cpp")

    # Passa o PID do launcher p/ os filhos (watchdog de pai: se este processo morrer de
    # QUALQUER jeito — Ctrl+C, fechar janela, kill — os hosts Frida se desanexam LIMPOS).
    child_env = dict(os.environ, NVT_PARENT_PID=str(os.getpid()))
    new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    # Eduardo 20/11: NÃO poluir a tela com N janelas de cmd. Rodamos os filhos com janela
    # ESCONDIDA (CREATE_NO_WINDOW) e a saída vai pra logs/bot_<sub>.log (legível p/ auditoria
    # e p/ o Claude). O desligamento LIMPO do Frida NÃO depende mais do console/CTRL_BREAK:
    # o watchdog de pai (NVT_PARENT_PID, acima) desanexa quando este launcher morre.
    CREATE_NO_WINDOW = 0x08000000
    _logdir = os.path.join(REPO, "logs")
    try:
        os.makedirs(_logdir, exist_ok=True)
    except Exception:
        pass
    _logfiles = []

    def _spawn(sub, script, cwd, extra):
        cf = CREATE_NO_WINDOW                 # janela escondida (sem console visível)
        if sub in ("emitir", "capturar"):
            cf |= new_group                   # grupo próprio (watchdog de pai faz o detach limpo)
        if frozen:
            cmd = [sys.executable, sub] + extra
            cwd = REPO
        else:
            flags = ["-I"] if sub in ("emitir", "capturar", "alerta") else []
            cmd = [sys.executable] + flags + [script] + extra
        try:
            logf = open(os.path.join(_logdir, "bot_%s.log" % sub), "w",
                        encoding="utf-8", errors="replace")
            _logfiles.append(logf)            # mantém o handle vivo (não GC)
            return subprocess.Popen(cmd, cwd=cwd, creationflags=cf, env=child_env,
                                    stdout=logf, stderr=subprocess.STDOUT)
        except Exception:
            return subprocess.Popen(cmd, cwd=cwd, creationflags=cf, env=child_env)

    # 1) OPERADOR: TUDO ligado. Mode/stage auto (ou forcado). Bounty passado se informado.
    op_flags = ["--hwnd", str(hwnd), "--arm", "--auto-arm", "--auto-fechar-bustada",
                "--hud", "--field-exploit", "--posflop", "--protobuf",
                "--overlay", "--antecipar", "--rediscover"]
    if bounty is not None:
        op_flags += ["--bounty-bb", str(bounty)]
    if opts.mode:
        op_flags += ["--mode", opts.mode]
    if opts.stage:
        op_flags += ["--stage", opts.stage]
    op = _spawn("operar", "operar_mesa.py", REPO, op_flags)
    procs.append(("OPERADOR", op))
    print("[ok] OPERADOR no ar: ARMADO + protobuf + pos-flop + exploit(HUD) + overlay + "
          "antecipar + rediscover + auto-fechar-bustada%s."
          % (" + bounty" if bounty is not None else ""))

    # 2) CAPTURA de maos (read-only) — alimenta a DB no padrao Hand2Note.
    cap = _spawn("capturar", "capturar_maos.py", research, [])
    procs.append(("CAPTURA", cap))
    print("[ok] CAPTURA de maos no ar (logs/maos_h2n).")

    # 3) EMISSOR de assentos: seat->uid+nick (protobuf) -> logs/live_seats.json.
    emt = _spawn("emitir", "emitir_seats.py", research, [])
    procs.append(("SEATS", emt))
    print("[ok] EMISSOR de assentos no ar (seat->uid p/ exploit da DB).")

    # 4) ALARME SONORO: MESA FINAL + BOLHA + DEAL -> toca p/ voce ASSUMIR (ENTER silencia).
    al = _spawn("alerta", "alerta_ft.py", research, ["--bubble"])
    procs.append(("ALARME", al))
    print("[ok] ALARME SONORO no ar (FT/bolha/deal; ENTER na janela dele silencia).")

    # 5) PAINEL de KPIs (central de gestao / desempenho). Opcional via --no-painel.
    if opts.painel:
        pa = _spawn("painel", "painel.py", REPO, [])
        procs.append(("PAINEL", pa))
        print("[ok] PAINEL de KPIs no ar (desempenho/gestao).")

    print("\n>>> TUDO NO AR (%d componentes). Feche esta janela ou Ctrl+C para PARAR TUDO. <<<\n"
          % len(procs))
    try:
        while True:
            time.sleep(2)
            vivos = [n for n, p in procs if p.poll() is None]
            if not vivos:
                print("Todos os processos encerraram.")
                break
    except KeyboardInterrupt:
        print("\nParando tudo (Ctrl+C)...")
    finally:
        _shutdown(procs)


if __name__ == "__main__":
    main()
