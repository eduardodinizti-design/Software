"""run_actions.py — carrega actions.js no PPPoker.

    python run_actions.py           # DRY-RUN: só resolve FloatingWindowFrameManager
                                    # e confirma os métodos. NAO organiza nada.
    python run_actions.py --tile    # idem, e dispara TileTableWindows() UMA vez
                                    # (organiza as mesas em grade, na main thread).

Requer PPPoker aberto COM 2+ mesas. Continua sendo injeção (frida.attach) —
rode só em conta de teste/play money.
"""
import sys, os, threading, time

try:
    import frida
except ImportError:
    sys.exit("frida nao instalado:  pip install frida")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "actions.js")
TARGET = "PPPoker.exe"
DO_TILE = "--tile" in sys.argv

ready = threading.Event()

def on_message(msg, data):
    if msg.get("type") == "send":
        if msg.get("payload") == "__ACTIONS_READY__":
            ready.set()
        else:
            print(msg["payload"])
    elif msg.get("type") == "error":
        print("[frida-error]", msg.get("stack") or msg.get("description"))
        ready.set()

def on_log(level, text):
    print(text)

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
    print(f"[run_actions] anexando a {TARGET} ({'TILE' if DO_TILE else 'DRY-RUN'})...")
    script.load()
    ready.wait(30)
    if DO_TILE:
        print("[run_actions] disparando TileTableWindows()...")
        script.post({"type": "tile"})
        time.sleep(2)   # deixa o próximo frame executar
    else:
        print("[run_actions] DRY-RUN concluído (nada foi alterado). Use --tile p/ organizar.")
    try:
        session.detach()
    except Exception:
        pass

if __name__ == "__main__":
    main()
