"""DIAG3 Suprema (read-only): confirma o CANAL de log = cocos2d::log e testa o eval JS.
Hooka ?log@cocos2d@@YAXPBDZZ (sink real do cc.log/console.log) e, via o capture agent,
roda um probe JS que console.log(['[[NVT]]'+globals]). Se surgir -> canal achado + sabemos
se spp/cc/WebSocket existem no contexto JS. Nenhuma acao no jogo."""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))

LOGHOOK = r"""
'use strict';
const COCOS = 'libcocos2d.dll';
const mod = Process.getModuleByName(COCOS);
const addr = mod.findExportByName('?log@cocos2d@@YAXPBDZZ');   // cocos2d::log(const char*, ...)
if (!addr) { send({loghook:'nao achou cocos2d::log'}); }
else {
  Interceptor.attach(addr, { onEnter(args){ try { const s = args[0].readCString(); if (s) send({cclog: s.length>400? s.slice(0,400): s}); } catch(e){} } });
  send({loghook:'hookado @ '+addr});
}
"""


def _on_message(m, _data):
    if m.get("type") == "send":
        p = m.get("payload") or {}
        if "cclog" in p:
            print("[cocos2d::log]", p["cclog"], flush=True)
        else:
            print("[send]", p, flush=True)
    elif m.get("type") == "error":
        print("[js-erro]", m.get("stack") or m.get("description"), flush=True)
    elif m.get("type") == "log":
        print("[agent-log]", m.get("payload"), flush=True)


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "supremapoker.exe"]
    if not procs:
        print("[diag3] SupremaPoker.exe nao aberto."); return 1
    session = dev.attach(procs[0].pid)

    # 1) hook do canal de log
    s_log = session.create_script(LOGHOOK)
    s_log.on("message", _on_message)
    s_log.load()

    # 2) capture agent (eval no main thread)
    with open(os.path.join(_HERE, "suprema_capture_agent.js"), encoding="utf-8") as fh:
        s_agent = session.create_script(fh.read())
    s_agent.on("message", _on_message)
    s_agent.load()
    exp = getattr(s_agent, "exports_sync", None) or s_agent.exports
    print("[diag3] ready =", exp.ready(), flush=True)

    probe = r"""
    (function(){
      var g = (typeof globalThis!=='undefined')?globalThis:this;
      var info = {probe:'globals',
        spp: typeof g.spp, cc: typeof g.cc, game: typeof g.game, gt: typeof g.gt,
        WebSocket: typeof g.WebSocket, jsb: typeof g.jsb, window: typeof g.window,
        require: typeof g.require, cocos: typeof g.cocos};
      try{ console.log('[[NVT]]'+JSON.stringify(info)); }catch(e){}
      // tenta tambem revelar nomes de topo (primeiros 40) p/ achar o objeto do jogo
      try{ var ks = Object.keys(g).slice(0,40); console.log('[[NVT]]'+JSON.stringify({globals_keys:ks})); }catch(e){}
      return 1;
    })();
    """
    try:
        print("[diag3] eval ret =", exp.eval_string(probe), flush=True)
    except Exception as e:
        print("[diag3] eval erro:", e, flush=True)

    t0 = time.time()
    while time.time() - t0 < 12:
        time.sleep(0.3)
    for s in (s_agent, s_log):
        try: s.unload()
        except Exception: pass
    try: session.detach()
    except Exception: pass
    print("[diag3] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
