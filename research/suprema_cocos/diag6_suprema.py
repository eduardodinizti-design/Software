"""DIAG6 Suprema (read-only): captura PAYLOADS COMPLETOS dos eventos de jogo (SSL_read),
grava num arquivo p/ analise offline do schema (cartas do heroi, prompt ativo, acoes,
resultado, codificacao de carta). Filtra so eventos de jogo (menos ruido de match/jackpot).
JOGUE 1 MAO COMPLETA (sente, receba cartas, aja, showdown). Nenhuma acao no jogo."""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suprema_capture_full.log")

AGENT = r"""
'use strict';
const SSL='libssl-1_1.dll';
const a=Process.getModuleByName(SSL).findExportByName('SSL_read');
if(!a){ send({err:'sem SSL_read'}); }
else Interceptor.attach(a, {
  onEnter(args){ this.buf=args[1]; },
  onLeave(ret){
    try{
      let n=ret.toInt32(); if(n<=0||!this.buf) return;
      const take=Math.min(n, 8000);
      const bytes=new Uint8Array(this.buf.readByteArray(take));
      let s=''; for(let i=0;i<bytes.length;i++){ const c=bytes[i]; s += (c>=32&&c<127)?String.fromCharCode(c):'.'; }
      // so eventos de jogo (corta match/jackpot/countdown, que sao ruido p/ o schema)
      if(/"event":"(gameinfo|moveturn|prompt|dealCard|handCard|deal|settle|gameResult|showdown|action|sitdown|buyin)"/.test(s)
         || /"cards":\[[0-9]/.test(s) || /"hole|"hand_card|"gamer_prompt":\{"fold":\{/.test(s)){
        send({full:s});
      }
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
        print("[diag6] SupremaPoker.exe nao aberto."); return 1
    session = dev.attach(procs[0].pid)
    fh = open(OUT, "w", encoding="utf-8")
    cnt = {"n": 0}

    def _on(m, _d):
        if m.get("type") == "send":
            p = m.get("payload") or {}
            if "full" in p:
                cnt["n"] += 1
                fh.write("\n===== frame %d =====\n" % cnt["n"])
                fh.write(p["full"])
                fh.flush()
            elif "ready" in p:
                print("[diag6] hook pronto; JOGUE 1 MAO COMPLETA (90s).", flush=True)
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
    print("[diag6] fim. frames de jogo gravados =", cnt["n"], "->", OUT, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
