"""DIAG4 Suprema (read-only): decide LUA x JS DEFINITIVAMENTE chamando
cocos2d::ScriptEngineManager::getInstance()->getScriptEngine()->getScriptType().
ccScriptType: 0=None, 1=Lua, 2=JavaScript. Tambem enumera modulos de rede p/ o plano B
(hook do protocolo). Nenhuma acao no jogo."""
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AGENT = r"""
'use strict';
const COCOS='libcocos2d.dll';
const mod=Process.getModuleByName(COCOS);
function f(sym, ret, args, conv){ const a=mod.findExportByName(sym); if(!a) return null; return new NativeFunction(a, ret, args, conv||undefined); }
try{
  const getInst=f('?getInstance@ScriptEngineManager@cocos2d@@SAPAV12@XZ','pointer',[]);
  const getEng=f('?getScriptEngine@ScriptEngineManager@cocos2d@@QAEPAVScriptEngineProtocol@2@XZ','pointer',['pointer'],'thiscall');
  const getType=f('?getScriptType@ScriptEngineProtocol@cocos2d@@UAE?AW4ccScriptType@2@XZ','int',['pointer'],'thiscall');
  if(!getInst||!getEng||!getType){ send({err:'simbolo ausente', getInst:!!getInst, getEng:!!getEng, getType:!!getType}); }
  else {
    const mgr=getInst();
    const eng=mgr.isNull()?NULL:getEng(mgr);
    const type=eng.isNull()?-1:getType(eng);
    send({script_type:type, label:({0:'None',1:'Lua',2:'JavaScript'}[type]||'?'), mgr:mgr.toString(), eng:eng.toString()});
  }
}catch(e){ send({err:String(e)}); }
// plano B: quais modulos podem carregar o protocolo de rede (websocket/ssl/proto)?
try{
  const mods=Process.enumerateModules().filter(m=>/websocket|ssl|libcurl|crypto|net|proto|game|spp|suprema|v8|lua|script|mozjs|jsc/i.test(m.name)).map(m=>m.name);
  send({net_modules:mods});
}catch(e){}
// e no EXE: ha exports de lua_/se:: (p/ saber onde o script vive)?
try{
  const exe=Process.enumerateModules()[0];
  const ex=exe.enumerateExports().filter(e=>/lua_|luaL_|^se@|ScriptEngine|evalString/i.test(e.name)).slice(0,20).map(e=>e.name);
  send({exe_script_exports:ex, exe:exe.name});
}catch(e){}
"""


def _on(m, _d):
    if m.get("type") == "send":
        print("[send]", m.get("payload"), flush=True)
    elif m.get("type") == "error":
        print("[js-erro]", m.get("stack") or m.get("description"), flush=True)


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "supremapoker.exe"]
    if not procs:
        print("[diag4] SupremaPoker.exe nao aberto."); return 1
    session = dev.attach(procs[0].pid)
    s = session.create_script(AGENT)
    s.on("message", _on)
    s.load()
    time.sleep(2.0)
    try: s.unload()
    except Exception: pass
    try: session.detach()
    except Exception: pass
    print("[diag4] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
