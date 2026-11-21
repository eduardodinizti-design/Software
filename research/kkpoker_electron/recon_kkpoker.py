"""RECON do KKPoker (Electron = Chromium + Node) via CDP (Chrome DevTools Protocol) —
SEM Frida. Observa o WebSocket do jogo (a fonte das mãos) e permite explorar o renderer.

Electron só expõe o CDP se o app subir com --remote-debugging-port. Como o atalho normal
NÃO passa essa flag, use --launch p/ reabrir o KKPoker com a porta (feche o aberto antes).
Se as 'fuses' do Electron bloquearem o inspector, cair p/ Frida no renderer (ver FINDINGS).

Uso:
    python -I recon_kkpoker.py --launch               # abre o KKPoker com a porta e observa
    python -I recon_kkpoker.py --port 9222            # se já estiver aberto com a porta
    python -I recon_kkpoker.py --launch --exe "C:\\caminho\\KKPoker Global.exe"

READ-ONLY: só habilita domínios de observação (Network/Runtime) e escuta; não injeta ação.
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_EXE_CANDIDATES = [
    r"C:\Program Files\KKPoker\KKPoker Global.exe",
    r"C:\Program Files (x86)\KKPoker\KKPoker Global.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\KKPoker\KKPoker Global.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\kkpoker\KKPoker.exe"),
]


def find_exe(explicit=None):
    if explicit and os.path.exists(explicit):
        return explicit
    for p in _EXE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def launch(exe, port):
    print(f"[kk] abrindo {exe} com --remote-debugging-port={port}", flush=True)
    # porta só escuta em 127.0.0.1 por padrão; nada é exposto externamente
    subprocess.Popen([exe, f"--remote-debugging-port={port}", "--remote-allow-origins=*"],
                     close_fds=True)


def fetch_targets(port, tries=30):
    """Espera o endpoint CDP subir e devolve os alvos (páginas do renderer)."""
    url = f"http://127.0.0.1:{port}/json/list"
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            time.sleep(1.0)
    return []


async def monitor(target, quiet_binary=False):
    import websockets
    ws_url = target.get("webSocketDebuggerUrl")
    title = target.get("title", "")[:40]
    if not ws_url:
        return
    try:
        async with websockets.connect(ws_url, max_size=None, ping_interval=None) as ws:
            mid = {"n": 0}

            async def call(method, params=None):
                mid["n"] += 1
                await ws.send(json.dumps({"id": mid["n"], "method": method, "params": params or {}}))

            await call("Network.enable")
            await call("Runtime.enable")
            await call("Page.enable")
            print(f"[kk] observando página '{title}' ({target.get('url','')[:60]})", flush=True)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                m = msg.get("method")
                p = msg.get("params", {})
                if m == "Network.webSocketCreated":
                    print(f"[kk][WS novo] {p.get('url','')[:90]}", flush=True)
                elif m in ("Network.webSocketFrameReceived", "Network.webSocketFrameSent"):
                    resp = p.get("response", {})
                    op = resp.get("opcode")
                    data = resp.get("payloadData", "")
                    arrow = "<=" if m.endswith("Received") else "=>"
                    kind = "bin" if op == 2 else "txt" if op == 1 else f"op{op}"
                    if op == 2 and quiet_binary:
                        print(f"[kk]{arrow} {kind} {len(data)}b", flush=True)
                    else:
                        print(f"[kk]{arrow} {kind} {str(data)[:220]}", flush=True)
    except Exception as e:
        print(f"[kk] página '{title}' encerrou: {type(e).__name__}: {e}", flush=True)


async def run(port, seconds, quiet_binary):
    targets = fetch_targets(port)
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        print("[kk] nenhum alvo CDP (página) encontrado. O app subiu com --remote-debugging-port? "
              "Se as fuses bloqueiam o inspector, use o caminho Frida (ver FINDINGS_KKPOKER.md).", flush=True)
        return
    print(f"[kk] {len(pages)} página(s) renderer. Entre numa MESA e jogue 1 mão.", flush=True)
    tasks = [asyncio.create_task(monitor(t, quiet_binary)) for t in pages]
    try:
        if seconds:
            await asyncio.wait(tasks, timeout=seconds)
        else:
            await asyncio.gather(*tasks)
    finally:
        for t in tasks:
            t.cancel()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--launch", action="store_true", help="reabre o KKPoker com a porta de debug")
    ap.add_argument("--exe", default=None, help="caminho do KKPoker (se --launch e não achar sozinho)")
    ap.add_argument("--seconds", type=float, default=0.0)
    ap.add_argument("--quiet-binary", action="store_true", help="não despeja o payload binário, só o tamanho")
    a = ap.parse_args()
    try:
        import websockets  # noqa: F401
    except Exception:
        print("[kk] falta a lib 'websockets' (pip install websockets)."); return 1
    if a.launch:
        exe = find_exe(a.exe)
        if not exe:
            print("[kk] não achei o KKPoker; passe --exe \"<caminho>\"."); return 1
        launch(exe, a.port)
    try:
        asyncio.run(run(a.port, a.seconds, a.quiet_binary))
    except KeyboardInterrupt:
        pass
    print("[kk] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
