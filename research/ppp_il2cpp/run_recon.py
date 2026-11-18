"""run_recon.py — anexa o Frida ao PPPoker.exe e roda o recon READ-ONLY.

Pré-requisitos: PPPoker aberto; `pip install frida` (já instalado: frida 17.x).
NÃO altera nada no jogo — só lê metadata IL2CPP e imprime as classes/métodos de
janela/mesa/tiling. Saída vai para o console e para recon_out.txt (ao lado).

    python run_recon.py            # anexa no PPPoker.exe já aberto

Ponto de parada: Ctrl+C. Se o anti-cheat for uma preocupação, lembre que
ATTACH do Frida já instrumenta o processo (é a parte "invasiva"); rode só quando
estiver confortável com isso (ver README.md).
"""
import sys, os, threading

try:
    import frida
except ImportError:
    sys.exit("frida nao instalado:  pip install frida")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "recon.js")
OUT = os.path.join(HERE, "recon_out.txt")
TARGET = "PPPoker.exe"

lines = []
done = threading.Event()

def on_message(msg, data):
    if msg.get("type") == "send":
        if msg.get("payload") == "__RECON_DONE__":
            done.set()
        else:
            print(msg["payload"])
    elif msg.get("type") == "error":
        print("[frida-error]", msg.get("stack") or msg.get("description"))
        done.set()

def on_log(level, text):
    # console.log do JS chega aqui
    print(text)
    lines.append(text)

def main():
    try:
        session = frida.attach(TARGET)
    except frida.ProcessNotFoundError:
        sys.exit(f"{TARGET} nao encontrado — abra o PPPoker primeiro.")
    with open(SCRIPT, "r", encoding="utf-8") as f:
        code = f.read()
    script = session.create_script(code)
    script.on("message", on_message)
    script.set_log_handler(on_log)
    print(f"[run_recon] anexado a {TARGET}; coletando...")
    script.load()
    if not done.wait(120):
        print("[run_recon] timeout (120s) — coleta parcial.")
    try:
        session.detach()
    except Exception:
        pass
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[run_recon] salvo em {OUT} ({len(lines)} linhas)")

if __name__ == "__main__":
    main()
