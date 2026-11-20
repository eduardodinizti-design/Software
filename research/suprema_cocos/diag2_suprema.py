"""DIAG2 Suprema (read-only): confirma o MOTOR (Lua x JS) e acha o canal de log.
- enumera exports de libcocos2d/EXE que revelam o motor (lua/script/dostring/evalstring/log);
- hook NATIVO em LuaLog (le o char* -> stdout) p/ ver o spew do jogo (SE for Lua);
- janela p/ o usuario jogar 1 mao. Nenhuma acao no jogo."""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AGENT = r"""
'use strict';
const COCOS = 'libcocos2d.dll';
function relevant(name){ return /lua_|luaL_|dostring|loadstring|luaLog|LuaLog|ScriptEngine|evalString|evalstr|jsb|require|^\?log@|ccLog|SE_LOG|runScript|executeScript/i.test(name); }
function enumEngine(){
  const out = [];
  for (const modName of [COCOS, Process.enumerateModules()[0].name]) {
    let mod; try { mod = Process.getModuleByName(modName); } catch(e){ continue; }
    try { mod.enumerateExports().forEach(e => { if (relevant(e.name)) out.push({mod:modName, name:e.name, addr:e.address.toString()}); }); } catch(e){}
  }
  send({engine_exports: out.slice(0, 80)});
}
function hookLuaLog(){
  const mod = Process.getModuleByName(COCOS);
  // RVA de ?LuaLog@cocos2d@@YAXPBD@Z visto no diag = 0x729c86ff - base; resolve por nome:
  let addr = null;
  try { addr = mod.findExportByName('?LuaLog@cocos2d@@YAXPBD@Z'); } catch(e){}
  if (!addr) { send({luaLog: 'export nao encontrado'}); return; }
  Interceptor.attach(addr, {
    onEnter(args){ try { const s = args[0].readCString(); if (s) send({lualog: s.length > 300 ? s.slice(0,300) : s}); } catch(e){} }
  });
  send({luaLog: 'hookado @ ' + addr});
}
rpc.exports = {
  go(){ try { enumEngine(); hookLuaLog(); return true; } catch(e){ return String(e); } }
};
"""


def _on_message(m, _data):
    if m.get("type") == "send":
        p = m.get("payload") or {}
        if "engine_exports" in p:
            print("[ENGINE EXPORTS]", flush=True)
            for e in p["engine_exports"]:
                print("   ", e.get("mod"), e.get("name"), e.get("addr"), flush=True)
        elif "lualog" in p:
            print("[LUALOG]", p["lualog"], flush=True)
        else:
            print("[send]", p, flush=True)
    elif m.get("type") == "error":
        print("[js-erro]", m.get("stack") or m.get("description"), flush=True)


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "supremapoker.exe"]
    if not procs:
        print("[diag2] SupremaPoker.exe nao aberto."); return 1
    session = dev.attach(procs[0].pid)
    script = session.create_script(AGENT)
    script.on("message", _on_message)
    script.load()
    exp = getattr(script, "exports_sync", None) or script.exports
    print("[diag2] go =", exp.go(), flush=True)
    t0 = time.time()
    while time.time() - t0 < 75:
        time.sleep(0.3)
    try: script.unload()
    except Exception: pass
    try: session.detach()
    except Exception: pass
    print("[diag2] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
