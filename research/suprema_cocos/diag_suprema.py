"""DIAGNOSTICO read-only do canal de log da Suprema: por que o [[NVT]] nao chega.
Anexa, ready(), lista exports de log do libcocos2d (logExports), e testa se o eval roda
(seta um global e le de volta NAO da -- evalString so devolve int; usamos logExports +
hook de candidatos). Imprime TODOS os tipos de msg Frida (send/error/LOG do agente)."""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))


def _exports(script):
    return getattr(script, "exports_sync", None) or script.exports


def _on_message(m, _data):
    t = m.get("type")
    if t == "send":
        print("[send]", m.get("payload"), flush=True)
    elif t == "error":
        print("[js-erro]", m.get("stack") or m.get("description"), flush=True)
    elif t == "log":
        print("[agent-log]", m.get("level"), m.get("payload"), flush=True)
    else:
        print("[msg?]", m, flush=True)


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "supremapoker.exe"]
    if not procs:
        print("[diag] SupremaPoker.exe nao esta aberto."); return 1
    pid = procs[0].pid
    session = dev.attach(pid)
    with open(os.path.join(_HERE, "suprema_capture_agent.js"), encoding="utf-8") as fh:
        script = session.create_script(fh.read())
    script.on("message", _on_message)
    script.load()
    exp = _exports(script)
    print("[diag] ready =", exp.ready(), flush=True)

    # 1) quais exports de log existem no libcocos2d?
    try:
        le = exp.log_exports()
        print("[diag] logExports (%d):" % len(le), flush=True)
        for e in le:
            print("    ", e.get("name"), e.get("addr"), flush=True)
    except Exception as e:
        print("[diag] logExports erro:", e, flush=True)

    # 2) o eval roda? injeta JS que escreve por VARIOS canais nativos (OutputDebugString +
    #    fputs/printf) marcado [[NVT]] -- vemos qual chega.
    probe = r"""
    (function(){
      var TAG='[[NVT]]';
      var msg = TAG + JSON.stringify({probe:'eval-ok', hasConsole: (typeof console!=='undefined'),
                                      hasCC: (typeof cc!=='undefined'), hasSpp:(typeof spp!=='undefined'),
                                      hasWS:(typeof WebSocket!=='undefined'), hasJsb:(typeof jsb!=='undefined')});
      try{ console.log(msg); }catch(e){}
      try{ if(typeof cc!=='undefined' && cc.log) cc.log(msg); }catch(e){}
      try{ if(typeof jsb!=='undefined' && jsb.console && jsb.console.log) jsb.console.log(msg); }catch(e){}
      return 1;
    })();
    """
    try:
        r = exp.eval_string(probe)
        print("[diag] eval_string(probe) ret =", r, flush=True)
    except Exception as e:
        print("[diag] eval_string erro:", e, flush=True)

    # 3) janela curta p/ qualquer saida chegar
    t0 = time.time()
    while time.time() - t0 < 8:
        time.sleep(0.3)

    try:
        script.unload()
    except Exception:
        pass
    try:
        session.detach()
    except Exception:
        pass
    print("[diag] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
