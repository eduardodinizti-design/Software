import os, sys, json
BOT = r"C:\Meus Projetos\Aplicativos\_repo_software"
TRK = r"C:\Users\tacao\NvtVoz\nvttracker"
sys.path.insert(0, BOT); sys.path.insert(0, TRK)
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
from hand_accumulator import HandAccumulator
from suprema_hand_builder import SupremaHandBuilder
from nvttracker.parser.nlhe_text import parse_hand, ParseError

FIX = os.path.join(BOT, "research", "suprema_cocos", "fixtures", "hands_2011.jsonl")
out = []
acc = HandAccumulator(room="SupremaPoker", tournament_id="14625", table_tag="mesa19", max_seats=9,
                      on_hand=lambda t, h: out.append(t))
b = SupremaHandBuilder(acc)
for line in open(FIX, encoding="utf-8"):
    r = json.loads(line); b.feed(r.get("msg") or r)

print("HH emitidos:", len(out), "\n")
for i, text in enumerate(out):
    print("=" * 60, "\nMÃO", i + 1)
    try:
        h = parse_hand(text, check_chips=True)
        print("  ✅ PARSE OK | saldo=%s | jogadores=%s | pote=%s" % (
            h.chip_balance(), len(getattr(h, 'seats', []) or []), getattr(h, 'total_pot', '?')))
    except ParseError as e:
        print("  ❌ ParseError:", e)
        # mostra o texto p/ depurar
        print("  --- HH ---")
        for ln in text.splitlines():
            print("   ", ln)
