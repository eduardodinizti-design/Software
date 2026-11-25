"""DIAG7 Suprema (read-only): captura o PROMPT ATIVO (a vez do heroi) + blinds + hero seat.
Hook SSL_read; grava payload COMPLETO de frames com 'prompt', config de sala (blind/sb/bb/
ante/room), e gamer_prompt com acao NAO-null. JOGUE ATE SER SUA VEZ e aja. Nenhuma acao."""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suprema_prompt_capture.log")

AGENT = r"""
'use strict';
const a=Process.getModuleByName('libssl-1_1.dll').findExportByName('SSL_read');
if(!a){ send({err:'sem SSL_read'}); }
else Interceptor.attach(a, {
  onEnter(args){ this.buf=args[1]; },
  onLeave(ret){
    try{
      let n=ret.toInt32(); if(n<=0||!this.buf) return;
      const take=Math.min(n, 8000);
      const bytes=new Uint8Array(this.buf.readByteArray(take));
      let s=''; for(let i=0;i<bytes.length;i++){ const c=bytes[i]; s += (c>=32&&c<127)?String.fromCharCode(c):'.'; }
      const active = /"gamer_prompt":\{[^}]*"(fold|check|call|raise|all_in|bet)":\{/.test(s);  // acao NAO-null
      const isPrompt = /"event":"prompt"/.test(s);
      const isConfig = /("small_blind"|"big_blind"|"smallBlind"|"bigBlind"|"ante"|"blind"|"roomConfig"|"enterRoom"|"sb_amount"|"bb_amount"|"blinds")/.test(s);
      if(isPrompt || isConfig || active){ send({full:s, active:active, kind: isPrompt?'prompt':(isConfig?'config':'other')}); }
    }catch(e){}
  }
});
send({ready:true});
"""


def main():
    import frida
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == "supremapoker.exe"]
    if not procs:
        print("[diag7] SupremaPoker.exe nao aberto."); return 1
    session = dev.attach(procs[0].pid)
    fh = open(OUT, "w", encoding="utf-8")
    cnt = {"n": 0, "active": 0, "config": 0}

    def _on(m, _d):
        if m.get("type") == "send":
            p = m.get("payload") or {}
            if "full" in p:
                cnt["n"] += 1
                if p.get("active"):
                    cnt["active"] += 1
                if p.get("kind") == "config":
                    cnt["config"] += 1
                fh.write("\n===== frame %d kind=%s active=%s =====\n" % (cnt["n"], p.get("kind"), p.get("active")))
                fh.write(p["full"])
                fh.flush()
            elif "ready" in p:
                print("[diag7] hook pronto; JOGUE ATE SER SUA VEZ e aja (90s).", flush=True)
        elif m.get("type") == "error":
            print("[js-erro]", m.get("stack") or m.get("description"), flush=True)

    s = session.create_script(AGENT)
    s.on("message", _on)
    s.load()
    t0 = time.time()
    while time.time() - t0 < 90:
        time.sleep(0.3)
    try: s.unload()
    except Exception: pass
    try: session.detach()
    except Exception: pass
    fh.close()
    print("[diag7] fim. frames=%d (prompt_ativo=%d, config=%d) -> %s" % (cnt["n"], cnt["active"], cnt["config"], OUT), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
