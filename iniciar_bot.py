"""LAUNCHER UNICO do bot NVT — "clicou, rodou". Acha o PPPoker e sobe TUDO junto:
  1) OPERADOR armado (auto-arm, sem depender de hotkey) + EXPLOIT do field (--hud:
     le os stats do vilao na tela e o advisor explora no pos-flop) + fecha mesa
     bustada sozinho.
  2) CAPTURADOR de maos (read-only, salva no padrao Hand2Note p/ alimentar a DB).
Cada um abre na SUA janela. Feche esta janela (ou Ctrl+C) para PARAR TUDO.

Obs: o exploit hoje vem do HUD lido na tela. A ponte p/ nossa DB gigante
(exploit_db.json, ~389k maos, chaveada por ID) e o proximo upgrade (precisa o
tracker ler seat->ID via protobuf; este launcher ja sobe o tracker junto).
"""
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


def main():
    print("=" * 62)
    print("   NVT BOT  —  launcher completo (operador + exploit + maos)")
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

    new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    procs = []
    frozen = getattr(sys, "frozen", False)   # .exe (PyInstaller) vs fonte
    research = os.path.join(REPO, "research", "ppp_il2cpp")

    def _spawn(sub, script, cwd, extra):
        # No .exe: chama o proprio executavel como despachante (NVTBot.exe <sub> ...).
        # No fonte: python <script> (com -I p/ captura/emissor, como antes).
        if frozen:
            cmd = [sys.executable, sub] + extra
            cwd = REPO
        else:
            flags = ["-I"] if sub in ("emitir", "capturar") else []
            cmd = [sys.executable] + flags + [script] + extra
        return subprocess.Popen(cmd, cwd=cwd, creationflags=new_console)

    # 1) OPERADOR: armado automaticamente, exploit do HUD ligado, fecha bustada.
    op = _spawn("operar", "operar_mesa.py", REPO,
                ["--hwnd", str(hwnd), "--arm", "--auto-arm", "--auto-fechar-bustada",
                 "--hud", "--field-exploit", "--posflop"])
    procs.append(("OPERADOR", op))
    print("[ok] OPERADOR no ar: ARMADO + exploit(HUD) + auto-fechar-bustada (janela propria).")

    # 2) CAPTURA de maos (read-only) — alimenta a DB no padrao Hand2Note.
    cap = _spawn("capturar", "capturar_maos.py", research, [])
    procs.append(("CAPTURA", cap))
    print("[ok] CAPTURA de maos no ar (salva em logs/maos_h2n). (janela propria).")

    # 3) EMISSOR de assentos: le seat->uid+nick (protobuf) -> logs/live_seats.json
    #    (ponte p/ o exploit da NOSSA DB). Semeia ao ENTRAR/trocar de mesa.
    emt = _spawn("emitir", "emitir_seats.py", research, [])
    procs.append(("SEATS", emt))
    print("[ok] EMISSOR de assentos no ar (seat->uid p/ exploit da DB). (janela propria).")

    print("\n>>> TUDO NO AR. Feche esta janela ou aperte Ctrl+C para PARAR TUDO. <<<\n")
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
