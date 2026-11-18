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

    # 1) OPERADOR: armado automaticamente, exploit do HUD ligado, fecha bustada.
    op = subprocess.Popen(
        [sys.executable, "operar_mesa.py", "--hwnd", str(hwnd),
         "--arm", "--auto-arm", "--auto-fechar-bustada", "--hud", "--field-exploit"],
        cwd=REPO, creationflags=new_console)
    procs.append(("OPERADOR", op))
    print("[ok] OPERADOR no ar: ARMADO + exploit(HUD) + auto-fechar-bustada (janela propria).")

    # 2) CAPTURA de maos (read-only) — alimenta a DB no padrao Hand2Note.
    cap = subprocess.Popen(
        [sys.executable, "-I", "capturar_maos.py"],
        cwd=os.path.join(REPO, "research", "ppp_il2cpp"), creationflags=new_console)
    procs.append(("CAPTURA", cap))
    print("[ok] CAPTURA de maos no ar (salva em logs/maos_h2n). (janela propria).")

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
