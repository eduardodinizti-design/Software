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


def main(argv=None):
    opts = _parse_args(argv if argv is not None else sys.argv[1:])
    print("=" * 62)
    print("   NVT BOT  —  launcher COMPLETO (tudo plugado)")
    print("=" * 62)
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

    def _spawn(sub, script, cwd, extra):
        if frozen:
            cmd = [sys.executable, sub] + extra
            cwd = REPO
        else:
            flags = ["-I"] if sub in ("emitir", "capturar", "alerta") else []
            cmd = [sys.executable] + flags + [script] + extra
        return subprocess.Popen(cmd, cwd=cwd, creationflags=new_console)

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
        for n, p in procs:
            try:
                p.terminate()
            except Exception:                    # noqa: BLE001
                pass


if __name__ == "__main__":
    main()
