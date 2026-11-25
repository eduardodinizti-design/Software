"""Runner do recon_enterroom.js (READ-ONLY): anexa no PPPoker e imprime o dump dos
campos de EnterRoomRSP/SeatStatusBRC p/ achar assento->ID+nick."""
import os, sys, time
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import frida

HERE = os.path.dirname(os.path.abspath(__file__))
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0

dev = frida.get_local_device()
procs = [p for p in dev.enumerate_processes() if p.name.lower() == "pppoker.exe"]
if not procs:
    print("[recon] PPPoker nao esta aberto."); sys.exit(1)
pid = procs[0].pid
session = dev.attach(pid)
with open(os.path.join(HERE, "recon_enterroom.js"), encoding="utf-8") as fh:
    script = session.create_script(fh.read())
script.set_log_handler(lambda level, text: print(text, flush=True))
script.on("message", lambda m, d: print("[msg]", m.get("payload") or m, flush=True))
script.load()
print(f"[recon] anexado ao PPPoker (pid {pid}). Observando {SECONDS:.0f}s...", flush=True)
t0 = time.time()
try:
    while time.time() - t0 < SECONDS:
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    try: session.detach()
    except Exception: pass
print("[recon] fim.", flush=True)
