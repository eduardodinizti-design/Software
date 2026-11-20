"""DIAG5 Suprema (read-only): captura o PROTOCOLO da mao via TLS. Hooka SSL_read/SSL_write
em libssl-1_1.dll (ponto ja descriptografado) e mostra um preview (ascii+hex) dos buffers
enquanto o usuario joga 1 mao. Objetivo: ver se o protocolo e JSON/texto ou binario
(protobuf) e quais mensagens carregam deal/acao/board/winner. Nenhuma acao no jogo."""
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AGENT = r"""
'use strict';
const SSL='libssl-1_1.dll';
function hookRW(name, dir){
  let a=null; try{ a=Process.getModuleByName(SSL).findExportByName(name); }catch(e){}
  if(!a){ send({hook:name, ok:false}); return; }
  Interceptor.attach(a, {
    onEnter(args){ this.buf=args[1]; this.num=args[2].toInt32(); },
    onLeave(ret){
      try{
        let n=ret.toInt32(); if(n<=0||!this.buf) return;
        const take=Math.min(n, 220);
        const bytes=new Uint8Array(this.buf.readByteArray(take));
        let ascii='', printable=0;
        for(let i=0;i<bytes.length;i++){ const c=bytes[i]; if(c>=32&&c<127){ ascii+=String.fromCharCode(c); printable++; } else ascii+='.'; }
        let hex=''; for(let i=0;i<Math.min(take,40);i++){ hex+=(('0'+bytes[i].toString(16)).slice(-2)); }
        send({dir:dir, n:n, frac_ascii:+(printable/bytes.length).toFixed(2), ascii:ascii, hex:hex});
      }catch(e){}
    }
  });
  send({hook:name, ok:true, addr:a.toString()});
}
hookRW('SSL_read','R');
hookRW('SSL_write','W');
"""

_SEEN = {"n": 0}


def _on(m, _d):
    if m.get("type") != "send":
        if m.get("type") == "error":
            print("[js-erro]", m.get("stack") or m.get("description"), flush=True)
        return
    p = m.get("payload") or {}
    if "hook" in p:
        print("[hook]", p, flush=True); return
    _SEEN["n"] += 1
    if _SEEN["n"] > 120:
        return
    # so mostra frames com algum texto legivel OU curtos (controle)
    print("[%s n=%d ascii=%.2f] %s | hex=%s" % (p.get("dir"), p.get("n"),
          p.get("frac_ascii", 0), (p.get("ascii") or "")[:160], (p.get("hex") or "")[:60]), flush=True)


def main():
    import frida
    dev = frida.get_local_device()
    procs = [pp for pp in dev.enumerate_processes() if pp.name.lower() == "supremapoker.exe"]
    if not procs:
        print("[diag5] SupremaPoker.exe nao aberto."); return 1
    session = dev.attach(procs[0].pid)
    s = session.create_script(AGENT)
    s.on("message", _on)
    s.load()
    print("[diag5] hooks TLS instalados; JOGUE 1 MAO agora (75s).", flush=True)
    t0 = time.time()
    while time.time() - t0 < 75:
        time.sleep(0.3)
    try: s.unload()
    except Exception: pass
    try: session.detach()
    except Exception: pass
    print("[diag5] fim. frames vistos =", _SEEN["n"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
